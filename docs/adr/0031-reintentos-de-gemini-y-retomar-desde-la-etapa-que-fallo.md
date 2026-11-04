# 0031. Reintentos de Gemini y retomar desde la etapa que falló

- **Fecha:** 2026-11-04
- **Estado:** Aceptada

## Contexto

Publicado en Render con Google AI Studio (sin Ollama), el análisis de una entrevista se caía
con «Google Gemini respondió 503». En el nivel gratuito, Gemini responde 503 UNAVAILABLE cuando
el modelo está saturado y 429 RESOURCE_EXHAUSTED cuando se acaba la cuota. Los dos son
pasajeros. Había tres problemas:

1. **No había reintentos.** El reintento de `estructurado.generar` es por JSON inválido, no
   por errores del servicio.
2. **«Volver a procesar» empezaba de cero.** Repetía las llamadas de las etapas que ya habían
   salido bien, y con ellas la probabilidad de otro 503 y el gasto de cuota.
3. **La pantalla mostraba el error tal cual.** El endpoint compatible con OpenAI de Gemini
   manda el error dentro de una lista JSON, y eso aparecía en la pantalla.

## Decisión

### 1. Reintentos solo para 503 y 429, con espera exponencial y jitter

`ClienteCompatibleOpenAI` reintenta, solo para Google, hasta `GEMINI_REINTENTOS` veces (5 por
omisión y como máximo). Solo reintenta ante 503/UNAVAILABLE o 429/RESOURCE_EXHAUSTED, ya sea
por el código HTTP o por el `status` del cuerpo.

**La espera** antes del reintento k es `min(tope, base·2^k)`, con jitter «igual»: la mitad fija
y la otra mitad al azar. Si el servicio manda `Retry-After`, se respeta, también con el tope.
Los valores por omisión son base 1 s y tope 30 s.

**Lo demás no se reintenta** (400, 401, 404, 500…): esperar no lo arregla. Los embeddings de
Gemini usan la misma función `con_reintentos`.

### 2. Un modelo de respaldo, una vez, y queda registrado

Si los reintentos se agotan y hay `GEMINI_FALLBACK_MODEL`, se intenta una sola vez con ese
modelo.

**Qué modelo respondió.** El cliente registra el modelo que de verdad respondió (`ultimo_uso`),
y `Respuesta` lo trae en `modelo`, con `respaldo` (el modelo que se reemplazó) y
`reintentos`. Esto queda guardado en tres lugares:

- **La entrevista:** `modelos_usados` (por corrida y agente) y `respaldos`.
- **Los mensajes de la bitácora:** `modelo_respaldo` y `reintentos_proveedor`.
- **Los documentos de mapa, metas y requisitos.**

**Dónde no hay respaldo:**

- **La prueba de modelos y «Probar» en Configuración** (`con_respaldo=False`): miden un modelo
  concreto, y un respaldo silencioso contaminaría la comparación.
- **Los embeddings:** otro modelo cambiaría las similitudes a media corrida.

### 3. La salida de cada etapa, en Mongo; «Volver a procesar» entra por la que falló

El decorador `@nodo` del grafo de la entrevista guarda en `etapas_entrevista` (un documento
por entrevista) qué etapa está en curso y, al terminar cada nodo, el estado completo del grafo
(`salidas[nodo]`). Si un nodo falla, se registra `fallo`.

**Retomar.** `reprocesar` busca la etapa en curso o fallida y la salida de la anterior, y
arranca una corrida nueva con ese estado y `reanudar_en`. Para eso, el grafo entra por una
arista condicional desde `START`, que por omisión va a `cargada`.

**La bitácora** conserva los mensajes de las etapas que salieron bien (sin los de error), para
que la escena cuente la historia completa.

**El LEL.** Lo propuesto y no validado se quita igual que antes, porque la etapa del Modelador
lo vuelve a escribir.

**Empezar de cero.** `desde_cero=true` («o desde el principio») sigue disponible. También se
empieza de cero si no hay salida guardada; por ejemplo, si se canceló antes de terminar
`cargada`.

**Mapa, metas y requisitos.** Cada uno es su propio documento y lo de atrás ya estaba
guardado. Un intento fallido se registra en `fallos_fase`, la pantalla lo dice, y «Volver a
generar» retoma en esa fase.

### 4. Errores legibles

**En el backend:** `_detalle` entiende la forma de lista de Google. El mensaje final queda
como «Google Gemini respondió 503 tras 5 reintento(s): The model is overloaded… (UNAVAILABLE)».

**En el frontend:** `services/errores.js` reconoce 503 y 429 y los cambia por una frase que
dice qué pasó, que lo hecho quedó guardado y desde dónde se retoma. El texto técnico queda
plegado.

## Alternativas consideradas

- **Reintentar en `estructurado.generar`:** mezclaría dos fallas distintas, el JSON inválido
  (que sí cambia al repetir con el error en el prompt) y el servicio caído.
- **Retomar con el checkpoint de LangGraph:** el nodo que falla no lanza la excepción, la
  convierte en `fallo` y el grafo termina en `error`. Ese checkpoint queda al final, no antes
  del nodo. Guardar la salida de cada etapa en Mongo es explícito, se puede inspeccionar y
  sobrevive aunque se borre el checkpoint.
- **Respaldo también en la prueba de modelos:** se descarta, porque la prueba mide un modelo.

## Consecuencias

- Un 503 que dura menos de un minuto ya no tira el análisis: cinco reintentos esperan en
  total unos 15 a 30 s.
- **La cola es de un solo trabajador:** mientras se reintenta, el resto espera.
- Una corrida que usó el modelo de respaldo lo dice en la entrevista, en la bitácora y en
  los documentos de las fases. Si se citan resultados, hay que revisarlo.
- La versión pasa a **2.6.0**.
