# 0029. Calidad con criterios binarios a ciegas, métricas pareadas y ground truth por varias personas

- **Fecha:** 2026-10-18
- **Estado:** Aceptada (rehace la revisión de ADR 0027 y 0028 y completa la calibración de ADR 0026). La revisión fuera del sistema, por persona o IA, la agrega ADR 0030.

## Contexto

### Prueba de modelos (ADR 0027 y 0028)

1. **La aprobación mezclaba dos preguntas.** La revisión guardaba un solo ✓/✗ por salida (`bueno`) y
   el resumen lo reportaba como «aprobación». Mezclaba si el modelo acertó al decidir que el término
   era ambiguo con si lo que escribió estaba bien escrito. El resultado se leía mal: un modelo podía
   tener 0.97 de aprobación y 0.00 de detección, porque se juzgaba la calidad de la única lectura que
   dio. La detección ya se mide sola contra el banco.
2. **McNemar se corría sobre la aprobación, que estaba saturada**, y daba p = 0.500. Donde sí había
   una diferencia (la detección, 34 contra 0 pares discordantes) no se calculaba.
3. **La revisión a ciegas era opcional.** Los nombres se veían por omisión, el orden no se guardaba
   y el propio resumen avisaba que se había revisado viendo los modelos.
4. **Faltaban medidas para leer las fallas:**
   - la estabilidad entre corridas idénticas (con temperatura 0 y semilla 42 la misma configuración
     dio 33 y 34 detecciones);
   - los modos de falla de los falsos negativos (10 de 11 fallas de polisemia eran «documento contra
     el hecho que registra»);
   - la subenumeración (de 10 ítems con tres lecturas, solo 1 recibió tres intenciones);
   - la cobertura de las lecturas esperadas.
5. **Los ids se reutilizaban.** `crear_doc` toma el número siguiente al mayor que existe: al borrar
   P01 y crear otra prueba, salía P01 de nuevo. Así quedaron dos pruebas distintas (banco v1 y v2) con
   el mismo id. Lo mismo pasaba con las corridas de calibración.

### Calibración (ADR 0026)

Sin etiquetas, la calibración no podía dar precisión, exhaustividad, F1 ni ROC: `n_etiquetas` salía
en 0 y la rejilla en `nan`. El etiquetado tenía otros cuatro problemas:

- era un documento por entrevista (una sola persona);
- usaba casillas, sin teclado ni orden barajado ni «no sé»;
- listaba todos los términos del Extractor, no solo los que llegaron a la divergencia;
- no había forma de medir el acuerdo entre dos personas.

## Decisión

### 1. Calidad: tres criterios booleanos por salida (`calidad.py`, `rubrica.py`)

La revisión humana mide solo la factura de lo que el modelo escribió, con tres criterios
independientes:

- **fidelidad**: la paráfrasis dice lo que decía la cita, sin agregar ni quitar información;
- **delimitación**: el significado está acotado y no es circular;
- **intención**: dice para qué se usa el término, no vuelve a decir qué significa.

En los términos ambiguos, además, la persona marca qué **lecturas esperadas** del banco aparecen en
la salida. La **cobertura** es cubiertas sobre esperadas, por ítem y agregada. Se coteja a mano
contra la referencia escrita, **sin similitud de embeddings**: el proyecto ya tiene un umbral que
defender y no conviene introducir un segundo.

**Granularidad: una marca por salida** (un término de un modelo). Un criterio se cumple si lo
cumplen todas las intenciones de la salida. Así cada salida es una observación pareable entre
modelos (McNemar por ítem) y basta una tecla por criterio. Por intención, el número de
observaciones cambiaría de un modelo a otro y no se podrían parear.

En el resumen y en las tablas, la medida se llama `calidad`, con sus tres sub-llaves. Cada una lleva
su intervalo de Wilson sobre las salidas revisadas.

### 2. La revisión vieja no se traduce ni se borra

La revisión v2.3 (`revisiones_modelos`, campo `bueno`) se queda como está:

- se reporta aparte, como «aprobación (criterio v2.3)»;
- ya no se puede escribir;
- «Rehacer la revisión» borra solo la revisión nueva.

No se rellena hacia atrás: un `bueno: true` no dice cuál de los tres criterios se cumplió. La
revisión nueva se hace sobre las salidas ya guardadas, sin volver a correr los modelos, así que la
detección, la precisión y las falsas alarmas no cambian y no se gasta API.

### 3. A ciegas por omisión y reconstruible (`revisiones_calidad`)

- Durante la revisión no se muestran el proveedor ni el modelo.
- El servidor baraja los ítems y, dentro de cada ítem, los modelos, con una semilla aleatoria.
- Guarda `a_ciegas`, la semilla, el orden resultante y las letras de los modelos.
- Revisar con los nombres a la vista es una opción explícita al empezar, y el resumen lo avisa.
- Si después se reintentan errores, las salidas nuevas se agregan al final con una semilla derivada:
  lo ya revisado no cambia de lugar.

La pantalla es para el teclado:

- `1`, `2` y `3` alternan los criterios;
- `4`, `5` y `6` marcan las lecturas;
- `Enter` guarda y avanza;
- `Backspace` regresa;
- `?` abre la rúbrica en un panel lateral.

Cada salida se guarda al avanzar: se puede dejar a medias y retomar.

### 4. Métricas pareadas y de diagnóstico

- **McNemar exacta sobre la detección**, en los ítems ambiguos. Un error cuenta como no detectado,
  igual que en la exhaustividad.
- **McNemar exacta sobre cada criterio por separado**, solo en los ítems revisados en los dos
  modelos y con **el mismo número de intenciones**: juzgar una lectura contra dos no es la misma
  cantidad en los dos lados. Los ítems excluidos por eso se reportan.
- **Subenumeración**: de los ítems con tres lecturas esperadas, cuántos se marcaron ambiguos y
  cuántos recibieron tres intenciones o más. La divergencia es el coseno mínimo entre paráfrasis: si
  la lectura más alejada nunca se genera, el mínimo sube y un ambiguo puede pasar el umbral.
- **Modos de falla** de los falsos negativos: un campo editable por ítem y modelo (`modos_falla`),
  con un catálogo corto que trae precargado «documento contra el hecho que registra». Una salida no
  válida se sugiere como «falla de formato».
- **Estabilidad**: `repeticiones` al crear la prueba, o «repetir», crean una **serie** de corridas
  idénticas que se ejecutan una tras otra. El resumen de la serie da la detección por corrida y por
  clase, y su rango.

### 5. Identidad de las corridas

- **Borrar deja una lápida** (`borrada: true`, con id, uid, código y banco). Como `crear_doc` toma el
  número siguiente al mayor que existe, un número nunca vuelve a usarse. Esto vale para las pruebas
  de modelos y para las corridas de calibración.
- Cada prueba nueva lleva un **`uid`** (uuid4) y un **`codigo`** citable con la versión y la huella
  corta de su banco (`P05-v2-84c2d8`). El código es el nombre del zip y el título del paquete.
- **`python -m app.calibracion.verificar_ids`** compara la base JSON local y Mongo, sin escribir nada,
  y reporta tres cosas: los ids repetidos con otro contenido, las pruebas sin uid y las que tienen un
  banco con otra huella.

### 6. Etiquetado de entrevistas por varias personas (`anotaciones.py`, `etiquetas_anotadores`)

- **Un documento por entrevista y persona** (A01, A02…), con `anotador`, `a_ciegas`, semilla, orden
  barajado y una respuesta por término: **sí, no o no sé**.
- **Solo entran los términos que llegaron a la divergencia.**
- La pantalla muestra el término, sus citas y el contexto, **nunca la similitud ni la decisión**.
  Mientras alguien etiqueta, la página oculta también los resultados y las corridas.
- Teclas: `S` sí, `N` no, `X` no sé, `Backspace` regresa, `?` rúbrica. Se retoma donde quedó.
- **Ground truth consolidado**: cuenta el valor en el que coinciden todas las personas que
  contestaron sí o no. Un desacuerdo, o solo «no sé», deja el término fuera, y se cuenta.
- **Acuerdo**: kappa de Cohen entre cada par de personas, sobre los términos que las dos contestaron
  con sí o no.
- El documento único de la v2.2 se lee como el de una persona más.

### 7. La calibración sigue siendo de solo lectura

Con etiquetas, la calibración da sin cambiar nada de la configuración:

- precisión, exhaustividad y F1 en cada umbral de la rejilla;
- la ROC con su AUC;
- los intervalos bootstrap ya configurados;
- **una banda bootstrap de la ROC**: en cada tasa de falsos positivos, los percentiles de la tasa de
  verdaderos positivos, con la misma semilla.

La decisión usa la misma función de producción (`divergence.similitud.decidir`). No modifica el
umbral, no recalcula vectores, no consulta ningún LLM y no hay ninguna interfaz para mover el umbral
hasta que el corpus pase. Si la similitud no separa los casos, es un hallazgo.

### 8. Exportación

Se conserva la estructura de los dos paquetes: `LEEME.md`, `main.tex`, `estilo-dudamel.tex` con
`\dudameldir`, `figuras/*.tex` en pgfplots que leen `datos/*.csv`, `tablas/*.tex` con booktabs y
longtable, y el JSON completo. Sobre esa estructura:

- **`main.tex` compila con pdfLaTeX y con XeLaTeX.** Usa `iftex`: con pdfLaTeX carga inputenc, T1 y
  Latin Modern; con XeLaTeX, fontspec.
- **Una prueba compila los dos paquetes con los dos motores** cuando están instalados. En el entorno
  de desarrollo se verificó con TeX Live 2023.
- **Figuras nuevas de la prueba de modelos:**
  - matriz de confusión por modelo;
  - barras de exhaustividad, precisión y falsas alarmas con Wilson;
  - los tres criterios de calidad;
  - distribución de la cobertura;
  - parejas discriminadas;
  - latencia (mediana y p90);
  - modos de falla;
  - subenumeración;
  - estabilidad, si la prueba es parte de una serie.
- **Figuras y tablas nuevas de la calibración:** la ROC con su banda y la tabla de acuerdo (kappa).
  La distribución por clase se enciende sola cuando hay etiquetas.
- **Reglas en cada pieza:**
  - un comentario arriba que explica qué mide y cómo se calcula;
  - los números siempre salen de un `.csv`;
  - cada serie lleva también su trama o su marca, así que el color no es lo único que distingue;
  - el intervalo de Wilson siempre visible;
  - `---` cuando una métrica no se puede calcular, más un aviso de qué falta.
- Una figura sin datos no se genera, y `main.tex` dice cuál se omitió y por qué.
- La rúbrica va como `apendice/rubrica.tex` y `rubrica.md`.

## Alternativas consideradas

- **Una escala de 1 a 5 en lugar de criterios binarios.** Con una sola persona revisora, más
  granularidad es más ruido, y además se pierde McNemar.
- **Traducir las marcas viejas a los criterios nuevos.** Un ✓ no dice qué criterio se cumplió:
  inventarlo sería fabricar datos.
- **Cobertura automática por similitud de embeddings.** Introduciría un segundo umbral que habría que
  defender, sobre el mismo tipo de medida que se está evaluando.
- **Calificar cada intención por separado.** El número de observaciones dependería del modelo y no
  habría prueba pareada por ítem.
- **Un contador global de ids.** Las lápidas logran lo mismo sin otra colección, en Mongo y en JSON, y
  además dejan constancia de qué prueba tuvo cada número.
- **Ground truth por mayoría.** Con dos personas no hay mayoría. El acuerdo unánime es más estricto y
  los desacuerdos se reportan.

## Consecuencias

- **Corridas viejas que quedan con su criterio viejo**, sin migrar: son citables en la tesis y tienen
  que seguir reproduciéndose igual.
  - Las pruebas de la v2.3 que tengan revisión ✓/✗ (por ejemplo, la P01 del banco v1) conservan su
    `aprobacion` tal cual. Se muestra como «aprobación (criterio v2.3)» y no tiene `calidad` hasta que
    alguien haga la revisión nueva sobre sus mismas salidas.
  - Las pruebas creadas antes de la v2.4.0 no tienen `uid`. Su código se deriva del id, la versión y
    la huella del banco, y el verificador las lista.
  - Las corridas de calibración guardadas antes de la v2.4.0 no tienen banda ROC. Su paquete se genera
    igual que antes (más el preámbulo que también compila con XeLaTeX) y la huella de sus etiquetas
    se calcula igual.
  - Las dos pruebas que quedaron como P01 (bancos v1 y v2) no se renumeran: cambiar un id ya citado
    rompería la cita. Se distinguen por su código (`P01-v1-…` y `P01-v2-…`) y el verificador lo
    reporta.
- El error «significado tiene N palabras; el máximo es 12» con Ollama es el contrato del Clasificador
  (`SIGNIFICADO_MAX_PALABRAS`). No se toca aquí, porque esta versión no cambia los agentes. La prueba
  lo cuenta como no detectado y lo sugiere como «falla de formato».
- La rúbrica (`docs/rubrica-revision.md`) se genera desde `rubrica.py`, y una prueba falla si se
  desincroniza.
- La versión del sistema pasa a **2.4.0**.
