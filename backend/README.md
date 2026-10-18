# backend

Núcleo del sistema en Python 3.12: agentes (Revisor, Extractor, Clasificador, Crítico,
Modelador), mecanismo de divergencia, filtros deterministas y orquestación con
LangGraph, expuestos por FastAPI (versión 2.4.0). Incluye una sandbox desechable en `/sandbox`.

La versión 2 (ADR 0024) parte de una **entrevista**: los agentes proponen el LEL con la
intención de cada término, una persona lo valida (y el sistema aprende de sus
correcciones), y de ahí salen el mapa conceptual, las metas y los requisitos. La versión 1
(requisitos ya escritos, uno por uno) sigue funcionando igual.

## Instalación (Windows, PowerShell, desde `backend/`)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt     # incluye el modelo es_core_news_sm de spaCy
copy ..\.env.example ..\.env        # y ajusta modelos/umbral si hace falta
```

Ollama debe estar corriendo con los modelos de `.env`:

```powershell
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

MongoDB es opcional: si no responde en `MONGO_URI`, las trazas y el LEL se
guardan en `data/resultados/` (JSON). `GET /conexion` (y la pantalla
`/conexion` del frontend) dice cuál se está usando: Atlas, un Mongo local o
JSON, y de dónde salió `MONGO_URI`. Las variables `MONGO_*` van solo en el
`.env` de la raíz (ver `app/db/README.md`).

## Cuentas

Cada persona entra con su cuenta y solo ve sus proyectos (ADR 0019). Al crear la
cuenta llega un código de 6 dígitos al correo; con él se confirma y se entra.
También hay «¿Olvidaste tu contraseña?» con otro código.

El correo sale por SMTP, configurado en el `.env` de la raíz:

```
SMTP_HOST=smtp.gmail.com
SMTP_PUERTO=587
SMTP_SEGURIDAD=starttls
SMTP_USUARIO=tu-correo@gmail.com
SMTP_CONTRASENA=<contraseña de aplicación de Google, no la normal>
SMTP_REMITENTE=Dudamel <tu-correo@gmail.com>
```

Con Gmail, la cuenta necesita la verificación en dos pasos activada; luego, en
<https://myaccount.google.com/apppasswords>, se crea una contraseña de
aplicación (16 letras) y esa va en `SMTP_CONTRASENA`, con o sin los espacios con
que la muestra Google. La contraseña normal de la cuenta no sirve.

Para probar la configuración sin abrir la app (desde la raíz del repo):

```powershell
python scripts\probar_correo.py              # manda un correo de prueba a SMTP_USUARIO
python scripts\probar_correo.py otra@correo.com
```

Muestra qué leyó y de dónde (nunca la contraseña) y, si falla, la respuesta del
servidor de correo.

Sin `SMTP_HOST` el correo no se envía: el código aparece en la consola de
uvicorn (`Código de registro para …: 123456`) y la pantalla lo avisa. Sirve para
desarrollar sin servidor de correo. `AUTH_CODIGO_AL_ENTRAR=true` pide además un
código cada vez que se entra.

## Ejecutar

```powershell
uvicorn app.api.main:app --reload     # desde backend/
```

La interfaz principal es Dudamel: en otra terminal, `cd ..\frontend`,
`npm install` y `npm run dev`, y abre <http://localhost:5173> (ver
`frontend/README.md`). La sandbox mínima sigue en <http://localhost:8000/sandbox>
y la documentación de la API en `/docs`.

Variables de `.env` que conviene conocer al correrlo (además de las calibrables):

| Variable | Por omisión | Para qué |
|---|---|---|
| `CORS_ORIGENES` | `http://localhost:5173,http://127.0.0.1:5173` | Orígenes del frontend, separados por coma. Agrega aquí el de otra máquina o dominio. |
| `CORS_ORIGENES_REGEX` | cualquier puerto de `localhost` y `127.0.0.1` | Además de la lista: `npm run dev` en 5174 o `npm run preview` (4173) funcionan sin tocar nada. Vacía, solo cuenta la lista. |
| `VALIDACION_HUMANA` | `si_hay_arbitraje` | Cuándo espera el grafo a una persona: solo si un término se resolvió por arbitraje, `siempre` o `nunca` (ADR 0017). Los proyectos de evaluación siempre se detienen antes de validar. |
| `OLLAMA_TIMEOUT_S` | `300` | Tiempo máximo de cada llamada a Ollama. Si se agota, el requisito termina en `error` con la explicación en la traza, en vez de detener la cola. |
| `SSE_INTERVALO_S` | `0.3` | Cada cuánto `/eventos` revisa la traza. |

Al arrancar (también tras `--reload` o una caída), el servidor retoma lo que
quedó a medias: vuelve a encolar lo que no empezó, continúa los grafos desde su
último checkpoint y reanuda las validaciones que ya había aceptado (ADR 0008).
Los requisitos que esperan validación siguen esperando.

Endpoints de la versión 2 (ADR 0024; también pasan por la cola):

| Grupo | Rutas |
|---|---|
| Fases | `GET /proyectos/{id}/fases` (en qué va cada fase, cuál sigue y por qué una está cerrada) |
| Entrevistas | `POST /proyectos/{id}/entrevistas/vista-previa` (turnos y hablantes, sin guardar), `POST /proyectos/{id}/entrevistas/archivo` (PDF o .txt → texto, sin guardar), `POST /proyectos/{id}/entrevistas` (la guarda y la encola, 202), `GET /proyectos/{id}/entrevistas`, `GET/PATCH/DELETE /entrevistas/{id}`, `GET /entrevistas/{id}/bitacora`, `GET /entrevistas/{id}/eventos` (SSE), `POST /entrevistas/{id}/cancelar`, `POST /entrevistas/{id}/reprocesar` |
| LEL interactivo | `GET/POST /proyectos/{id}/lexico`, `POST /lexico/{id}/validar`, `/corregir` (`{cambios, alternativa}`), `/descartar`, `/restaurar`, `POST /proyectos/{id}/lexico/validar-sin-ambiguedad` |
| Memoria | `GET /proyectos/{id}/memoria` (los acuerdos aprendidos), `DELETE /memoria/{id}` (olvidar uno) |
| Mapa, metas, requisitos | `GET/PUT /proyectos/{id}/fases/{fase}` (`mapa`, `metas`, `requisitos`), `POST …/{fase}/generar` (NDJSON con el avance), `POST …/{fase}/conservar` |
| Exportar | `GET /proyectos/{id}/fases/mapa/mermaid`, `GET /proyectos/{id}/fases/requisitos/markdown` (la especificación completa con su trazabilidad) |

Endpoints de la versión 1 (todo lo que llama a un LLM pasa por la cola de un solo
trabajador, ADR 0008):

| Grupo | Rutas |
|---|---|
| Proyectos | `GET/POST /proyectos`, `GET/PATCH /proyectos/{id}` (nombre y contexto general), `GET /proyectos/{id}/resumen`, `GET/POST /proyectos/{id}/requisitos` |
| Documentos | `POST /proyectos/{id}/documentos` (PDF o .txt), `GET /proyectos/{id}/documentos`, `GET /documentos/{id}`, `POST /requisitos/separar` (con IA, patrones de respaldo; ADR 0023) |
| Requisitos | `POST /procesar`, `GET /requisitos/{id}` (vista por término), `GET /traza/{id}`, `GET /eventos/{id}` (SSE), `POST /validar/{id}`, `GET /requisitos/{id}/artefactos`, `PATCH /requisitos/{id}/formalizacion`, `PATCH /requisitos/{id}/lel/{termino}`, `GET /trazas`, `GET /cola` |
| Proyecto | `GET /proyectos/{id}/especificacion` (RF/RNF y glosario), `/ambiguedades`, `/flujo`, `/metas`, `/big-picture` (las tres de artefactos aceptan `?req_ids=`), `GET /lel?proyecto_id=` |
| Mapa conceptual | `GET /proyectos/{id}/mapa-conceptual` (el guardado, si sigue al día), `POST /proyectos/{id}/mapa-conceptual` (lo genera con el Modelador y responde su progreso en NDJSON; ADR 0020) |
| Contexto y triaje | `GET/POST /proyectos/{id}/ficha` (ficha del contexto, ADR 0022), `POST /proyectos/{id}/triaje` (claro, ambiguo o incompleto, contra la ficha) |
| Modelos por cuenta | `GET/PUT /cuenta/modelos` (proveedor y modelo por agente, claves cifradas), `POST /cuenta/modelos/probar`, `POST /cuenta/modelos/listar` (ADR 0021) |
| Exploratorio | `POST/GET /proyectos/{id}/comparaciones`, `GET /comparaciones/{id}` (ADR 0012) |
| Calibración (ADR 0026, 0029) | `GET /proyectos/{id}/calibracion/entrevistas`, `GET/PUT /entrevistas/{id}/etiquetas` (v2.2), `GET/POST /entrevistas/{id}/anotaciones`, `GET/DELETE /anotaciones/{id}`, `PUT /anotaciones/{id}/respuesta`, `POST/GET /proyectos/{id}/calibraciones`, `GET/DELETE /calibraciones/{id}`, `GET /calibraciones/{id}/overleaf.zip` |
| Prueba de modelos (ADR 0027–0029) | `GET /bancos/ambiguedad?version=`, `GET /rubricas/revision`, `GET /pruebas-modelos/modelos`, `POST/GET /pruebas-modelos`, `GET/DELETE /pruebas-modelos/{id}`, `POST /pruebas-modelos/{id}/cancelar`, `/reanudar`, `/repetir`, `GET /pruebas-modelos/series/{serie}`, `GET/POST/DELETE /pruebas-modelos/{id}/revision-calidad`, `PUT/DELETE /pruebas-modelos/{id}/revision-calidad/marca`, `PUT /pruebas-modelos/{id}/modos`, `GET /pruebas-modelos/{id}/overleaf.zip` |
| Experimentación | `GET /calibracion`, `GET /proyectos/{id}/calibracion` (v1, ADR 0013), `GET /corpus`, `GET /corpus/{nombre}`, `POST/GET /evaluaciones`, `GET /evaluaciones/{id}` |
| Configuración | `GET /configuracion`, `GET /catalogos`, `GET /salud`, `GET /conexion` |
| Preparación | `GET /preparacion` (base, Ollama y modelos del análisis: descargados y en memoria), `POST /preparacion/cargar` (precarga uno de esos modelos) |
| Cuenta | `POST /auth/registro`, `/auth/verificar`, `/auth/reenviar`, `/auth/entrar`, `/auth/salir`, `/auth/recuperar`, `/auth/restablecer`, `GET /auth/yo` |
| Borrar | `DELETE /proyectos/{id}` (con todo lo suyo), `DELETE /requisitos/{id}` |
| Reanalizar | `POST /proyectos/{id}/reanalizar` (los que terminaron en error, como reproceso) |

## Pruebas

```powershell
pytest                                  # desde backend/, sin Ollama ni Mongo
```

Usan LLMs y embeddings falsos (`tests/fakes.py`, `tests/escenarios.py`; la versión 2,
`tests/fases/escenario.py`, con la entrevista del consultorio y el debate sobre «consultas»). Las del
repositorio Mongo usan `mongomock` si está instalado (`pip install mongomock`);
si no, se omiten. Las de la API responden como una cuenta de prueba
(`como_usuario`); las de `tests/auth` prueban el registro, el código y la cookie
de verdad, con un correo falso (`CorreoFalso`).

## Casos de aceptación con Ollama real

```powershell
python ..\scripts\casos_aceptacion.py
```

Corre los tres requisitos de la fase hasta la validación humana (fija `VALIDACION_HUMANA=siempre`), imprime filtros,
interpretaciones y similitudes, y guarda el reporte en `data/resultados/aceptacion/`.
Puede correr con la API arriba, también con el respaldo JSON (las escrituras se
serializan con un candado de archivo, ADR 0006); lo que no conviene es arrancar
la API mientras el script está a mitad de un requisito, porque lo retomaría en
paralelo.

## Estructura

- `app/models/`: contratos Pydantic y sobre de mensajes (ADR 0001).
- `app/divergence/`: embeddings y similitud coseno mínima entre pares (ADR 0002).
- `app/nlp/`: spaCy, catálogos y filtros deterministas (ADR 0003).
- `app/llm/`, `app/prompts/`: clientes por agente, salida estructurada con un
  reintento, prompts versionados.
- `app/agents/`: los cinco agentes; reglas R1/R2 del Crítico en código (ADR 0004).
- `app/orchestration/`: grafo del requisito = máquina de estados, validación con `interrupt` (ADR 0005);
  grafo de la entrevista (`grafo_entrevista.py`) y su servicio (ADR 0024).
- `app/entrevistas/`: la entrevista en turnos (`turnos.py`) y su almacén con la bitácora (ADR 0024).
- `app/fases/`: el LEL interactivo (`lexico.py`), la memoria del proyecto (`memoria.py`), el
  mapa con propósito, las metas, los requisitos, las huellas que abren cada fase (`documento.py`)
  y la generación en la cola con su avance (`progreso.py`) (ADR 0024).
- `app/db/`: Mongo con respaldo JSON, proyectos (ADR 0006, 0008).
- `app/documentos/`: carga de PDF/.txt y separación en requisitos (ADR 0009).
- `app/analisis/`: vista por término y análisis del proyecto (ADR 0015).
- `app/artefactos/`: especificación RF/RNF, modelo de metas y Big Picture, sin LLM (ADR 0011, 0017), y el
  mapa conceptual, que organiza el Modelador sobre un protocolo previo en código (ADR 0020).
- `app/comparacion/`: comparación entre requisitos, **exploratoria** (ADR 0012).
- `app/calibracion/`: sensibilidad del umbral y contraste con el ground truth: sobre las entrevistas, con ROC, AUC, intervalos bootstrap, corridas guardadas y el paquete para Overleaf (ADR 0026); sobre las trazas v1 (ADR 0013). La prueba de modelos con bancos versionados de términos (`banco/`: v1 con 50 ambiguos; v2 con 23 controles inequívocos más), con exhaustividad, falsas alarmas y precisión; calidad con tres criterios binarios a ciegas (`calidad.py`, rúbrica en `rubrica.py`), McNemar sobre detección y criterios, subenumeración, modos de falla y estabilidad entre corridas (`estabilidad.py`); etiquetado de entrevistas por varias personas con kappa de Cohen (`anotaciones.py`); ids que no se reutilizan (`verificar_ids.py`) y paquetes para Overleaf que compilan con pdfLaTeX y XeLaTeX (ADR 0027–0029).
- `app/evaluacion/`: corpus y evaluación contra un solo agente (ADR 0014).
- `app/api/`: FastAPI y `static/sandbox.html`.
- `tests/`: replican la estructura de `app/`.
