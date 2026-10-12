# db

Persistencia de trazas y del LEL (ADR 0006).

- `repositorio.py`: interfaz `Repositorio` con dos implementaciones.
  - `RepositorioMongo`: colecciones `trazas` (un documento por requisito, con
    todos sus mensajes y transiciones) y `lel` (entradas formalizadas).
  - `RepositorioJson`: `data/resultados/trazas/R01.json` y `data/resultados/lel.json`.
    Las escrituras toman un candado de archivo (`trazas/.candado`): un script
    puede escribir junto a la API sin repetir ids.
  - `guardar_lel` reemplaza la entrada del mismo `req_id` y término: reejecutar
    `formalizado` tras una caída no duplica el LEL.
  - Almacén genérico por colección (`proyectos`, `documentos`, `validaciones`…).
- `crear_repositorio(settings)`: usa Mongo si responde al `ping` dentro de
  `MONGO_TIMEOUT_MS`; si no, JSON. La traza registra cuál se usó. Con
  `mongodb+srv://` (Atlas) pasa `tlsCAFile=certifi.where()` y `appname`.
  La descripción dice a qué servidor se conectó, sin credenciales:
  `mongo:atlas:cluster0.xxxx.mongodb.net/tesis`, `mongo:local:localhost:27017/tesis`
  u `mongo:otro:…`. Al arrancar se registra (INFO) o, si cae a JSON, se registra
  el motivo (WARNING) con la contraseña enmascarada.

## Conexión

- `MONGO_URI`, `MONGO_DB` y `MONGO_TIMEOUT_MS` viven **solo en el `.env` de la
  raíz**. pydantic-settings también lee `backend/.env` y, si la variable está en
  los dos, gana `backend/.env`; una variable de entorno del sistema gana a ambos.
  Por eso no deben estar en `backend/.env` ni como variable de Windows.
  Tras editar un `.env`, reinicia uvicorn: `--reload` no lo relee.
- `GET /conexion` (`conexion.py`, pantalla `/conexion` del frontend): tipo
  (`atlas` | `local` | `otro`), host, base, de dónde salió `MONGO_URI`
  (`env_raiz` | `env_backend` | `variable_de_sistema` | `default`, fijado al
  arrancar), ping y versión medidos en el momento, colecciones con su número de
  documentos y una escritura de prueba en `_prueba_conexion` (inserta, lee y
  borra; si la colección queda vacía, la borra). Con el respaldo JSON responde
  200 con `persistencia: "json"` y el motivo del fallo en `error`. Ningún campo
  lleva usuario ni contraseña.
