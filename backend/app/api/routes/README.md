# routes

Endpoints de FastAPI. Solo validan la entrada y delegan en `app.orchestration.Servicio`.
Todo exige sesión salvo `/auth/*` y `/salud` (ADR 0019); lo de otra cuenta responde 404.

| Método | Ruta | Archivo |
|---|---|---|
| POST | `/auth/registro`, `/auth/verificar`, `/auth/reenviar`, `/auth/entrar`, `/auth/salir`, `/auth/recuperar`, `/auth/restablecer` | `auth.py` |
| GET | `/auth/yo` | `auth.py` |
| GET/POST/PATCH/DELETE | `/proyectos`, `/proyectos/{id}` | `proyectos.py` |
| DELETE | `/requisitos/{req_id}` | `requisitos.py` |
| POST | `/procesar` (con `proyecto_id`) | `requisitos.py` |
| GET | `/trazas`, `/traza/{req_id}` | `requisitos.py` |
| GET | `/eventos/{req_id}` (SSE) | `requisitos.py` |
| POST | `/validar/{req_id}` | `requisitos.py` |
| GET | `/lel` | `lel.py` |
| GET | `/sandbox`, `/salud`, `/conexion` | `sandbox.py` |
| GET | `/preparacion` (base, Ollama y modelos del análisis) | `preparacion.py` |
| POST | `/preparacion/cargar` (precarga un modelo configurado; 422 si no lo es, 502 si Ollama falla) | `preparacion.py` |
