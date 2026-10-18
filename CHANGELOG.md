# Cambios

## 2.4.0 — 2026-10-18

El aparato de evaluación, rehecho para documentar (ADR 0029). No cambia los agentes, el grafo de la
entrevista ni las etapas del pipeline.

- **Calidad en lugar de aprobación.** La revisión humana ya no es un ✓/✗ que mezclaba detección y
  redacción. Son tres criterios binarios por salida: fidelidad, delimitación e intención. En los
  términos ambiguos se marca además la cobertura de las lecturas esperadas, a mano y sin embeddings.
  La rúbrica, con un ejemplo de qué pasa y qué no pasa por criterio, está en
  `docs/rubrica-revision.md`, en la pantalla y en el paquete.
- **A ciegas y con teclado.** La revisión oculta proveedor y modelo por omisión, y baraja los ítems
  y, dentro de cada ítem, los modelos. Guarda la semilla y el orden, para que la revisión sea
  reconstruible. Se usa con `1 2 3`, `4 5 6`, `Enter`, `Backspace` y `?`, y se retoma donde quedó.
- **Métricas que separan modelos.**
  - McNemar exacta sobre la detección y sobre cada criterio, en este caso solo con el mismo número
    de intenciones; los ítems excluidos se cuentan.
  - Subenumeración: con tres lecturas esperadas, ¿cuántas intenciones dio el modelo?
  - Modos de falla de los falsos negativos, con «documento contra el hecho que registra» precargado.
  - Estabilidad entre N corridas idénticas, con su rango.
- **Ids que no se reutilizan.** Borrar deja una lápida, cada prueba tiene `uid` y un código con su
  banco (`P05-v2-84c2d8`), y `python -m app.calibracion.verificar_ids` reporta las colisiones entre
  la base local y Mongo. Lo mismo vale para las corridas de calibración.
- **Ground truth de las entrevistas.** El etiquetado es por persona, a ciegas de la similitud y de la
  decisión, con orden barajado, teclado (`S` sí, `N` no, `X` no sé) y solo los términos que llegaron
  a la divergencia. Con dos personas se usan los términos en que coinciden y se calcula la kappa de
  Cohen. Con etiquetas, la calibración da precisión, exhaustividad, F1, la ROC con su banda bootstrap
  y los intervalos, sin cambiar la configuración. Sigue siendo de solo lectura.
- **Paquetes para Overleaf.** Los dos compilan con pdfLaTeX y con XeLaTeX, verificado con TeX Live
  en las pruebas. La prueba de modelos suma ocho figuras: confusión, detección, calidad, cobertura,
  parejas, latencia, modos y subenumeración, y estabilidad si la prueba es parte de una serie.
  La calibración suma la ROC con banda y el acuerdo entre personas. Cada pieza lee de un CSV, explica
  qué mide y pone `---` con un aviso cuando falta algo.
- **Las corridas viejas no se migran.** La aprobación de la v2.3 se conserva tal cual y se reporta
  aparte, con su criterio. Las pruebas sin uid se identifican por su código. Las corridas de
  calibración se siguen reproduciendo igual. Detalle en ADR 0029, «Consecuencias».

## 2.3.1 — 2026-10-18

La prueba de modelos, con controles negativos y revisión a ciegas (ADR 0028).

- **Banco v2 con 23 controles inequívocos.** Trae los 50 ambiguos de v1 sin cambios y suma 23
  términos de dominio con una sola lectura: 10 inequívocos de dominio («contraseña»,
  «kilometraje»…) y 13 sustantivos genéricos de negocio («paciente», «recibo», «caja
  registradora»…). Veinte de los controles van en pareja con un ambiguo del mismo dominio. El
  banco v1 no se toca, así que las pruebas viejas siguen correspondiendo a su banco.
- **Precisión y falsas alarmas.** Con los controles, la prueba mide además de la exhaustividad
  la tasa de falsas alarmas, la precisión, la matriz de confusión y las parejas (en cuántas
  marcó el ambiguo y no su control). Un modelo que marcara todo como ambiguo ya no sale perfecto.
  Todo va con intervalos de Wilson, en la pantalla, en la gráfica y en el paquete para Overleaf.
- **Revisión a ciegas de verdad.** Con los nombres ocultos, las letras de los modelos y el orden
  de los términos se barajan, y los avisos no nombran modelos. «Rehacer la revisión» borra las
  marcas para repetirla a ciegas.
- Se elige la versión del banco al crear una prueba; cada prueba se mide con la suya.

## 2.3.0 — 2026-10-18

Prueba de modelos con un banco de 50 términos ambiguos y revisión humana (ADR 0027).

- **Banco de términos.** 50 términos ambiguos del español de México (31 de polisemia y 19
  regionalismos), cada uno con su dominio, la cita de entrevista donde aparece y las lecturas
  esperadas. Va versionado y se cita por su huella.
- **Pruebas a elegir.** En Calibración → «Modelos · banco de términos» se eligen de 1 a 8
  modelos (Ollama y los proveedores con clave guardada: Gemini, OpenAI, Claude, Groq…) y los
  términos (todos, una clase o una prueba rápida de 10). El Clasificador real corre con cada
  modelo en segundo plano. Se puede cancelar, reanudar y reintentar los errores.
- **Revisión humana.** Una tabla con el término y sus lecturas esperadas, lo que respondió el
  modelo y una tercera columna para marcar ✓ / ✗ si hizo un buen trabajo. Se puede revisar sin
  ver los nombres de los modelos.
- **Medidas.**
  - Detección y aprobación por modelo y por clase, con intervalos de Wilson al 95 %.
  - Errores, reintentos y latencia.
  - Prueba exacta de McNemar entre cada par de modelos.
- **Gráfica y Overleaf.** La gráfica usa el mismo sistema visual que el resto de la calibración.
  El paquete para LaTeX trae la figura en pgfplots, las tablas booktabs, el banco y las
  respuestas.

## 2.2.0 — 2026-10-18

La calibración, sobre las entrevistas y lista para la tesis (ADR 0026).

- **Ground truth de las entrevistas.** En cada entrevista se marca qué términos son ambiguos y
  de qué tipo, a ciegas por omisión (sin ver la similitud del sistema), con anotador y fecha.
- **Medidas más sólidas.**
  - Curva ROC y AUC: cuánto separa la similitud lo ambiguo de lo que no lo es, sin elegir umbral.
  - Intervalos bootstrap al 95 % con semilla fija, para el AUC y para la precisión, la
    exhaustividad y el F1.
  - Matriz de confusión y desglose por tipo de ambigüedad.
  - Avisos de muestra chica, de clases desbalanceadas y de etiquetas hechas viendo al sistema.
- **Corridas guardadas.** Cada corrida congela los resultados con su fecha, la configuración, la
  versión y una huella de las similitudes y etiquetas de cada entrevista: es la evidencia citable.
- **Paquete para Overleaf.** Figuras en pgfplots, tablas en booktabs, datos CSV y la corrida en
  JSON, con un `main.tex` que compila.
- **Gráficas consistentes.** Un solo marco y una paleta validada para daltonismo. El color
  significa lo mismo en todas (naranja = ambiguo / a debate, azul = no ambiguo / directo) y el
  texto mide lo mismo en todas. Cada gráfica se descarga en SVG.
- La pantalla deja de usar las trazas de requisitos v1. Sus rutas en la API se conservan.

## 2.1.0 — 2026-10-15

La escena con cuatro esferas como máximo y una interfaz sin lag (ADR 0025).

- **La escena, simplificada.** Antes salía una esfera por agente, una por intención y una
  partícula por mensaje (hasta 37). Ahora son cuatro como máximo: el sistema; el agente que
  tiene el turno, que viaja por las estaciones del flujo (Entrevista, Intención, Discusión,
  Léxico) con el tono y el nombre de quien habla; y las dos intenciones más distintas del
  término en debate, que se acercan o alejan según su similitud. Un riel de texto nombra las
  estaciones. Igual en la escena del análisis de la versión 1.
- **Las esferas ya no traban la página.**
  - Las ondas se dibujan en un lienzo desde un worker.
  - El color del fondo cambia sin recalcular toda la página.
  - Pasar el cursor por el camino de fases solo cambia el color de la esfera.
  - Las esferas del menú nacen chicas.
  - Con la CPU limitada a 4×, la escena pasó de 3 a 48 fps; el menú, de 68 a 24 ms por
    cuadro; una sección en reposo, de 17 a 6 ms.
- **Entrar al mapa ya no congela la pantalla.** El diagrama de «Exportar» se dibuja al
  abrirlo.
- **Las páginas:** un solo sondeo de las fases, recargas silenciosas, caché al cambiar de
  fase y menos renders en el léxico y en el editor del mapa.

## 2.0.0 — 2026-10-13

De la entrevista a los requisitos (ADR 0024).

- **Entrada nueva: la entrevista.** Texto pegado, PDF con texto o .txt, leída por turnos y
  hablantes, con vista previa antes de enviarla. Varias entrevistas por proyecto.
- **LEL interactivo.** Un grafo nuevo procesa la entrevista completa: el Revisor la anota,
  el Extractor separa los términos, los filtros los cruzan con la memoria del proyecto, el
  Clasificador propone la intención de cada uno, la divergencia y el Crítico debaten las
  que divergen y el Modelador escribe el LEL. La persona experta valida, corrige, elige otra
  intención, descarta o agrega términos.
- **El sistema aprende.** Lo que la persona corrige, confirma entre varias intenciones o
  descarta queda como acuerdo del proyecto: resuelve el término en las entrevistas
  siguientes y lo reciben los agentes en todas las fases. Se puede olvidar.
- **Mapa conceptual con propósito**, editable sobre el propio mapa (React Flow) y validable
  por componente; se exporta como Mermaid, PNG o SVG.
- **Metas en tres niveles**: de la organización, estratégicas y específicas.
- **Requisitos** funcionales y no funcionales con trazabilidad a metas, LEL y entrevista,
  avisos de lo que conviene revisar y la especificación completa en Markdown.
- **Fases con compuertas**: cada una se abre cuando la anterior quedó validada; si cambia lo
  de atrás, lo de adelante se marca para volver a generar o conservar.
- **Las esferas** en cada fase: reciben la entrevista, la procesan en escena, absorben lo que
  la persona valida y dicen qué aprendió el sistema.
- La versión 1 (requisitos escritos, uno por uno) se conserva en `/proyectos/:id/v1` y en «Más».
