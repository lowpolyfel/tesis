# Cambios

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
