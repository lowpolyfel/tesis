# hooks

- `useApi`: ejecuta una llamada del backend y expone datos, error, carga y `recargar` (silencioso: conserva la referencia si la respuesta no cambió; `{ silencioso: false }` vuelve a mostrar la carga). Un cambio local con `setDatos` descarta las respuestas que salieron antes de él y vuelve a pedir.
- `useCache`: datos que comparten las fases (léxico, entrevistas y sus turnos) en una caché por clave, con revalidación en segundo plano; `invalidarCache(prefijo)` los pone al día.
- `useRequisitoVivo`: vista por término de un requisito que se mantiene al día con el SSE mientras el requisito no termina.
