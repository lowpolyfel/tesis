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

Abre <http://localhost:8000/sandbox>. Endpoints: `POST /procesar`,
`GET /traza/{req_id}`, `GET /eventos/{req_id}` (SSE), `POST /validar/{req_id}`,
`GET /lel`, `GET /trazas`, `GET /salud`; documentación en `/docs`.

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

## Estructura

- `app/models/`: contratos Pydantic y sobre de mensajes (ADR 0001).
- `app/divergence/`: embeddings y similitud coseno mínima entre pares (ADR 0002).
- `app/nlp/`: spaCy, catálogos y filtros deterministas (ADR 0003).
- `app/llm/`, `app/prompts/`: clientes por agente, salida estructurada con un
  reintento, prompts versionados.
- `app/agents/`: los cuatro agentes; reglas R1/R2 del Crítico en código (ADR 0004).
- `app/orchestration/`: grafo = máquina de estados, validación con `interrupt` (ADR 0005).
- `app/db/`: Mongo con respaldo JSON (ADR 0006).
- `app/api/`: FastAPI y `static/sandbox.html`.
- `tests/`: replican la estructura de `app/`.
