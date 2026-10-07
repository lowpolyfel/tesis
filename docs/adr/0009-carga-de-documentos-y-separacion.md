# 0009. Carga de documentos y separación en requisitos candidatos

- **Fecha:** 2026-10-06
- **Estado:** Aceptada (las heurísticas de separación son v1 y se revisan con documentos reales)

## Contexto

CONTEXTO §9 limita la entrada a texto plano y PDF con texto extraíble. Hasta
ahora el frontend leía el PDF en el navegador (pdfjs) y lo partía con una
expresión regular: se perdían la página y la numeración original (RF-01,
3.2.1), los encabezados y pies repetidos se colaban como requisitos y lo que se
dejaba fuera no se veía en ningún lado. ADR 0008 ya prevé el `origen` de cada
requisito (documento, archivo, página, índice, marca, texto original); faltaba
quién lo llenara con datos confiables.

## Decisión

1. **El backend extrae y propone; el humano decide** (`app/documentos/`). Nada
   entra al grafo hasta que el humano revisa, edita si quiere y confirma con el
   endpoint existente `POST /proyectos/{id}/requisitos`, que lleva el `origen` de
   cada requisito. La carga no llama a ningún LLM, así que no pasa por la cola.
2. **Extracción** (`extraccion.py`): pypdf, texto por página. El tipo se decide
   por la firma (`%PDF-`) y luego por la extensión.
   - PDF sin texto extraíble → **422** que cita CONTEXTO §9 (sin OCR). Una página
     sin texto entre otras con texto → advertencia con su número.
   - PDF dañado o con contraseña → 422. Más de `DOCUMENTO_MAX_MB` → **413**.
     Otro tipo (docx, imagen…) → **415**.
   - `.txt`: UTF-8 (con o sin BOM) o UTF-16 con BOM; si no, Windows-1252 y al
     final latin-1, con advertencia. Se prueba cp1252 antes de latin-1 porque es
     lo que guarda el Bloc de notas en español: coincide con latin-1 en acentos y
     eñes, y además decodifica comillas curvas y rayas, que latin-1 convierte en
     caracteres de control. Un salto de página (`\f`) separa páginas.
3. **Limpieza** (`limpieza.py`): NFKC (ligaduras, espacios duros), sin guiones
   suaves ni caracteres invisibles; un guion suave al final del renglón (así
   marcan el corte de palabra algunos PDF: el byte 0xAD de WinAnsi) cuenta como
   guion de corte. Solo cuando hay páginas reales:
   - números de página sueltos («7», «- 7 -», «Página 7 de 9») en los tres
     primeros y tres últimos renglones de cada página;
   - encabezados y pies: renglones de esos bordes que se repiten (sin acentos y
     con los dígitos como comodín) en al menos la mitad de las páginas con texto
     y en dos como mínimo. Nunca se toma como encabezado un renglón con verbo de
     obligación, una marca sola («RF-01» en una celda) ni uno que empieza con
     identificador: con los dígitos como comodín, «RF-01 Registro de usuarios» y
     «RF-02 Registro de usuarios» arriba de dos páginas parecerían el mismo.
   Lo quitado se informa en `advertencias` (cuántas páginas): nada se descarta
   en silencio.
4. **Reconstrucción de párrafos**: un renglón vacío cierra; una marca de
   numeración abre, salvo un número que sigue la oración: jerárquico ante
   minúscula («la versión / 2.1 o superior») o jerárquico o identificador tras
   palabra de enlace («un máximo de / 2.5 segundos», «lo indica el / RF-01»);
   `1.` `2)` siempre abren, también en minúscula y tras «…, y». Un renglón que
   empieza en minúscula, o un anterior que termina en coma, guion o palabra de
   enlace, continúa. Punto final seguido de mayúscula cierra, y también un
   renglón que abre oración con mayúscula inicial («El», «La», «Cada», «Se»,
   «Debe»…: a media oración van en minúscula), para que los requisitos escritos
   uno por renglón y sin punto no se peguen. Si no, sin punto final: en un PDF
   cierra si el renglón anterior es corto (menos del 75 % del percentil 90 del
   ancho: título o párrafo sin punto); en texto plano solo si el anterior es un
   título aislado (un renglón, sin verbo, 12 palabras o menos). La palabra
   cortada con guion al final del renglón se une si el siguiente empieza en
   minúscula. Un párrafo puede seguir en la página siguiente. El párrafo guarda
   la página de cada renglón y dónde empieza cada uno en el texto unido, para
   devolver de cada oración su pedazo del original.
5. **Separación** (`separacion.py`, función pura, sin LLM ni spaCy):
   - Oraciones por `. ! ?` seguidos de mayúscula, dígito o signo de apertura; no
     se parte tras abreviaturas («p. ej.», «Sr.»), iniciales, siglas con punto ni
     números que numeran (al inicio de la oración o tras dos puntos: «1.
     Ingresar», «Los pasos son: 1. Ingresar»). Un número al final de la oración sí
     la cierra («… de 5. El sistema…»), y «no.» solo es «número» ante un dígito
     («No. 5»; «… o no. El sistema…» cierra).
   - Se propone solo la oración con verbo de obligación o capacidad de una lista
     cerrada, comparada sin acentos: debe(n), deberá(n), debería(n), podrá(n),
     puede(n), permitirá(n), tiene/tienen/tendrá(n) que, ha/han/habrá(n) de, se
     requiere(n), es necesario/a, es obligatorio/a.
   - Marcas al inicio, guardadas en `marca`: viñetas (`-`, `•`, `*` y las de Word,
     que a menudo se extraen como caracteres de uso privado), `1.` `1)` `1-` `1.-`, `a)`,
     `3.2.1`, y RF-01, RF01, RNF-3, R1., REQ-12, [RF-02], CU-4, HU-7.
   - Frase introductoria con obligación que termina en dos puntos seguida de una
     lista sin verbos («El sistema deberá permitir:» / «- Registrar usuarios»):
     cada elemento se propone compuesto con la frase. Si la frase tenía
     identificador, el elemento lo conserva: con viñeta, «RF-03»; numerado,
     «RF-03.a» o «3.2.1.1». Sin lista, la frase se propone sola con advertencia.
   - Título con identificador y sin verbo («RF-01 Registro de usuarios») seguido
     de un párrafo sin marca: el párrafo hereda la marca (con advertencia).
   - Lo que no se propone va a `fragmentos_descartados` con página, marca y
     motivo (`titulo`, `sin_verbo_obligacion`, `sin_texto`); se devuelven los 50
     primeros y siempre el total (`total_descartados`).
   - De cada oración propuesta: `pagina` es la página donde empieza ella (no su
     párrafo) y `texto_original` es solo su pedazo del original, con sus
     renglones, sus guiones de corte y la marca si abre el párrafo. Copiar el
     párrafo entero en cada oración hacía crecer la respuesta con el cuadrado del
     largo del párrafo (66 KB pegados en un solo renglón daban 132 MB de JSON).
   - Todo es lineal en el tamaño del texto (las uniones de renglones y la
     revisión de abreviaturas solo miran la cola): los 10 MB permitidos tardan
     segundos, no horas.
6. **Advertencias por requisito propuesto**: más de 400 caracteres; sin sujeto
   explícito (empieza con el verbo, tras conectores como «además» o «se»);
   varias oraciones con obligación en el mismo párrafo; la oración continúa en
   otra página; compuesto con frase introductoria; marca heredada; repetido;
   caracteres no reconocidos (fuente del PDF sin mapa a Unicode).
7. **Persistencia**: colección `documentos` (`D01`…), validada con el modelo
   `Documento`. Guarda `texto_por_pagina` tal como se extrajo, para ubicar cada
   requisito en su página, y no un campo con el texto completo duplicado. Si el
   texto pasa de 1 000 000 de caracteres no se guarda y se advierte: límite
   técnico (16 MB por documento de Mongo, y los requisitos repiten parte del
   texto), no calibrable.
8. **Rutas**: `POST /proyectos/{id}/documentos` (multipart, campo `archivo`) →
   201 `Documento`; `GET /proyectos/{id}/documentos` → resúmenes;
   `GET /documentos/{documento_id}` → `Documento` (404 si no existe);
   `POST /requisitos/separar {texto}` → la misma separación sin guardar nada
   (`requisitos_propuestos`, `fragmentos_descartados`, `total_descartados` y las
   `advertencias` de la limpieza).

## Alternativas consideradas

- **Seguir separando en el navegador:** pierde página y marca, y no deja rastro
  de lo descartado ni de lo que la limpieza quitó.
- **Separar con el LLM:** no es reproducible, cuesta corridas, y sus errores se
  confundirían con los de los agentes, que son lo que se evalúa. El humano
  confirma de todos modos, así que lo determinista y explicable basta.
- **spaCy para oraciones y sujeto:** el segmentador de `es_core_news_sm` tropieza
  con numeraciones y renglones partidos, y ataría la separación al modelo.
- **pdfplumber/pdfminer con coordenadas, o el modo `layout` de pypdf:** darían
  posiciones para distinguir columnas y tablas, a cambio de otra dependencia y
  más heurísticas. pypdf ya estaba en `requirements.txt`.
- **OCR para PDF escaneados:** fuera por alcance (CONTEXTO §9): sus errores se
  confundirían con ambigüedad real.
- **Llevar las heurísticas a `Settings`:** no son parámetros del experimento,
  porque el humano confirma cada requisito antes de que entre al sistema.
  Quedan como constantes con nombre en el módulo (`LINEAS_BORDE`,
  `FRACCION_LINEA_LLENA`, `MAX_PALABRAS_TITULO`, `LARGO_ADVERTENCIA`,
  `MAX_FRAGMENTOS`); si hiciera falta ajustarlas sin tocar código, se mueven.

## Consecuencias

- El frontend deja de leer PDF (puede retirar `pdfjs-dist`): sube el archivo,
  muestra lo propuesto con sus advertencias y lo descartado, y envía lo
  confirmado con su `origen`.
- Las pruebas generan PDF reales byte por byte (Helvetica, `/WinAnsiEncoding`,
  acentos como escapes octales) y comprueban que pypdf devuelve acentos y eñes.
- Limitaciones conocidas:
  - Tablas y texto en varias columnas: pypdf lee renglón por renglón y puede
    mezclar celdas o columnas.
  - El presente descriptivo («el sistema registra») y otros giros («se
    necesita», «habrá que») no se reconocen como requisito: aparecen en
    descartados. A la inversa, «puede» capta oraciones que solo expresan
    posibilidad («puede ocurrir que…»).
  - Una palabra compuesta partida justo en su guion («teórico-/práctico») se une
    sin el guion.
  - Un nombre propio que empieza con artículo al inicio del renglón y tras una
    palabra que no es de enlace («la sucursal / La Paz debe…») se toma como
    oración nueva. A la inversa, requisitos sin punto final uno por renglón que
    no empiezan con una palabra de apertura («Cajeros y supervisores podrán…»)
    se siguen uniendo al renglón anterior en texto plano; el humano los separa
    al editar.
  - Una lista con `3.2.1` en minúscula o tras palabra de enlace se toma como
    continuación de la oración (para no partir «versión / 2.1 o superior»).
  - Las viñetas de segundo nivel de Word que se extraen como la letra «o» no se
    reconocen como marca.
  - Encabezados que cambian en cada página (el nombre de cada capítulo) no se
    detectan; renglones repetidos de una plantilla («Prioridad: Alta») pueden
    quitarse como pie, aunque queda advertido.
  - La composición con frase introductoria acepta cualquier elemento con marca
    de lista: si la «lista» eran subtítulos, el requisito compuesto no tiene
    sentido (va con advertencia y el humano lo corrige).
  - El tamaño máximo se revisa cuando Starlette ya recibió el archivo (lo
    guarda en un temporal); limitar el cuerpo HTTP le toca al proxy.
  - La extracción corre en el hilo de la petición: un PDF de cientos de páginas
    tarda segundos.
  - Un PDF de 10 MB comprimido puede contener varios millones de caracteres: si
    lo propuesto pasa de unos 7 millones, el documento excede los 16 MB de Mongo
    y la carga falla (el JSON no tiene ese límite). No se acota porque un SRS
    real está órdenes de magnitud por debajo.
  - El endpoint que confirma (`POST /proyectos/{id}/requisitos`, ADR 0008)
    acepta hasta 200 requisitos por llamada y 2 000 caracteres por texto: un
    documento con más propuestos se confirma por partes, y un propuesto más
    largo se recorta al editarlo (ya lleva la advertencia de más de 400).
