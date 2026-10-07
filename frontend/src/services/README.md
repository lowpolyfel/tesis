# services

Comunicación con el backend (FastAPI):

- `http.js`: transporte; la URL base sale de `VITE_API_URL` (por omisión `http://localhost:8000`).
- `backend.js`: una función por endpoint.
- `eventos.js`: SSE de un requisito (`GET /eventos/{req_id}`).
