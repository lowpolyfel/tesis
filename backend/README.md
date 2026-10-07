# backend

Núcleo del sistema en Python 3.12: agentes (Extractor, Clasificador, Crítico,
Modelador), mecanismo de divergencia, filtros deterministas y orquestación con
LangGraph, expuestos por FastAPI. Incluye una sandbox desechable en `/sandbox`.

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
guardan en `data/resultados/` (JSON). `GET /salud` dice cuál se está usando.

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
| `OLLAMA_TIMEOUT_S` | `300` | Tiempo máximo de cada llamada a Ollama. Si se agota, el requisito termina en `error` con la explicación en la traza, en vez de detener la cola. |
| `SSE_INTERVALO_S` | `0.3` | Cada cuánto `/eventos` revisa la traza. |

Al arrancar (también tras `--reload` o una caída), el servidor retoma lo que
quedó a medias: vuelve a encolar lo que no empezó, continúa los grafos desde su
último checkpoint y reanuda las validaciones que ya había aceptado (ADR 0008).
Los requisitos que esperan validación siguen esperando.

Endpoints principales (todo lo que llama a un LLM pasa por la cola de un solo
trabajador, ADR 0008):

| Grupo | Rutas |
|---|---|
| Proyectos | `GET/POST /proyectos`, `GET/PATCH /proyectos/{id}`, `GET /proyectos/{id}/resumen`, `GET/POST /proyectos/{id}/requisitos` |
| Documentos | `POST /proyectos/{id}/documentos` (PDF o .txt), `GET /proyectos/{id}/documentos`, `GET /documentos/{id}`, `POST /requisitos/separar` |
| Requisitos | `POST /procesar`, `GET /requisitos/{id}` (vista por término), `GET /traza/{id}`, `GET /eventos/{id}` (SSE), `POST /validar/{id}`, `GET /requisitos/{id}/artefactos`, `GET /trazas`, `GET /cola` |
| Proyecto | `GET /proyectos/{id}/ambiguedades`, `/flujo`, `/metas`, `/big-picture`, `GET /lel?proyecto_id=` |
| Exploratorio | `POST/GET /proyectos/{id}/comparaciones`, `GET /comparaciones/{id}` (ADR 0012) |
| Experimentación | `GET /calibracion`, `GET /proyectos/{id}/calibracion`, `GET /corpus`, `GET /corpus/{nombre}`, `POST/GET /evaluaciones`, `GET /evaluaciones/{id}` |
| Configuración | `GET /configuracion`, `GET /catalogos`, `GET /salud` |

## Pruebas

```powershell
pytest                                  # desde backend/, sin Ollama ni Mongo
```

Usan LLMs y embeddings falsos (`tests/fakes.py`, `tests/escenarios.py`). Las del
repositorio Mongo usan `mongomock` si está instalado (`pip install mongomock`);
si no, se omiten.

## Casos de aceptación con Ollama real

```powershell
python ..\scripts\casos_aceptacion.py
```

Corre los tres requisitos de la fase hasta la validación humana, imprime filtros,
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
- `app/agents/`: los cuatro agentes; reglas R1/R2 del Crítico en código (ADR 0004).
- `app/orchestration/`: grafo = máquina de estados, validación con `interrupt` (ADR 0005).
- `app/db/`: Mongo con respaldo JSON, proyectos (ADR 0006, 0008).
- `app/documentos/`: carga de PDF/.txt y separación en requisitos (ADR 0009).
- `app/analisis/`: vista por término y análisis del proyecto (ADR 0015).
- `app/artefactos/`: modelo de metas y Big Picture, sin LLM (ADR 0011).
- `app/comparacion/`: comparación entre requisitos, **exploratoria** (ADR 0012).
- `app/calibracion/`: sensibilidad del umbral y contraste con el ground truth (ADR 0013).
- `app/evaluacion/`: corpus y evaluación contra un solo agente (ADR 0014).
- `app/api/`: FastAPI y `static/sandbox.html`.
- `tests/`: replican la estructura de `app/`.
