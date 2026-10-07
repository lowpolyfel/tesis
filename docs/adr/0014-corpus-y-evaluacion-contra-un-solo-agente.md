# 0014. Corpus con ground truth y evaluación contra un solo agente

- **Fecha:** 2026-10-06
- **Estado:** Aceptada. Las métricas son **exploratorias** (CONTEXTO §9); el corpus
  de la tesis y su ground truth **todavía no existen**: el del repositorio es un
  ejemplo del formato.

## Contexto

CONTEXTO §9 promete una "evaluación empírica [...] comparando el consenso de los
agentes contra la interpretación de un solo agente", y §11 pone el corpus primero:
15 a 25 requisitos construidos a propósito, con el ground truth **en un archivo
separado** para que no se filtre a los agentes, e incluyendo casos sin ambigüedad
(son los que revelan si el umbral dispara de más). La calibración (ADR 0013) ya
espera de este módulo un contrato fijo: etiquetas `{req_id, termino, ambiguo,
tipo_ambiguedad}` en la colección `evaluaciones`.

Había que decidir el formato del corpus, qué es la "línea base de un solo agente",
en qué punto del grafo se mide el sistema, cómo se emparejan los términos del
sistema con los del ground truth y qué se cuenta como acierto.

## Decisión

1. **Formato** (`data/corpus/README.md`): un directorio por corpus en
   `CORPUS_DIR/<nombre>/` con `requisitos.jsonl` (`{id, texto}`, lo único que llega
   a los agentes), `ground_truth.jsonl` (`{id, ambiguo, terminos[{termino,
   tipo_ambiguedad, interpretaciones_validas, interpretacion_esperada}], vaguedad,
   regionales, notas}`) y `corpus.json` opcional (`descripcion`, `ejemplo`,
   `autoria`, `validado_por`). El cargador (`app/evaluacion/corpus.py`) valida cada
   línea con Pydantic (`extra="forbid"`), que los ids coincidan entre los dos
   archivos y que el ground truth sea coherente: `ambiguo` si y solo si hay
   términos, al menos dos interpretaciones válidas distintas, la esperada entre las
   válidas, sin términos repetidos y ningún término a la vez en `terminos` y en
   `vaguedad`. Reporta **todos** los errores juntos, con archivo, línea e id.
   Avisa (sin rechazar) si un término no aparece tal cual en el texto o si no hay
   casos sin ambigüedad. Acepta UTF-8 con o sin BOM. La vaguedad no es ambigüedad
   (CONTEXTO §6): va en su propia lista y un requisito solo vago tiene
   `ambiguo: false`. Las interpretaciones distintas y la separación de la vaguedad
   se revisan en el cargador y no en el modelo del ground truth, para que una regla
   nueva no invalide las copias ya guardadas en evaluaciones anteriores.
2. **Corpus de ejemplo** en `data/corpus/ejemplo/` (7 requisitos: sin ambigüedad,
   léxica *sesión*, regional *jalar* con vaguedad *ahorita*, anafórica *su
   historial*, alcance *todos … no* y vaguedad sola *rápido*). Está marcado como
   EJEMPLO en `corpus.json`, en cada `notas` y en el README, y la evaluación lo
   advierte. Lo escribió el asistente de código para mostrar el formato: no es el
   corpus de la tesis, nadie lo validó y sus resultados no se reportan.
3. **Línea base de un solo agente** (`agente_unico_v1`, cliente
   `AGENTE_UNICO_MODEL`): una llamada por requisito, sin Extractor, sin filtros,
   sin detectores, sin divergencia ni debate. Devuelve `{ambiguo, terminos[{termino,
   tipo_ambiguedad, interpretacion_elegida}]}` con salida estructurada (`generar`,
   un reintento). Usa **la misma taxonomía y el mismo límite de palabras** que el
   Clasificador (`clasificador_v2`, `SIGNIFICADO_MAX_PALABRAS`), para que la
   diferencia medida sea la arquitectura y no el prompt. La plantilla solo tiene
   las variables `texto` y `max_palabras`: el ground truth no tiene por dónde
   entrar (hay una prueba que lo verifica con marcas en el ground truth).
4. **Corrida** (`POST /evaluaciones {corpus, nombre?}` → 202): crea un proyecto
   `tipo: evaluacion` (LEL vacío), encola los requisitos como un lote con
   `origen = {archivo: "corpus:<nombre>", marca: <id>, indice}` y encola la línea
   base por requisito en la prioridad `analisis` de la cola (ADR 0008), así que
   corre después de los grafos y con el mismo texto que recibió el sistema. Un
   último trabajo cierra la evaluación. El documento en `evaluaciones` guarda
   `config` (`config_traza()` más modelo y prompt del agente único), `items`
   `[{id_corpus, req_id}]`, `linea_base` por id (resultado o error, modelo,
   prompt), **una copia del ground truth** y la `huella` (sha256) del corpus.
   Con la copia, la evaluación se mide siempre contra el ground truth con el que se
   creó; si el corpus cambia o desaparece, la respuesta lo avisa y para medir con
   el nuevo se crea otra evaluación.
5. **Se mide lo que el sistema propone, sin validación humana:** el requisito
   cuenta como listo en `pendiente_validacion` o en un estado terminal (`error`
   incluido). Se lee de la traza: la última clasificación (un nodo reejecutado
   repite mensajes, ADR 0008), el filtrado, la similitud inicial, la vía y la
   propuesta de la `solicitud_validacion`.
6. **Emparejamiento de términos**, uno a uno y del criterio más fuerte al más débil
   (`app/evaluacion/emparejamiento.py`): (a) **exacto**: las mismas palabras tras
   normalizar (minúsculas, sin acentos ni puntuación); (b) **contención**: las
   palabras de uno aparecen seguidas dentro del otro, palabra por palabra (*su* y
   *su historial*; *usuarios* y *todos los usuarios*; nunca por subcadena: *su* no
   está en *usuario*); (c) **lema**: el mismo conjunto, no vacío, de lemas de
   contenido según spaCy (*sesiones* y *sesión*). Primero se toman todos los pares
   exactos, luego los de contención y al final los de lema, en orden de aparición.
   Cada par informa su criterio. En las etiquetas (punto 8), dentro de cada
   criterio van primero los candidatos con interpretaciones.
7. **Métricas** (`GET /evaluaciones/{id}`), calculadas al vuelo, por requisito y en
   resumen para los dos lados:
   - `deteccion` por término (vp, fp, fn, precisión, exhaustividad, F1; `null` con
     denominador cero). Lo esperado es todo lo que marca el ground truth (términos
     ambiguos, vaguedad y regionales, sin repetir). Un término del sistema cuenta
     como detectado si tuvo interpretaciones, o si los filtros lo marcaron como
     vaguedad o regional **y** el ground truth lo lista en `vaguedad` o en
     `regionales`; uno de la línea base, si lo devolvió. Como con el tipo de
     ambigüedad, la clase no decide la detección: *ahorita* está en el catálogo de
     vaguedad y el ground truth puede listarlo como regional (CONTEXTO §6 lo
     clasifica como mexicanismo); la fila muestra las dos clases.
   - `deteccion_ambiguedad`: lo mismo solo con términos ambiguos (los del
     Clasificador con interpretaciones; todos los de la línea base). Es la
     comparación del núcleo.
   - `requisito`: ambiguo sí/no contra el ground truth (vp, fp, vn, fn,
     `sin_decision`, exactitud). Para el sistema, ambiguo = algún término con
     interpretaciones (la opinión del Clasificador, no el debate). La exactitud
     divide entre todos los requisitos listos de ese lado: un `sin_decision`
     cuenta como fallo.
   - `tipo`: exactitud del tipo de ambigüedad en los pares emparejados con un
     término ambiguo del ground truth.
   - Solo del sistema: `debates` por requisito (`en_debate` contra `ambiguo`):
     activados, necesarios, justificados, de más y faltantes; y `vias` por término
     con interpretaciones (aceptado directo, consenso, arbitraje, sin vía).
   - Errores. En la línea base, una falla cuenta como `sin_decision` y sin
     términos detectados. En el sistema depende de dónde falló: **antes** de la
     clasificación cuenta como `sin_decision`, sin debate (si el ground truth es
     ambiguo es un debate faltante) y de sus términos solo cuenta lo que ya habían
     marcado los filtros; **después** de la clasificación cuenta lo que propuso el
     Clasificador (ambiguo sí/no, detección y tipo), y los términos que no
     terminaron el debate quedan `sin_via`. Los dos casos se cuentan en `errores`
     y el informe los avisa por separado.
   - La interpretación elegida **no se califica**: se muestra junto a la esperada
     del ground truth para revisarla a mano.
8. **Etiquetas para la calibración** (contrato de ADR 0013): una por candidato del
   Clasificador, con el término **como lo escribió el sistema** (así la
   calibración lo encuentra entre sus similitudes), ambiguo si se emparejó con un
   término ambiguo del ground truth y con su tipo; más una por término ambiguo del
   ground truth que no se emparejó con ningún candidato. Dentro de cada criterio de
   emparejamiento se prefieren los candidatos con interpretaciones, que son los que
   tienen similitud: un unívoco (*historial*) no le quita el término del ground
   truth (*historial de compras de su cliente*) al que se debatió (*su cliente*);
   si el unívoco coincide exacto, sí se lo queda (el Clasificador vio el término y
   no le encontró ambigüedad). La vaguedad y los regionales no ambiguos no
   generan etiqueta. Solo se escriben para requisitos que el sistema ya terminó.
   Se recalculan bajo un candado al terminar cada trabajo de la evaluación y en
   cada `GET /evaluaciones/{id}`, que escribe el documento solo si algo cambió.
   La evaluación termina cuando los dos lados están listos; una traza que no
   existe (las trazas se crean antes que el documento, así que no va a llegar) no
   detiene el cierre y el informe la avisa. Una evaluación `terminada` no vuelve
   atrás.
9. **Rutas:** `POST /evaluaciones` (404 corpus inexistente, 422 corpus inválido con
   la lista de errores, 503 sin cliente del agente único), `GET /evaluaciones`
   (la más reciente primero, con progreso), `GET /evaluaciones/{id}`,
   `GET /corpus` (los inválidos se listan con sus errores) y `GET /corpus/{nombre}`
   (requisitos con su ground truth, para la pantalla Corpus). Formas en
   `app/evaluacion/formas.py`.

## Alternativas consideradas

- **Ground truth en el mismo archivo que los requisitos:** más cómodo de editar,
  pero cualquier cambio en el código que lea el archivo podría mandarlo a un
  prompt. Separado, el único lector es el módulo de métricas.
- **Medir después de la validación humana:** mediría al sistema más la persona y
  pediría 15–25 validaciones por corrida. Lo que se compara es el consenso de los
  agentes contra un agente solo, antes del punto de revisión.
- **Usar como línea base la primera interpretación del Clasificador (ablación sin
  debate):** no cuesta llamadas extra, pero conserva el Extractor, los filtros y los
  detectores, y el Clasificador no está hecho para elegir. CONTEXTO pide un solo
  agente. Queda como experimento complementario posible, con las mismas métricas.
- **Darle a la línea base los catálogos de vaguedad y regionales:** dejaría de ser
  un solo agente. En su lugar se reportan dos detecciones: la que incluye lo que
  aportan los catálogos y la que solo cuenta ambigüedad.
- **Emparejar términos e interpretaciones por similitud de embeddings:** agrega otro
  umbral que calibrar con el mismo corpus que se evalúa. El emparejamiento literal
  es explicable caso por caso y cada par dice su criterio.
- **Un juez LLM que califique la interpretación elegida:** sería otro modelo sin
  validar decidiendo el resultado de la evaluación. Se deja a revisión humana.
- **Guardar las métricas al terminar:** se calculan al vuelo desde datos crudos
  (trazas, copia del ground truth y línea base) para poder corregir una fórmula sin
  volver a llamar a los LLM; solo las etiquetas se guardan, porque son el contrato
  con la calibración.

## Consecuencias

- **Corpus pendiente.** El corpus real (15–25 requisitos, con casos sin
  ambigüedad) y su ground truth los construye la tesista y, de preferencia, los
  revisa otra persona (`validado_por`). Con un solo anotador no hay acuerdo entre
  anotadores que reportar; si se consiguen dos, conviene medirlo (kappa) antes de
  evaluar.
- **Calibrar y evaluar con el mismo corpus** es una limitación que la tesis debe
  declarar (ADR 0013). Con 15–25 casos, un caso mueve las proporciones varios
  puntos: los números son exploratorios.
- **Ejemplos compartidos con los prompts.** `clasificador_v2` y `agente_unico_v1`
  usan como ejemplos *sesión*, *todos los usuarios no deben…* y *su cuenta*, los
  mismos casos del corpus de ejemplo. El corpus real debería evitar los ejemplos de
  los prompts o reportarlos aparte.
- **El emparejamiento es literal.** Escribir en el ground truth un término distinto
  de como aparece en el texto (*jalar* cuando el texto dice *jale*) lo deja sin
  pareja: el lematizador de `es_core_news_sm` falla justo con las formas
  regionales (ADR 0003). El cargador lo avisa. La contención puede emparejar un
  término con otro de distinta naturaleza (*usuarios* léxico con *todos los
  usuarios* de alcance); el tipo lo deja ver. El emparejamiento es voraz, no un
  emparejamiento máximo.
- **La línea base no tiene catálogos.** En `deteccion` el sistema tiene ventaja por
  diseño (vaguedad y regionales); la comparación del núcleo es
  `deteccion_ambiguedad`. Una vaguedad o un regional que el ground truth no lista
  no cuenta como falso positivo del sistema.
- **Debates faltantes no siempre son errores.** El ground truth dice si hay
  ambigüedad, no si es nociva o inocua (Chantree et al.): un término ambiguo con
  interpretaciones cercanas se acepta directo por diseño.
- **Modelos.** Si `AGENTE_UNICO_MODEL` no es el modelo de los agentes, la diferencia
  mezcla arquitectura y modelo; `config` registra ambos. Una corrida es una
  muestra: la variación de los LLM se ve repitiendo la evaluación (cada corrida es
  otro proyecto).
- **Escrituras al consultar.** `GET /evaluaciones/{id}` puede escribir el documento
  (etiquetas y estado) para que la calibración no dependa de que alguien lo
  consulte; el candado es de proceso, como la cola (un solo servidor).
- **Interferencia humana.** Si alguien valida requisitos del proyecto de evaluación
  mientras corre, el LEL del proyecto afecta a los siguientes; la respuesta lo
  avisa cuando hay términos `resuelto_por_lel`. Un reproceso crea otra traza que la
  evaluación no sigue.
- **Reinicio.** La cola vive en memoria: tras un reinicio se pierde la línea base
  que faltaba. Al arrancar la API, el `lifespan` del router de evaluaciones llama
  a `evaluacion.recuperar(servicio)` (después de `servicio.iniciar()`, que retoma
  los grafos), y la vuelve a encolar con el cierre, como hace comparaciones.
  Además, `GET /evaluaciones/{id}` lo suple si el servicio se armó sin ese
  arranque (scripts, pruebas): si falta línea base y ningún trabajo de esa
  evaluación está en la cola, la vuelve a encolar. Esa consulta, además de
  escribir el documento, puede encolar trabajo (que no repite llamadas: lo que ya
  tiene resultado se salta).
- **Cola.** La línea base va en la prioridad `analisis`: un corpus grande retrasa
  las comparaciones de otros proyectos, y requisitos nuevos de otros proyectos se
  adelantan a la línea base.
