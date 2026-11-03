# Mapa del código de Dudamel

Qué hace cada carpeta y cada archivo del repositorio, versión 2.5.0. Las decisiones de diseño
están en `docs/adr/` (el número entre paréntesis es el ADR que la explica).

**v1** = la versión 1: requisitos ya escritos, analizados uno por uno.
**v2** = la versión 2: de la entrevista a los requisitos, por fases.

---

## Raíz

| Archivo | Qué hace |
|---|---|
| `README.md` | Presentación del proyecto: el flujo por fases, los agentes, el stack y la estructura. |
| `CHANGELOG.md` | Qué cambió en cada versión. |
| `.env.example` | Plantilla de variables de entorno: modelos, umbral, rondas, Mongo, correo, etc. |
| `.gitignore` | Lo que no se sube a git: `.env`, datos generados, checkpoints, `node_modules`. |
| `docker-compose.yml` | Levanta los servicios de apoyo (MongoDB) con Docker. |

---

## `backend/` — servidor en Python (FastAPI + LangGraph)

| Archivo | Qué hace |
|---|---|
| `README.md` | Cómo instalar, arrancar y probar el backend; tabla de endpoints y variables de operación. |
| `requirements.txt` | Dependencias de Python con versión fija. |
| `pytest.ini` | Configuración de las pruebas. |
| `scripts_prueba_divergencia.py` | Script suelto para probar a mano el mecanismo de divergencia. |

### `backend/app/` — el código de la aplicación

| Archivo | Qué hace |
|---|---|
| `config.py` | Toda la configuración calibrable, leída del `.env`: modelos por agente, umbral (0.75), rondas (2), temperatura y semilla, rutas, Mongo, rejilla de calibración. |
| `preparacion.py` | Antes de analizar, revisa la base de datos, Ollama y los modelos, y los carga en memoria. |
| `README.md` | Guía de los módulos de `app/`. |

### `app/agents/` — los cinco agentes LLM

Cada agente es una clase que arma su prompt, llama al LLM con salida estructurada y devuelve un contrato validado. Ningún agente toca la base de datos.

| Archivo | Qué hace |
|---|---|
| `base.py` | Utilidades comunes de los agentes: llamada estructurada y registro de la respuesta. |
| `revisor/agente.py` | **Revisor**: lee la entrevista y arma su ficha (participantes, objetivo, problemas, necesidades, reglas, con turnos). En v1 también la ficha del contexto, el triaje y la separación con IA (22, 23). |
| `extractor/agente.py` | **Extractor**: separa el vocabulario del dominio. No interpreta. |
| `clasificador/agente.py` | **Clasificador**: propone la intención de cada término y, si ve varias, las da como candidatas; refina o retira en el debate. No decide cuál es la correcta. |
| `critico/agente.py` | **Crítico**: objeta las interpretaciones contra reglas y arbitra al agotarse las rondas. No genera interpretaciones. |
| `critico/reglas.py` | Reglas del Crítico que se verifican en código con spaCy: R1 (vocabulario consistente con el LEL) y R2 (sin entidades nuevas). R3 la juzga el LLM (4). |
| `modelador/agente.py` | **Modelador**: formaliza lo validado: entradas del LEL, mapa conceptual, metas y requisitos. No valida. |
| `*/README.md` | Contrato de entrada y salida de cada agente. |

### `app/orchestration/` — los grafos de LangGraph y la cola

| Archivo | Qué hace |
|---|---|
| `grafo_entrevista.py` | **Grafo v2**: `cargada → leida → extraida → interpretada → (en_debate ⟲ → arbitrada) → modelada`. De una entrevista a su LEL propuesto (24). |
| `grafo.py` | **Grafo v1**: la máquina de estados de un requisito, con la pausa `humano` (`interrupt`) para la validación (5). |
| `estado.py` | Estado tipado del grafo v1 (JSON plano). |
| `dependencias.py` | Arma lo que usan los grafos (agentes, filtros, embeddings, repositorio) desde la configuración; las pruebas lo reemplazan por dobles. |
| `servicio.py` | Punto de entrada para la API: registrar, ejecutar, validar y reanudar requisitos; checkpointer SQLite; retoma lo pendiente al arrancar (8). |
| `servicio_entrevistas.py` | Pone las entrevistas en la cola con los modelos de la cuenta y retoma las que quedaron a medias. |
| `cola.py` | Cola de trabajos con un solo trabajador y prioridades (8). |

### `app/divergence/` — el mecanismo de divergencia (no es un agente)

| Archivo | Qué hace |
|---|---|
| `embeddings.py` | Vectores de las paráfrasis con `nomic-embed-text` (Ollama). |
| `similitud.py` | Coseno a mano, similitud mínima entre pares y la decisión `similitud ≥ umbral → aceptado_directo`, si no `en_debate`. Funciones puras (2). |
| `evaluacion.py` | Junta embeddings y similitud para las interpretaciones de un término. |

### `app/llm/` — cómo se habla con los modelos

| Archivo | Qué hace |
|---|---|
| `cliente.py` | Cliente de Ollama (`ChatOllama` de LangChain) con el esquema JSON como formato de salida. |
| `proveedores.py` | Catálogo de proveedores y clientes HTTP directos para Gemini y OpenAI (formato compatible) y Claude; lista de modelos disponibles (21). |
| `perfiles.py` | Qué proveedor y modelo usa cada agente por cuenta (colección `perfiles_llm`); cifra las claves de API con Fernet (21). |
| `prompts.py` | Carga los prompts versionados de `app/prompts/`. |
| `estructurado.py` | Llamada con salida estructurada: valida con Pydantic, reintenta una vez con el error y, si vuelve a fallar, lanza `FalloEstructurado` con la traza (1). |

### `app/prompts/` — plantillas de los prompts (`<agente>_v<N>.txt`)

Cada archivo es un prompt versionado. La bitácora guarda qué versión se usó en cada llamada.

| Grupo | Archivos |
|---|---|
| Revisor | `revisor_entrevista_v1` (ficha de la entrevista), `revisor_ficha_v1`, `revisor_triaje_v1`, `revisor_separacion_v1` (v1) |
| Extractor | `extractor_entrevista_v1` (v2), `extractor_v1` (v1) |
| Clasificador | `clasificador_intencion_v1` (v2, también la prueba de modelos), `clasificador_refinamiento_entrevista_v1`, `clasificador_v1–v3`, `clasificador_refinamiento_v1` (v1) |
| Crítico | `critico_entrevista_v1`, `critico_arbitraje_entrevista_v1` (v2), `critico_v1`, `critico_arbitraje_v1–v2` (v1) |
| Modelador | `modelador_lexico_v1`, `modelador_mapa_proposito_v1`, `modelador_metas_v1`, `modelador_requisitos_v1` (v2); `modelador_v1–v2`, `modelador_requisito_v1–v2`, `modelador_mapa_v1` (v1) |
| Otros | `comparador_v1` (juez de la comparación entre requisitos), `agente_unico_v1` (línea base de la evaluación) |

### `app/models/` — contratos (Pydantic)

| Archivo | Qué hace |
|---|---|
| `comunes.py` | Vocabulario cerrado: estados, nodos, tipos de mensaje, tipos de ambigüedad, vías de decisión. |
| `contratos.py` | Entrada y salida de cada agente en v1 (1). |
| `fases.py` | Contratos de v2: ficha de la entrevista, entradas del LEL, mapa, metas y requisitos (24). |
| `mensajes.py` | El sobre común de los mensajes entre nodos (emisor, receptor, tipo, payload, modelo, versión del prompt) y la traza (1). |

### `app/nlp/` — procesamiento de lenguaje sin LLM

| Archivo | Qué hace |
|---|---|
| `spacy_es.py` | Acceso único a spaCy `es_core_news_sm`: lemas, sustantivos, entidades y `normalizar`. |
| `catalogos.py` | Catálogos de regionalismos y vaguedad con `PhraseMatcher` (3). |
| `filtros.py` | Filtros deterministas antes del Clasificador: LEL, regionales, vagos, límites (3). |
| `detectores.py` | Detectores de posible ambigüedad de alcance y anafórica (10). |

### `app/entrevistas/` — v2: la entrevista

| Archivo | Qué hace |
|---|---|
| `turnos.py` | Del texto (pegado, .txt o PDF) a los turnos T1, T2…, con hablantes y su rol probable. |
| `almacen.py` | Colecciones `entrevistas` y `bitacoras`: crear, estados, mensajes entre agentes, borrar (24). |

### `app/fases/` — v2: las fases después de la entrevista

| Archivo | Qué hace |
|---|---|
| `lexico.py` | El LEL interactivo: proponer, validar, corregir, elegir otra intención, descartar. |
| `memoria.py` | La memoria del proyecto: los **acuerdos** que salen de lo que corrige la persona y que reciben los agentes en sus prompts. |
| `claves.py` | Cómo se reconoce el mismo término en el LEL, la memoria y las entrevistas. |
| `mapa.py` | Fase del mapa conceptual con propósito (pregunta de enfoque, conceptos, proposiciones). |
| `metas.py` | Fase de metas en tres niveles: organización, estratégicas y específicas. |
| `requisitos.py` | Fase de requisitos funcionales y no funcionales, rastreables a metas, LEL y turnos. |
| `documento.py` | El documento de cada fase y en qué va el proyecto. |
| `progreso.py` | Corre una fase en la cola y cuenta su avance en vivo. |
| `textos.py` | Lo validado en una fase convertido en el texto que leen los agentes en la siguiente; filtra las citas que no existen. |

### `app/db/` — persistencia

| Archivo | Qué hace |
|---|---|
| `repositorio.py` | MongoDB con respaldo en archivos JSON (`data/resultados/`) si Mongo no responde; misma interfaz para las dos (6). |
| `proyectos.py` | Proyectos por cuenta; cada uno separa su LEL (8). |
| `conexion.py` | A qué Mongo está conectado el servidor (`GET /conexion`). |

### `app/auth/` — cuentas

| Archivo | Qué hace |
|---|---|
| `cuentas.py` | Registro con código por correo, entrar, sesiones y restablecer la contraseña. |
| `contrasenas.py` | Hash de contraseñas con scrypt. |
| `correo.py` | Envío del código por SMTP. |
| `modelos.py` | El documento de una cuenta (colección `usuarios`). |

### `app/contexto/` — la ficha del contexto del proyecto

| Archivo | Qué hace |
|---|---|
| `ficha.py` | La ficha del contexto del proyecto que arma el Revisor (22). |
| `triaje.py` | Triaje de requisitos contra la ficha (v1). |

### `app/documentos/` — v1: carga de documentos de requisitos

| Archivo | Qué hace |
|---|---|
| `extraccion.py` | Del PDF o .txt al texto por página. |
| `limpieza.py` | Limpia el texto extraído y reconstruye párrafos. |
| `patrones.py` | Expresiones regulares para separar requisitos (numeración, verbos de obligación). |
| `separacion.py` | Separa un texto en requisitos candidatos por patrones (9). |
| `separacion_ia.py` | Separación con IA para textos pegados (23). |
| `almacen.py` | Colección `documentos`: extracción, separación y registro. |
| `modelos.py` | Contratos del módulo. |

### `app/analisis/` — v1: vistas derivadas para el frontend

| Archivo | Qué hace |
|---|---|
| `requisito.py` | La vista por término de un requisito, desde su traza. |
| `proyecto.py` | Resumen, ambigüedades por término y flujo KMoS-SSA por ciclo de un proyecto. |
| `traza.py` | Qué mensajes de una traza cuentan y cómo se normaliza su configuración. |
| `configuracion.py` | La configuración vigente y los catálogos, de solo lectura. |
| `formas.py` | Las formas exactas de esas vistas (15). |

### `app/artefactos/` — v1: artefactos de salida

| Archivo | Qué hace |
|---|---|
| `especificacion.py` | Especificación RF/RNF armada en código desde lo formalizado. |
| `metas.py` | Modelo de metas estratégicas. |
| `big_picture.py` | El Big Picture como grafo de conocimiento. |
| `mapa_conceptual.py` | Mapa conceptual (20). |
| `exportar.py` | Exporta a Mermaid y PlantUML, de forma determinista. |
| `seleccion.py` | Qué requisitos entran a los artefactos. |
| `simbolos.py` | Símbolos del LEL agrupados por forma normalizada. |
| `terminos.py` | Compara términos contra textos sin LLM (también lo usa el grafo v2). |
| `formas.py` | Las formas de los artefactos (11). |

### `app/comparacion/` — v1: comparación entre requisitos (exploratoria)

| Archivo | Qué hace |
|---|---|
| `bases.py` | Qué texto se compara de cada requisito. |
| `pares.py` | Selecciona por coseno los pares que pasan al juez LLM y marca casi duplicados. |
| `juez.py` | El juez LLM de un par (`comparador_v1`). |
| `vocabulario.py` | Inconsistencias de vocabulario entre requisitos. |
| `ejecucion.py` | La corrida completa, guardada paso a paso. |
| `modelos.py` | Contratos (12). |

### `app/evaluacion/` — v1: evaluación contra el corpus

| Archivo | Qué hace |
|---|---|
| `corpus.py` | El corpus de requisitos con su ground truth en un archivo aparte. |
| `agente_unico.py` | Línea base de un solo agente, sin debate, para comparar contra el multiagente. |
| `emparejamiento.py` | Empareja los términos detectados con los del ground truth. |
| `metricas.py` | Precisión, exhaustividad y demás contra el ground truth. |
| `ejecucion.py` | La corrida de una evaluación. |
| `modelos.py`, `formas.py` | Documento y formas de respuesta (14). |

### `app/calibracion/` — calibración del umbral y prueba de modelos

Todo es de solo lectura: no cambia el umbral ni toca a los agentes.

| Archivo | Qué hace |
|---|---|
| `entrevistas.py` | Calibración del umbral sobre las entrevistas de v2 (26). |
| `informe_entrevistas.py` | El informe de calibración (sensibilidad, ground truth, ROC) y las corridas guardadas. |
| `anotaciones.py` | Etiquetado de términos por varias personas, a ciegas, con la kappa de Cohen (29). |
| `estadistica.py` | ROC, AUC, intervalos bootstrap, banda ROC. |
| `sensibilidad.py` | Qué habría decidido cada umbral de la rejilla (13). |
| `ground_truth.py`, `informe.py`, `formas.py` | Calibración de v1 sobre el corpus (13). |
| `pruebas_modelos.py` | La prueba de modelos con el banco: corre modelos, guarda respuestas, resumen con exhaustividad, falsas alarmas, precisión y Wilson (27, 28). |
| `banco/ambiguedad_v1.json`, `ambiguedad_v2.json` | Los bancos de términos: 50 ambiguos; v2 suma 23 controles inequívocos. No se editan: se versionan. |
| `calidad.py` | Revisión de calidad a ciegas (fidelidad, delimitación, intención), cobertura, McNemar, subenumeración y modos de falla (29). |
| `rubrica.py` | La rúbrica con sus casos frecuentes; genera `docs/rubrica-revision.md`. |
| `intercambio.py` | Exporta la revisión a un archivo a ciegas e importa lo que conteste una persona o una IA (30). |
| `estabilidad.py` | Estabilidad entre corridas idénticas de una serie. |
| `verificar_ids.py` | Reporta ids repetidos entre la base local y Mongo (`python -m app.calibracion.verificar_ids`). |
| `latex.py` | Paquete de Overleaf de una corrida de calibración. |
| `latex_modelos.py` | Paquete de Overleaf de una prueba de modelos (figuras pgfplots desde CSV, tablas, apéndice). |

### `app/api/` — la API

| Archivo | Qué hace |
|---|---|
| `main.py` | Crea la aplicación FastAPI, la versión, CORS, la sesión obligatoria y el arranque del trabajador. |
| `dependencias.py` | El servicio, la cuenta con sesión y lo que pertenece a esa cuenta (lo ajeno responde 404). |
| `static/sandbox.html` | Página de prueba desechable. |

`app/api/routes/` tiene un archivo por grupo de endpoints:

| Archivo | Endpoints |
|---|---|
| `auth.py` | Registro, verificación, entrar, salir, recuperar la contraseña. |
| `proyectos.py` | Proyectos de la cuenta. |
| `entrevistas.py` | Subir y leer entrevistas, procesarlas, bitácora en vivo (v2). |
| `lel.py` | Entradas del LEL. |
| `fases.py` | Mapa, metas y requisitos de v2: generar, editar, validar, descargar. |
| `contexto.py` | Ficha del contexto y triaje. |
| `modelos.py` | Qué modelo usa cada agente de la cuenta. |
| `preparacion.py` | Estado de la base, Ollama y los modelos. |
| `requisitos.py`, `documentos.py`, `analisis.py`, `artefactos.py`, `comparaciones.py`, `evaluaciones.py` | v1. |
| `calibracion.py`, `calibracion_entrevistas.py` | Calibración del umbral (v1 y v2), etiquetado, corridas, Overleaf. |
| `pruebas_modelos.py` | Banco, rúbrica, pruebas, revisión de calidad, exportar e importar, modos de falla, Overleaf. |
| `sandbox.py` | La página sandbox y el estado del servidor. |

### `backend/tests/` — pruebas automáticas

Replica la estructura de `app/` (`tests/agents`, `tests/orchestration`, `tests/calibracion`…). `fakes.py` tiene los LLM y embeddings falsos para probar sin Ollama, y `escenarios.py` y `tests/fases/escenario.py` montan proyectos de ejemplo.

---

## `frontend/` — la interfaz (React + Vite)

| Archivo | Qué hace |
|---|---|
| `index.html`, `vite.config.js` | Entrada de la página y configuración de Vite. |
| `package.json`, `package-lock.json` | Dependencias y versión (2.5.0). |
| `src/main.jsx` | Arranca React. |
| `src/App.jsx` | Las rutas de la aplicación. |
| `src/index.css`, `src/styles/dudamel.css` | Estilos globales y el sistema visual (colores, tema claro y oscuro). |

### `src/services/` — conexión con el backend

| Archivo | Qué hace |
|---|---|
| `http.js` | Transporte: `get`, `post`, `put`, errores y la sesión. |
| `backend.js` | **Todas** las llamadas al backend (las pantallas no arman URLs). |
| `eventos.js` | Mensajes en vivo por SSE. |

### `src/pages/` — pantallas

| Archivo | Qué hace |
|---|---|
| `intro/` (`Intro`, `Landing`, `Loader`, `Welcome`) | Portada, carga y entrada. |
| `cuenta/Cuenta.jsx` | Registro, entrar y recuperar la cuenta. |
| `Proyectos.jsx` | La lista de proyectos. |
| `fases/Proyecto.jsx` | El proyecto en v2, con su camino por fases. |
| `fases/NuevaEntrevista.jsx`, `Entrevistas.jsx` | Subir una entrevista y la lista con sus turnos. |
| `fases/EscenaEntrevista.jsx` | La escena en vivo mientras los agentes procesan la entrevista. |
| `fases/Lexico.jsx` | El LEL interactivo para validar. |
| `fases/Mapa.jsx`, `Metas.jsx`, `Requisitos.jsx` | Las fases que genera el Modelador. |
| `Calibracion.jsx` | Calibración del umbral y prueba de modelos. |
| `Configuracion.jsx` | Modelos por agente y claves de la cuenta. |
| `Mas.jsx` | Lo que no es del trabajo diario (v1, catálogos, conexión, evaluación). |
| `Conexion.jsx`, `Catalogos.jsx`, `Cola.jsx` | Base conectada, catálogos y el historial de la cola. |
| `proyecto/`, `Analizar.jsx`, `Analisis.jsx`, `DetalleRequisito.jsx`, `Validacion.jsx`, `Ambiguedades.jsx`, `Comparaciones.jsx`, `Evaluacion.jsx`, `Flujo.jsx`, `Lel.jsx` | Pantallas de v1. |

### `src/components/` — piezas reutilizables

| Carpeta o archivo | Qué hace |
|---|---|
| `calibracion/PruebaModelos.jsx` | La prueba de modelos: nueva prueba, resultados, revisión, falsos negativos, estabilidad. |
| `calibracion/RevisionCalidad.jsx` | La revisión a ciegas con el teclado. |
| `calibracion/RevisionFuera.jsx` | Exportar e importar la revisión (persona o IA). |
| `calibracion/EtiquetarEntrevista.jsx` | Etiquetado de términos de entrevista (S/N/X). |
| `calibracion/Rubrica.jsx` | La rúbrica en un panel lateral. |
| `calibracion/graficas.jsx` | Las gráficas de calibración (ROC, modelos). |
| `fases/` | Piezas de v2: el camino del proyecto, citas, editor del mapa (React Flow), carga de fases. |
| `orb/` | Las esferas animadas de Dudamel (motor, colores, poses, estados de ánimo). |
| `traza/` | La traza de un requisito en v1: bitácora, rondas, matrices, ruta de estados. |
| `artefactos/` | Diagramas Mermaid y exportaciones. |
| `intro/`, `layout/Shell.jsx` | Botones de portada y el marco de la aplicación. |
| `ui.jsx` | Piezas comunes: pestañas, avisos, confirmar, plegables. |
| `sesion.jsx`, `tema.jsx` | La cuenta con sesión y el tema claro u oscuro. |

### Otras carpetas de `src/`

| Carpeta | Qué hace |
|---|---|
| `escena/` | La escena en vivo: coreografía de los mensajes de los agentes, resumen legible de cada mensaje, preparación. |
| `hooks/` | `useApi` (pedir datos), `useCache`, `useRequisitoVivo` (SSE). |
| `constants/` | Estados, fases, tipos de agente y proyectos. |

---

## `data/` — datos

| Carpeta | Qué hace |
|---|---|
| `corpus/` | Requisitos de prueba con su ground truth, separados (evaluación de v1). |
| `catalogos/regionales.json`, `vaguedad.json` | Mexicanismos y palabras vagas que usan los filtros. |
| `resultados/` | Donde se guarda todo cuando no hay Mongo (un JSON por documento) y los checkpoints. |

## `docs/` — documentación

| Archivo | Qué hace |
|---|---|
| `CONTEXTO_PROYECTO.md` | El contexto y alcance del proyecto de tesis. |
| `adr/` | Las 30 decisiones de diseño, con plantilla. |
| `rubrica-revision.md` | La rúbrica de la revisión humana (apéndice; se genera desde el backend). |
| `lel/`, `diagramas/` | LEL del dominio y diagramas (secuencia, actividad, componentes). |
| `mapa-del-codigo.md` | Este documento. |

## `scripts/`

| Archivo | Qué hace |
|---|---|
| `casos_aceptacion.py` | Corre los casos de aceptación con Ollama real y reporta lo observado. |
| `probar_correo.py` | Prueba la configuración SMTP sin abrir la app. |

## `revisiones/`

Las respuestas de revisión de calidad que contestó la IA (P02, P03, P04), listas para importar.
