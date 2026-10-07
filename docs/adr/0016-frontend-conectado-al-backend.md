# 0016. Frontend conectado al backend: escena dirigida por mensajes reales

- **Fecha:** 2026-10-06
- **Estado:** Aceptada

## Contexto

Dudamel (el frontend en React) nació como prototipo con datos simulados
(`mockDb.js`, `simulacion.js`, `fixtures/`): un requisito tenía **una**
divergencia con dos interpretaciones fijas *A* y *B*, y la escena animaba un guion
inventado. El backend no trabaja así: la divergencia se mide por término
(ADR 0002), cada término tiene N interpretaciones `I1..In` que el Clasificador
refina o retira en cada ronda (ADR 0005) y cada paso queda como un `Mensaje`
de la traza (ADR 0001). El usuario pidió que la interfaz se conectara al backend
y que se **viera qué hace cada agente**.

## Decisión

1. **Un solo transporte.** `services/http.js` (URL base en `VITE_API_URL`, por
   omisión `http://localhost:8000`; los errores `{detail}` del backend se
   convierten en `Error` con ese texto) y `services/backend.js`, una función por
   endpoint. Ninguna pantalla llama a `fetch` directamente.
2. **La escena se dirige con los mensajes reales.** `services/eventos.js` sigue
   `GET /eventos/{req_id}` (SSE); `escena/useEnVivo.js` encola los mensajes,
   descarta repetidos por `secuencia` (reconexiones) y los anima con un ritmo
   legible que la persona puede acelerar. `escena/coreografia.js` traduce cada
   mensaje (emisor → receptor, tipo, payload) a movimientos de la esfera: una
   esfera por nodo real del grafo (Extractor, Filtros, Clasificador,
   Divergencia, Crítico, Humano, Modelador), una por interpretación de cada
   término, y una partícula por mensaje. **Lo que no está en la traza no se
   anima**: la escena no decide ni completa nada del método.
3. **Las vistas no recalculan.** Lo que la interfaz muestra por término, por
   proyecto (ambigüedades, flujo KMoS-SSA) y para la calibración viene ya armado
   del backend (`app/analisis`, ADR 0015; `app/calibracion`, ADR 0013). La
   interfaz solo presenta.
4. **Validación por término** contra `POST /validar/{req_id}`: en cada término
   la persona acepta la propuesta, elige otra de las interpretaciones o la
   reescribe; aprobar o rechazar es una sola decisión por requisito
   (`Validacion.decision`). La reanudación pasa por la cola (ADR 0008).
5. **El proyecto vive en la URL** (`?proyecto=`) en las vistas de análisis, para
   que un enlace se pueda compartir y la recarga no lo pierda.
6. **Configuración y catálogos de solo lectura** en la interfaz: se cambian en
   `backend/.env` y en `data/catalogos/*.json`; cada traza guarda la
   configuración y la versión de catálogo con que corrió.
7. **Sin datos simulados en el repositorio.** Se borran `mockDb.js`,
   `simulacion.js`, `polling.js` y los fixtures (queda solo el documento de
   ejemplo de la pantalla de carga).
8. **Errores y conexión** (añadido el 2026-10-07). El backend admite por omisión
   cualquier puerto de `localhost` y `127.0.0.1` (`CORS_ORIGENES` más
   `CORS_ORIGENES_REGEX`), para que `npm run preview` o Vite en otro puerto no
   queden sin backend. Todo error sale como `{detail}` con cabeceras CORS,
   también un 500 inesperado, así que `http.js` muestra el error del servidor y
   reserva «No hay conexión» para cuando de verdad no la hay. El SSE termina sin
   `fin` cuando el servidor se apaga (Ctrl+C, `--reload`); el navegador reconecta
   solo y `Last-Event-ID` evita repetir mensajes.

## Justificación

- La tesis estudia la divergencia entre interpretaciones de los agentes; una
  animación que no saliera de la traza enseñaría algo que el sistema no hizo.
- SSE basta: el flujo es de una sola dirección (backend → interfaz) y el
  backend ya numera los mensajes, lo que hace segura la reconexión.
- Calcular en el backend deja una sola definición de cada métrica, la misma que
  usan las pruebas y el script de casos.
- Con la configuración en `.env` ningún parámetro calibrable queda en el código
  ni se cambia a mano desde la interfaz sin dejar rastro.

## Alternativas consideradas

- **Sondear la traza para la escena:** más simple, pero los mensajes llegan en
  bloques y fuera de ritmo; se usa solo para listas y contadores.
- **WebSocket:** innecesario para un flujo unidireccional.
- **Conservar el modelo A/B en la interfaz:** no representa N interpretaciones
  ni el retiro de interpretaciones entre rondas.
- **Editar umbral, modelos y catálogos desde la interfaz:** cómodo, pero rompe
  la reproducibilidad (un cambio sin versión) y mezcla calibración con uso.
- **Mantener un modo de demostración con LLM simulados en el repositorio:**
  descartado; todo resultado que se vea en la interfaz debe venir de los
  agentes reales. Las pruebas del backend ya usan LLM con guion
  (`tests/escenarios.py`).

## Consecuencias

- La interfaz necesita el backend corriendo (y Ollama para procesar requisitos
  nuevos); sin él, las pantallas muestran el error de conexión.
- La duración de la escena depende de los LLM; con el ritmo y «acelerar» la
  persona controla la lectura sin perder mensajes.
- Cualquier cambio de forma en `app/analisis/formas.py` u otras respuestas
  obliga a revisar la pantalla que la usa.
- Admitir cualquier puerto local es cómodo porque el backend es una herramienta
  local sin autenticación; para exponerlo fuera de la máquina hay que vaciar
  `CORS_ORIGENES_REGEX` y listar los orígenes en `CORS_ORIGENES`.
- El SSE se entera del apagado por las señales que atiende uvicorn (SIGINT,
  SIGTERM) en el hilo principal. Si uvicorn corre en un hilo (pruebas, scripts)
  no hay señales, y el stream de un requisito en pausa dura hasta que el
  cliente se desconecta.
