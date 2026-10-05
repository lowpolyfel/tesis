# 0006. Persistencia: MongoDB con respaldo JSON; SSE por sondeo

- **Fecha:** 2026-10-05
- **Estado:** Aceptada

## Contexto

La traza es el NFR de trazabilidad: un documento por requisito con todos los
mensajes, del que se pueda reconstruir el proceso completo. Las entradas
formalizadas forman el LEL. La sandbox debe funcionar aunque MongoDB no esté
corriendo, y debe mostrar los mensajes en vivo.

## Decisión

1. **Una interfaz, dos implementaciones** (`app/db/repositorio.py`):
   `RepositorioMongo` (colecciones `trazas` y `lel`) y `RepositorioJson`
   (`data/resultados/trazas/R01.json` y `data/resultados/lel.json`).
2. **Fábrica con respaldo:** se intenta `ping` a Mongo con `MONGO_TIMEOUT_MS`;
   si falla, JSON. Cuál se usó queda en la traza (`config.persistencia`) y en
   `GET /salud`.
3. **Identificadores** `R01`, `R02`, … consecutivos. En Mongo `_id = req_id`; si
   dos procesos chocan, el índice único de `_id` obliga a tomar el siguiente.
4. **Secuencia de mensajes atómica:** en Mongo, `$inc` sobre `ultima_secuencia`
   del documento; en JSON, un candado de proceso y escritura atómica
   (archivo temporal + `os.replace`).
5. **Transiciones de estado** en la traza (`transiciones`: estado, último
   mensaje previo, fecha), además del estado actual. Con mensajes y transiciones
   se reconstruye el camino completo.
6. **SSE por sondeo del repositorio:** `GET /eventos/{req_id}` lee la traza cada
   `SSE_INTERVALO_S` y envía los mensajes nuevos y los cambios de estado. Así
   funciona igual con Mongo o JSON y no hay un bus en memoria que se pierda.

## Alternativas consideradas

- **Change streams de Mongo:** requieren réplica; no aplican al respaldo JSON.
- **Bus en memoria (colas por requisito):** más inmediato, pero duplica la
  fuente de verdad y no sobrevive a un reinicio.
- **Colección de contadores para `req_id`:** una colección más sin necesidad.

## Consecuencias

- El respaldo JSON es para un solo proceso (un candado de hilo); no está pensado
  para varios servidores sobre la misma carpeta.
- `data/resultados/trazas/` y `lel.json` no se versionan (están en `.gitignore`).
