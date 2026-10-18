# 0026. Calibración sobre las entrevistas, con ground truth, ROC y corridas citables

- **Fecha:** 2026-10-18
- **Estado:** Aceptada (la pantalla de Calibración deja de usar las trazas de requisitos de la v1;
  ADR 0013 sigue vigente en su principio y en su API)

## Contexto

La calibración del ADR 0013 respondía qué habría decidido «similitud ≥ umbral» con otros
umbrales, sobre las trazas de los **requisitos** de la versión 1 y el ground truth del corpus
(ADR 0014). En la versión 2 (ADR 0024) la entrada son **entrevistas**, y la tesis se documenta
con ellas.

Una revisión de la tesis señaló además dos huecos:

- No había ningún resultado de calibración guardado. La salida se calculaba al vuelo, así que
  no quedaba evidencia que citar.
- Con un corpus de unas decenas de términos, una sola proporción (precisión, F1) en un solo
  umbral no basta: hace falta saber cuánto separa la similitud los casos **sin elegir umbral**
  y con qué incertidumbre.

## Decisión

### 1. Las similitudes salen de las entrevistas (`app/calibracion/entrevistas.py`)

De la bitácora de cada entrevista terminada (última corrida), por término, se toma el mensaje
`similitud` de ronda 0 con valor no nulo. Si un nodo se repitió tras una caída, cuenta el
último mensaje. La vía final sale de los mensajes posteriores (`consenso`, `arbitraje`) o de
la propia decisión (aceptado directo). Cada valor guarda además:

- el umbral con que se decidió;
- el modelo de embeddings;
- el modelo del Clasificador;
- el tipo de ambigüedad que propuso el Clasificador.

### 2. Ground truth por entrevista, a ciegas (`etiquetas_entrevista`)

La persona anotadora marca, por entrevista, qué términos son ambiguos y de qué tipo
(`PUT /entrevistas/{id}/etiquetas`). Por omisión etiqueta **a ciegas**: la interfaz no
muestra la similitud ni la decisión del sistema. Si las pide (`?sistema=true` en la API,
«ver al sistema» en la pantalla), lo que guarde queda marcado `a_ciegas: false`, y el
informe avisa que el ground truth puede estar sesgado hacia el sistema.

Las etiquetas:

- llevan anotador y fecha;
- se emparejan por entrevista y término normalizado, de forma literal, como en ADR 0014;
- pueden incluir términos que el Extractor no encontró. Esos aparecen como «etiquetas sin
  similitud»: ningún umbral puede corregirlos.

### 3. Medidas (`app/calibracion/estadistica.py`)

Sigue siendo positivo «a debate» (similitud < umbral) contra la verdad «ambiguo». Las medidas
son:

- **Rejilla:** directos y debates por umbral, como en ADR 0013, más la precisión, la
  exhaustividad y el F1 en cada umbral.
- **Matriz de confusión:** con el umbral configurado.
- **Curva ROC y AUC (Mann–Whitney, los empates cuentan la mitad):** cuánto separa la
  similitud los casos sin elegir ningún umbral. 0.5 es el azar y 1 es la separación
  perfecta.
- **Intervalos bootstrap percentil al 95 %:** para el AUC y para la precisión, la
  exhaustividad y el F1 en el umbral configurado. El remuestreo es de los pares con
  reemplazo, con `CALIBRACION_BOOTSTRAP` remuestreos (2000) y la semilla fija
  `CALIBRACION_SEMILLA`, así que los mismos datos dan los mismos intervalos.
- **Desglose por tipo de ambigüedad:** con el tipo de la etiqueta.
- **Avisos:**
  - muestra chica (menos de 20 pares);
  - clases desbalanceadas;
  - modelos de embeddings mezclados;
  - términos decididos con otro umbral;
  - ningún umbral separa los casos (es un hallazgo);
  - etiquetas hechas viendo al sistema.

**Nada elige ni recomienda un umbral.** El umbral se cambia a mano en `.env`, como en
ADR 0013.

### 4. Corridas guardadas (`calibraciones`)

`POST /proyectos/{id}/calibraciones` congela el informe de ese momento en una corrida
(C01, C02…). La corrida guarda:

- la fecha y una nota;
- la versión de la app;
- la configuración: umbral, rondas, rejilla, remuestreos, semilla y modelo de embeddings
  configurado;
- por entrevista, una **huella** (sha256) de sus similitudes y de sus etiquetas.

Las corridas se listan, se comparan por su resumen (AUC y F1 con sus intervalos), se ven
completas y se borran. Una corrida no se recalcula: es la evidencia tal como estaba. Si los
datos cambian después, la corrida nueva lleva otras huellas.

### 5. Paquete para Overleaf (`app/calibracion/latex.py`)

`GET /calibraciones/{id}/overleaf.zip` entrega:

- `main.tex`, que compila con pdfLaTeX;
- `estilo-dudamel.tex`, el preámbulo común: pgfplots y booktabs, los colores de la app y
  un estilo por serie;
- las figuras como código pgfplots (distribución por clase, precisión, exhaustividad y F1
  por umbral, ROC y debates por umbral). Son vectoriales, usan la tipografía del documento
  y leen sus números de `datos/*.csv`;
- las tablas con booktabs (métricas con intervalos, matriz de confusión, por tipo, rejilla
  y los valores en `longtable`);
- `corrida.json` y un `LEEME.md`.

El texto de la persona se escapa para LaTeX. `\dudameldir` permite copiar el paquete dentro
de la tesis.

### 6. Un solo sistema visual (`components/calibracion/graficas.jsx`)

Todas las gráficas comparten:

- el marco: ejes, rejilla tenue, línea discontinua del umbral configurado, leyenda y rótulos
  directos;
- una paleta categórica validada para daltonismo en los dos temas;
- el significado del color: naranja = ambiguo / a debate, azul = no ambiguo / directo,
  aqua = F1, gris = sin etiqueta;
- el tamaño del texto: se dibujan al ancho real medido, así que el texto mide lo mismo en
  todas.

Al pasar el cursor se lee el valor exacto, y cada gráfica se descarga en SVG con los colores
resueltos. En pgfplots cada serie tiene además su propio trazo, para leerse en blanco y negro.

## Justificación

- **La tesis se documenta con entrevistas.** La calibración debe medir el mecanismo sobre
  esa entrada.
- **AUC con intervalo** responde la pregunta de fondo («¿la similitud inicial separa lo
  ambiguo de lo que no lo es?») sin el grado de libertad de elegir un umbral. Es coherente
  con la regla de ADR 0013: si no separa, es un hallazgo.
- **El bootstrap con semilla fija** hace visible la incertidumbre de un corpus chico y es
  reproducible.
- **Las corridas con huellas** convierten un cálculo al vuelo en evidencia citable y
  verificable.
- **pgfplots en lugar de imágenes** da figuras con la tipografía y la escala del documento,
  editables en el propio LaTeX.

## Alternativas consideradas

- **Elegir el umbral que maximiza el F1:** se descarta como en ADR 0013, porque sería
  ajustar el umbral al mismo corpus con el que se evalúa.
- **Usar las decisiones de la persona experta en el LEL como ground truth:** mezclaría la
  validación con la referencia. La persona valida viendo al sistema, y el ground truth debe
  ser independiente.
- **Intervalos de Wilson para las proporciones:** el bootstrap cubre también el AUC y el
  F1, que no son proporciones simples, con un solo método.
- **Exportar las figuras como PDF o PNG prerrenderizados:** no siguen la tipografía del
  documento y no se pueden ajustar. El SVG de cada gráfica sigue disponible desde la
  pantalla.

## Consecuencias

- La pantalla de Calibración ya no muestra las trazas de requisitos v1. Las rutas
  `/calibracion` y `/proyectos/{id}/calibracion` del ADR 0013 se conservan en la API, con
  sus pruebas.
- El ground truth de entrevistas es nuevo. Hay que etiquetarlo, de preferencia a ciegas y
  revisado por una segunda persona, antes de citar resultados.
- Borrar una entrevista borra sus etiquetas. Las corridas guardadas no cambian: conservan lo
  que había.
- El paquete se validó por su estructura (llaves, entornos y archivos referidos) en las
  pruebas. No se compiló en el entorno de desarrollo, que no tiene una distribución TeX, así
  que la primera compilación en Overleaf es la verificación final.
- La versión del sistema pasa a **2.2.0**.
