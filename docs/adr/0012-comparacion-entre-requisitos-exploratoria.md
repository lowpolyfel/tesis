# 0012. Comparación entre requisitos de un proyecto (módulo exploratorio)

- **Fecha:** 2026-10-06
- **Estado:** Aceptada como **exploratoria**. **Amplía el alcance** de CONTEXTO §6
  y queda **pendiente de revisar con la asesora** (Dra. Karla Olmos Sánchez).

## Contexto

CONTEXTO §6 deja **fuera** la contradicción entre requisitos distintos: el
sistema procesa cada requisito por separado y su aportación es la divergencia
entre interpretaciones **de un mismo enunciado** (ADR 0002). Con los proyectos
(ADR 0008) y la carga de documentos (ADR 0009), un proyecto ya agrupa decenas de
requisitos de un mismo dominio, y aparecen problemas que el núcleo no ve por
diseño: dos requisitos que se contradicen, dos que piden lo mismo con otras
palabras, o un término que quedó validado con un significado en un requisito y
con otro en el siguiente (pasa cuando dos requisitos de un mismo lote se debaten
antes de que el primero entre al LEL).

El usuario decidió agregar esa revisión como un **módulo aparte**, sin tocar el
grafo ni el debate. Hay que dejar claro que no es parte de la aportación: negociar
conflictos entre requisitos que ya se entienden es justo lo que hacen ArgRE y
MARE (CONTEXTO §3), y la tesis se distingue de ellos por no hacerlo.

## Decisión

1. **Paquete aparte** `app/comparacion/`. No modifica trazas, estados, mensajes,
   el LEL ni el grafo: lee las trazas del proyecto, la colección `formalizados`
   y el LEL del proyecto, y escribe solo en la colección `comparaciones`. Se
   corre a pedido, por proyecto.
2. **Base de comparación por requisito:** el `requisito_reescrito` del documento
   de `formalizados` si existe; si no, el texto original. Cada requisito registra
   cuál se usó (`base: reescrito | original`). Se excluyen los requisitos en
   `error` o `rechazado` y, además, los que otro requisito vigente vuelve a
   procesar (`origen.reproceso_de`): compararlos con su versión nueva solo daría
   un duplicado obvio. Los excluidos se listan con su motivo.
3. **Inconsistencia de vocabulario, determinista y sin LLM:**
   - el mismo símbolo del LEL (normalizado) con nociones distintas en
     requisitos distintos (`fuente: lel`);
   - el mismo término validado con significados distintos, tomados de las
     `resoluciones` del documento formalizado o, si no lo hay, del último mensaje
     `validacion` **aprobado** (`fuente: validacion`).
   Solo ambigüedad léxica (y trazas sin tipo, ADR 0010): el referente de una
   anáfora o el alcance de un cuantificador son propios de cada requisito y que
   difieran no es inconsistencia. El criterio es el mismo que el de las
   ambigüedades del proyecto (ADR 0015 §6), comparación literal sin mayúsculas
   ni acentos, pero expresado **por par** de requisitos. Si un par tiene las dos
   cosas para el mismo término sale un solo hallazgo (`lel`) que menciona
   también los significados.
4. **Selección de pares:** embeddings del texto base de cada requisito y coseno a
   mano (`app.divergence.similitud.coseno`); la matriz completa se guarda. Un par
   es **candidato** si su coseno alcanza `comparacion_relacion_umbral` **o** si
   comparten un símbolo del LEL (por forma o por secuencia de lemas) o un lema de
   contenido. Los candidatos se ordenan por coseno descendente y se cortan en
   `comparacion_max_pares`; los que quedan fuera se cuentan y se listan con su
   similitud y motivo. Nada se corta en silencio.
5. **Casi duplicado, determinista:** todo par con coseno ≥
   `comparacion_duplicado_umbral`, haya entrado o no al juez (`fuente: embeddings`).
6. **Juez LLM por par candidato** (prompt `comparador_v1`, cliente
   `llm_comparador`): salida estructurada `{relacion: contradiccion | redundancia
   | complementaria | independiente, explicacion (≤ 60 palabras), cita_a, cita_b}`
   con validación y un reintento (ADR 0001). El prompt pide que cada cita se copie
   tal cual del requisito. El código **verifica** que cada cita aparezca literal
   en su texto base (sin distinguir mayúsculas, acentos, espacios repetidos ni
   comillas o puntuación en los extremos) y lo registra como `verificada`; **no
   descarta** el juicio. `contradiccion` y `redundancia` producen hallazgo;
   `complementaria` e `independiente` quedan solo en `relaciones_por_par`.
7. **Fallos:** si el LLM falla en un par (salida inválida tras el reintento o el
   servidor no responde), el par queda con `relacion: null` y su `error` (con las
   salidas crudas si fue un `FalloEstructurado`) y la comparación sigue. Si falla
   algo que no es de un par (embeddings, spaCy), la comparación queda en `error`
   y conserva lo determinista ya calculado.
8. **Ejecución por la cola** (ADR 0008), prioridad `analisis`, la más baja:
   `POST /proyectos/{id}/comparaciones` responde 202 `en_cola`; menos de dos
   requisitos comparables es 422. El documento (`C01`, `C02`…) se guarda tras cada
   paso y tras cada par (`avance`), para que la interfaz muestre el progreso.
   Cada ejecución recalcula desde cero. `comparar` corre en el mismo hilo para
   pruebas y scripts; `recuperar` vuelve a encolar las que quedaron pendientes
   tras un reinicio.
9. **Configuración registrada** en cada comparación: umbrales, límite de pares,
   modelo, versión de prompt y modelo de embeddings. Los tres parámetros vienen de
   `Settings`; ninguno está escrito en el código.

## Justificación

La preselección por embeddings y vocabulario compartido acota las llamadas al
LLM: con 25 requisitos hay 300 pares, y con un solo trabajador local juzgarlos
todos tardaría demasiado para un módulo secundario. El juez existe porque el
coseno no distingue contradicción de redundancia: «debe cerrarse a los 15
minutos» y «nunca debe cerrarse» quedan cerca en el espacio de embeddings. Las
citas verificadas en código siguen la misma idea que R1 y R2 del Crítico (ADR
0004): lo que se puede comprobar sin LLM se comprueba en código.

## Alternativas consideradas

- **Meterlo en el grafo o en el debate:** la unidad del grafo y de la validación
  humana es el requisito; un par no tiene estado en esa máquina y rompería la
  trazabilidad por requisito. Se descartó.
- **Juzgar todos los pares con el LLM:** crecimiento cuadrático y costo
  impredecible. Se prefirió preseleccionar y reportar lo que queda fuera.
- **Solo embeddings, sin LLM:** determinista y barato, pero ciego a la negación;
  se usa solo para el casi duplicado.
- **Modelo de inferencia (NLI) para contradicción:** agregaría una dependencia
  sin modelo en español en el stack actual; queda como trabajo futuro.
- **Descartar los juicios con citas no verificadas:** perdería juicios correctos
  con una cita mal copiada; se prefirió marcarlos y dejar el juicio al humano.
- **Lista de palabras genéricas para el criterio de lemas** («sistema»,
  «usuario»): sería un parámetro escrito a mano en el código; no se agregó.

## Consecuencias

- **Amplía el alcance** declarado en CONTEXTO §6. Sus resultados son
  exploratorios: no entran en la evaluación del núcleo ni se presentan como
  aportación. Si la asesora decide dejarlo fuera, se quita el paquete y su ruta
  sin tocar el núcleo.
- **No hay ground truth** de contradicciones ni redundancias en el corpus: no se
  mide precisión ni exhaustividad. Los valores por defecto (0.60, 0.92, 60 pares)
  son provisionales y no se calibran (la calibración cubre solo el umbral de
  divergencia).
- **El juicio es de un solo modelo, sin debate ni divergencia**: justo el
  esquema que la tesis critica en otros sistemas. Es aceptable para un módulo de
  apoyo, no para afirmar que detecta contradicciones.
- El criterio de lemas es amplio: palabras genéricas como «sistema» hacen
  candidatos a casi todos los pares, y en la práctica decide el corte por coseno.
- El coseno se calcula sobre el texto completo: un casi duplicado puede ser en
  realidad una contradicción; el hallazgo `casi_duplicado` no lo distingue y solo
  el juez puede, si el par entró.
- La verificación de citas comprueba **que el texto existe**, no que sostenga el
  juicio: una cita literal puede ser irrelevante y una no verificada puede ser una
  paráfrasis fiel. Es evidencia, no prueba.
- Comparar un requisito reescrito con uno original mezcla estilos: el reescrito
  trae vocabulario del LEL y puede subir o bajar la similitud. Por eso se
  registra la base de cada uno.
- La inconsistencia es literal (como en ADR 0015): «periodo de uso» y «periodo de
  uso del sistema» cuentan como distintos (falso positivo posible).
- Un hallazgo del LEL puede citar un requisito excluido por reprocesado: su
  entrada sigue en la memoria del proyecto y la inconsistencia es real; queda con
  `similitud: null` porque ese requisito no está en la matriz.
- El orden A/B lo fija el número de requisito; el juez puede ser sensible al
  orden y no se prueba el par invertido.
- La comparación es una foto: no se actualiza si los requisitos cambian. Tras un
  reinicio se vuelve a correr completa, y con temperatura mayor que cero puede
  dar juicios distintos.
- El máximo de 60 palabras de la explicación es un límite de formato del
  contrato (constante), no un parámetro calibrable.
