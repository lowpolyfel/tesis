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
   - PDF dañado o con contraseña de apertura → 422. Más de `DOCUMENTO_MAX_MB` →
     **413**. Otro tipo (docx, imagen…) → **415**.
   - PDF cifrado solo con contraseña de propietario (Word y Acrobat lo hacen al
     restringir edición, copia o impresión): se abre con contraseña vacía. Con
     AES, pypdf necesita el paquete `cryptography`; si falta, el 422 lo dice en
     vez de tratar cada página como vacía y terminar en «¿es un escaneo?».
   - pypdf decodifica los mapas ToUnicode con `surrogatepass`: un glifo puede dar
     media pareja sustituta UTF-16 (un emoji partido, una CMap mal hecha), que no
     se puede guardar en UTF-8 ni en BSON y daba 500. Las parejas completas se
     unen; las mitades sueltas se cambian por U+FFFD, con advertencia de página
     (y la del requisito: «caracteres no reconocidos»).
   - **Costo acotado** (límites técnicos en `extraccion.py`, no calibrables):
     pypdf lee los operadores en Python, a unos 3 s por MB, y la lectura de un
     flujo no se puede interrumpir; un PDF de 30 KB cuyo flujo se infla a 20 MB
     tardaba casi un minuto por página. Antes de leer cada página se mide su
     contenido descomprimido más el de los formularios (XObject) que usa: si pasa
     de 2 MB (una página de texto ocupa unos 6 KB; más es un dibujo) no se lee y
     se advierte. Además, todo el PDF tiene 30 s: el tiempo se revisa antes de
     cada operador (también dentro de los formularios, que pypdf vuelve a leer en
     cada uso) y al agotarse las páginas que faltan no se extraen y se advierte.
     Si por estos límites, o por páginas dañadas, no queda texto, el 422 dice
     por qué, no «¿es un escaneo?».
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
6. **Advertencias por requisito propuesto**: más de 2 000 caracteres, lo más que
   acepta la carga (`MAX_CARACTERES_REQUISITO`, igual al de `RequisitoNuevo`; una
   prueba lo compara), también como advertencia del documento con los índices,
   para que el humano lo recorte o lo parta antes de analizar; si no, más de
   400 caracteres (puede ser más de un requisito); sin sujeto
   explícito (empieza con el verbo, tras conectores como «además» o «se»);
   varias oraciones con obligación en el mismo párrafo; la oración continúa en
   otra página; compuesto con frase introductoria; marca heredada; repetido;
   caracteres no reconocidos (fuente del PDF sin mapa a Unicode).
7. **Persistencia**: colección `documentos` (`D01`…), validada con el modelo
   `Documento`. Guarda `texto_por_pagina` tal como se extrajo, para ubicar cada
   requisito en su página, y no un campo con el texto completo duplicado. Si el
   texto pasa de 1 000 000 de caracteres no se guarda y se advierte. Además se
   mide el JSON de lo que se guardaría: Mongo no acepta un documento de más de
   16 MiB de BSON, y lo propuesto puede pesar varias veces el archivo (un .txt de
   2 MB con una lista bajo una frase introductoria propone 100 000 requisitos y
   pesa 28 MB). Si pasa de 8 MB (la mitad: el BSON pesa casi lo mismo que el
   JSON, y un poco más con muchas listas cortas), primero se deja fuera
   `texto_por_pagina`, con advertencia; si aún no cabe, **413** con cuántos
   requisitos propone y que se divida el archivo, sin guardar nada. Límites
   técnicos, no calibrables.
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
  Igual los límites técnicos (`MAX_BYTES_OPERADORES_PAGINA`,
  `TIEMPO_MAX_EXTRACCION`, `MAX_BYTES_GUARDADOS`, `MAX_CARACTERES_GUARDADOS`).
- **Partir en la separación los propuestos de más de 2 000 caracteres:** sin
  puntos no hay dónde partir con sentido; cortar por largo daría mitades que el
  humano tendría que unir. Se advierte y él decide.
- **Proponer solo los primeros N requisitos en lugar de rechazar el documento
  que no cabe:** dejaría fuera requisitos sin que el humano lo note al
  confirmar; un SRS real queda muy por debajo de los 8 MB.

## Consecuencias

- El frontend deja de leer PDF (puede retirar `pdfjs-dist`): sube el archivo,
  muestra lo propuesto con sus advertencias y lo descartado, y envía lo
  confirmado con su `origen`.
- Las pruebas generan PDF reales byte por byte (Helvetica, `/WinAnsiEncoding`,
  acentos como escapes octales) y comprueban que pypdf devuelve acentos y eñes.
  Los cifrados con AES van incrustados en base64 (`pdf_cifrados.py`) porque
  generarlos requiere `cryptography`; la prueba exige el texto si está instalado
  y el mensaje de la dependencia si no. Los topes de costo se prueban con un
  reloj falso que avanza en cada consulta.
- `backend/requirements.txt` debe incluir `cryptography` para leer PDF cifrados
  con AES.
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
    tarda segundos (300 páginas de texto, unos 2.5 s). Con los topes, el peor
    caso son unos 30 s más la lectura de una página de hasta 2 MB (unos 6 s), y
    mientras tanto el resto de la API responde más lento (el GIL). Extraer en un
    proceso aparte con tiempo límite lo aislaría del todo, a cambio de lanzar
    un intérprete por carga y de las diferencias de `multiprocessing` en Windows.
  - El tope de 30 s depende de la máquina: en una lenta, un PDF legítimo muy
    largo podría quedar incompleto. Queda advertido con las páginas que faltan.
  - Una página con texto y un dibujo de más de 2 MB se pierde completa (con
    advertencia de su número): el humano copia su texto si tenía requisitos.
  - La descompresión no tiene tope propio: la acota pypdf (75 MB por flujo).
  - Sin `cryptography` instalado, los PDF cifrados con AES se rechazan con 422
    (el mensaje lo dice); con RC4 se leen.
  - Un documento cuyo JSON pasa de 8 MB se rechaza aunque quizá cupiera en
    Mongo; con el repositorio JSON, `GET /proyectos/{id}/documentos` relee
    cada documento entero (hasta 8 MB cada uno).
  - El endpoint que confirma (`POST /proyectos/{id}/requisitos`, ADR 0008)
    acepta hasta 200 requisitos por llamada y 2 000 caracteres por texto: un
    documento con más propuestos se confirma por partes, y un propuesto más
    largo lleva su advertencia y el humano lo recorta o lo parte al editarlo
    (la separación no parte una oración sin puntos: saldrían mitades sin
    sentido).
