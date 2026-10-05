# routes

Endpoints de FastAPI. Solo validan la entrada y delegan en `app.orchestration.Servicio`.

| Método | Ruta | Archivo |
|---|---|---|
| POST | `/procesar` | `requisitos.py` |
| GET | `/trazas`, `/traza/{req_id}` | `requisitos.py` |
| GET | `/eventos/{req_id}` (SSE) | `requisitos.py` |
| POST | `/validar/{req_id}` | `requisitos.py` |
| GET | `/lel` | `lel.py` |
| GET | `/sandbox`, `/salud` | `sandbox.py` |
