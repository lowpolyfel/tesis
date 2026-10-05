# api

Capa HTTP de FastAPI (`main.py`). Los endpoints viven en `routes/`; la sandbox
(`static/sandbox.html`, JS plano, desechable) se sirve en `/sandbox`.

Arranque, desde `backend/`:

```
uvicorn app.api.main:app --reload
```
