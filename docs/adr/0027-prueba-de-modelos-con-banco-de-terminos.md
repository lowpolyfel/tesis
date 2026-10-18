# 0027. Prueba de modelos con un banco de términos ambiguos y revisión humana

- **Fecha:** 2026-10-18
- **Estado:** Aceptada (complementa ADR 0026: la pantalla de Calibración tiene ahora dos pestañas). El banco v1 no tiene controles negativos: ADR 0028 agrega el banco v2 con precisión y falsas alarmas.

## Contexto

El ADR 0021 deja elegir proveedor y modelo por agente: Ollama local, Google Gemini, OpenAI,
Anthropic, Groq, OpenRouter, DeepSeek, Mistral o cualquier servidor compatible. Para la tesis hace
falta saber **qué tan bien hace cada modelo el trabajo del Clasificador**: detectar que un término
es ambiguo y proponer sus interpretaciones.

La calibración del ADR 0026 no responde eso:

- mide el umbral de similitud, no al modelo;
- depende de las entrevistas que se hayan procesado, que cambian de un proyecto a otro, así que
  dos modelos no se comparan sobre la misma entrada.

## Decisión

### 1. Un banco fijo de 50 términos ambiguos (`app/calibracion/banco/ambiguedad_v1.json`)

Cada término trae:

- un id (B01…B50);
- su clase:
  - **polisemia** (31): varios sentidos dentro del mismo oficio, como «consulta» en una clínica;
  - **regionalismo** (19): español de trabajo en México que alguien de otra región u otro oficio
    puede leer distinto, como «checar», «la raya» o «ahorita»;
- el dominio y un contexto de proyecto de una línea;
- una cita de entrevista donde aparece;
- de 2 a 3 **lecturas esperadas**: la referencia de quien revisa.

El banco va versionado en el repositorio y se cita por su versión y su huella (sha256 de los
términos), que la API y cada prueba guardan. `GET /bancos/ambiguedad` lo devuelve.

Todos los términos son ambiguos. El banco mide si el modelo lo detecta y si sus interpretaciones
cubren las lecturas esperadas sin inventar. No mide falsos positivos, que siguen cubriendo el
ground truth de las entrevistas (ADR 0026) y el corpus (ADR 0014).

### 2. Se prueba el Clasificador real, un término por llamada (`app/calibracion/pruebas_modelos.py`)

Cada modelo corre `Clasificador.intenciones` con el prompt `clasificador_intencion_v1`, el mismo
que usa una entrevista:

- recibe la cita del término y el contexto de su dominio;
- no recibe LEL ni acuerdos;
- usa la temperatura y la semilla del `.env`.

Por cada respuesta se guarda:

- si respondió y cuántos intentos hizo (incluido el reintento de ADR 0001);
- si marcó el término como ambiguo (dos o más intenciones);
- el tipo;
- las intenciones;
- la latencia;
- el error, si falló.

Las credenciales salen de la cuenta: los proveedores con clave guardada en Configuración y Ollama
(con su URL o la del servidor). Las claves no se guardan en la prueba.

### 3. Corre en segundo plano, fuera de la cola de análisis

Una prueba de 50 términos con 3 modelos son 150 llamadas, y no debe bloquear las entrevistas.

- Corre en hilos propios: uno por proveedor. Dentro de un proveedor, los modelos van uno tras
  otro, para no cargar dos modelos de Ollama a la vez.
- El documento (`pruebas_modelos`, ids P01, P02…) se guarda tras cada término. La pantalla lo
  pide cada 2 s mientras corre.
- Se puede cancelar.
- Una prueba que quedó a medias por un reinicio se reporta como **interrumpida** y se reanuda
  donde quedó. «Reintentar los errores» vuelve a correr solo los términos que fallaron.

### 4. Revisión humana: la tercera columna

La tabla de revisión tiene tres columnas:

1. el término, su cita y sus lecturas esperadas;
2. lo que respondió el modelo;
3. **¿buen trabajo? ✓ / ✗**.

El criterio, escrito en el banco, es: buen trabajo es marcar el término como ambiguo y que las
interpretaciones cubran al menos dos de las lecturas esperadas, sin inventar.

- Las marcas se guardan una por una en `revisiones_modelos`, otra colección, para poder revisar
  mientras la prueba sigue corriendo.
- Cada marca lleva revisor y fecha.
- «Ocultar nombres de los modelos» muestra los modelos como A, B, C… Si se marca algo viendo los
  nombres, la revisión queda como no ciega y el resumen lo avisa.

### 5. Medidas por modelo

- **Detección:** términos marcados como ambiguos sobre los de la prueba. Un error cuenta como no
  detectado, porque el sistema fallaría igual.
- **Aprobación:** ✓ sobre los revisados.
- Las dos van con su **intervalo de Wilson al 95 %**, que se porta bien con n chica y con
  proporciones de 0 o 1, y con un desglose por clase.
- Además: errores, reintentos, intenciones promedio, y la mediana y el p90 de la latencia.
- **Entre cada par de modelos:** la prueba exacta de McNemar sobre los términos que ambos tienen
  revisados. Responde si la diferencia de aprobación es más que azar.
- **Avisos:** muestra chica (menos de 20 términos), revisiones incompletas, términos con error y
  revisión no ciega.

### 6. Gráfica y paquete para Overleaf

- **Gráfica:** detección (naranja: «marcó ambiguo», el mismo significado que en ADR 0026) y
  aprobación (aqua) por modelo, con sus intervalos. Usa el mismo marco, paleta y tamaño de
  texto que el resto de la calibración.
- **Paquete:** `GET /pruebas-modelos/{id}/overleaf.zip` sigue el formato del ADR 0026, con el
  mismo `estilo-dudamel.tex`, que suma dos estilos. Trae:
  - la figura en pgfplots con barras de error;
  - las tablas booktabs por modelo, por clase y por pares;
  - el banco y las respuestas en `longtable`;
  - los CSV;
  - `prueba.json` con las revisiones.
- El texto de los modelos se escapa, y los caracteres que pdfLaTeX no conoce (emojis, flechas)
  se cambian por «?».

## Justificación

- **Un banco fijo** hace comparables los modelos: todos reciben exactamente la misma entrada,
  citable por su huella.
- **La revisión humana** es la única forma razonable de juzgar si unas interpretaciones en texto
  libre «cubren» las lecturas esperadas. Una métrica automática por similitud dependería de otro
  modelo de embeddings.
- **Wilson y McNemar** son las pruebas estándar para proporciones y para comparaciones pareadas
  sobre los mismos ítems, y son cerradas y reproducibles.

## Alternativas consideradas

- **Incluir términos no ambiguos en el banco:** mediría falsos positivos, pero ya los mide el
  ground truth de las entrevistas. Se puede agregar como `ambiguedad_v2` sin cambiar el código,
  más allá del cálculo de detección.
- **Juzgar con un LLM («LLM como juez»):** se descarta como medida principal porque mete el
  sesgo de otro modelo justo en lo que se está comparando.
- **Correr las pruebas por la cola de análisis (ADR 0008):** una prueba larga bloquearía las
  entrevistas. Se acepta que, si al mismo tiempo corre una entrevista con Ollama, las dos
  compiten por la GPU. La pantalla lo deja ver en la latencia.

## Consecuencias

- La pantalla de Calibración tiene dos pestañas: «Umbral · entrevistas» (ADR 0026) y
  «Modelos · banco de términos».
- Las pruebas son de la cuenta que las crea, no de un proyecto.
- Cambiar el banco significa una versión nueva del archivo: las pruebas viejas conservan la
  versión y la huella con que corrieron.
- La versión del sistema pasa a **2.3.0**.
