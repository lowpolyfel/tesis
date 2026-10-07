# 0015. Vista por término y análisis de proyecto derivados de las trazas

- **Fecha:** 2026-10-06
- **Estado:** Aceptada

## Contexto

El frontend se diseñó con datos de prueba que suponían **una** divergencia por
requisito con dos interpretaciones fijas *A* y *B* (`similitudInicial`,
`interpretaciones: {A, B}`). El backend no trabaja así: la divergencia se mide
**por término** (ADR 0002), cada término tiene N interpretaciones `I1..In`, el
Clasificador puede refinarlas o retirarlas en cada ronda (ADR 0005) y hay
varios tipos de ambigüedad (ADR 0010). Toda esa información está en la traza,
pero como una secuencia de mensajes del protocolo (ADR 0001).

Si el frontend reconstruyera la vista leyendo los mensajes, el conocimiento del
protocolo quedaría duplicado en JavaScript, se rompería con cada cambio de
payload y no se podría probar contra trazas reales del grafo. Además, las
pantallas de proyecto (ambigüedades, flujo del ciclo KMoS-SSA) y las de
catálogo y calibración necesitan agregados que no existen en ningún documento.

## Decisión

1. **Paquete `app/analisis/`** con funciones **puras** sobre `Traza`, el
   documento de `formalizados` y el LEL del proyecto. No llaman a ningún LLM ni
   a los embeddings, ni leen el repositorio: las rutas leen y delegan. Se
   recalcula en cada petición; la traza sigue siendo la única fuente de verdad
   (ADR 0006).

2. **Vista por requisito** (`vista_requisito`, `GET /requisitos/{req_id}`):

   ```
   {req_id, proyecto_id, ciclo, texto, origen, estado, creado, actualizado,
    en_proceso, terminal,
    config: {umbral, max_rondas, modelos{extractor, clasificador, critico, modelador},
             modelo_embeddings, temperatura, semilla, significado_max_palabras,
             spacy_model, catalogos, persistencia, otros},
    transiciones: [{estado, secuencia, timestamp}],
    marcados: [{inicio, fin, texto, termino, decision_filtro, tipo, detalle, univoco}],
    extraccion: {terminos, descartados, modelo, prompt_version, intentos, duracion_ms} | null,
    terminos: [{termino, origen, detalle, categoria, univoco, tipo_ambiguedad,
                interpretaciones: [{id, significado, parafrasis_del_requisito,
                                    estado: vigente|retirada, retirada_en_ronda, motivo_retiro}],
                divergencia_inicial: {similitud, umbral, decision, pares, par_minimo,
                                      modelo_embeddings} | null,
                rondas: [{ronda, evaluadas, evaluaciones, objeciones,
                          refinamiento: {interpretaciones, retiradas, nota} | null,
                          similitud: {similitud, umbral, decision, pares, par_minimo} | null,
                          consenso: {motivo, similitud, umbral, propuesta} | null}],
                resolucion: {via, decision, propuesta, motivo, similitud_final,
                             arbitraje: {interpretacion_elegida, justificacion_por_regla} | null} | null,
                validacion: {final, cambio} | null,
                entrada_lel: {...EntradaLELFormalizada} | null}],
    resumen: {n_terminos, n_ambiguos, tipos{lexica, alcance, anaforica, sintactica},
              vaguedad[], regionales[], resueltos_por_lel[], estructuras, similitud_minima,
              via, rondas_max, n_errores},
    solicitud: payload de solicitud_validacion | null,
    validacion: {decision, comentario, terminos, timestamp} | null,
    formalizacion: documento de formalizados (o el mensaje con alcance requisito) | null,
    errores: [{secuencia, nodo, excepcion, mensaje, prompt_version}],
    n_mensajes, n_repetidos, ultima_secuencia}
   ```

   - `terminos` son los candidatos que pasaron al Clasificador (unívocos
     incluidos), uno por forma normalizada, como en el grafo. `en_proceso` es
     «no terminal y no `pendiente_validacion`».
   - `marcados.tipo` es el tipo de ambigüedad si el término tiene
     interpretaciones; si no, `vaguedad`, `lel` (resuelto por el LEL) o
     `regional`; `null` para unívocos o candidatos aún sin clasificar. `texto` es
     el tramo exacto del requisito.
   - Una interpretación refinada **conserva su id** y la vista muestra su última
     versión; cada ronda lleva además `evaluadas` (lo que el Crítico evaluó en esa
     ronda), porque las evaluaciones solo citan ids.
   - `resolucion`: aceptado directo → `motivo: umbral` y la primera
     interpretación; consenso → `umbral | una_interpretacion` y la primera
     vigente; arbitraje → `rondas_agotadas` y la elegida. Si existe la
     solicitud de validación, la `propuesta` es exactamente la que vio el humano.
     `null` mientras el término se debate.
   - `resumen.via` es la más fuerte entre términos (arbitraje > consenso >
     aceptado directo), coherente con el estado del requisito (ADR 0002 §4), y
     `similitud_minima` la mínima de las similitudes iniciales.

3. **Mensajes efectivos.** Un nodo que continúa tras un reinicio se reejecuta y
   repite sus mensajes (ADR 0008). Para la vista cuenta el **último** mensaje de
   cada clave (`tipo`, `ronda`, término normalizado; `extraccion`, `filtrado`,
   `interpretaciones`, `solicitud_validacion` y `validacion` son únicos por
   requisito), que es el que quedó en el estado del grafo; las similitudes
   iniciales anteriores a la última clasificación se descartan; los errores
   nunca. La traza no se toca y `n_repetidos` dice cuántos se descartaron.

4. **Tolerancia.** Trazas en proceso (campos `null` o listas vacías), en error,
   anteriores al tipo de ambigüedad (se tratan como léxicas, ADR 0010 §5), con
   `formalizacion` sin `alcance` (anteriores al ADR 0010) y con configuración sin
   catálogos ni persistencia.

5. **Resumen ligero** (`resumen_requisito`) para listas: `{req_id, proyecto_id,
   ciclo, texto, origen, estado, creado, actualizado, similitud_minima, via,
   rondas_max, n_ambiguos, tipos, vaguedad, en_proceso}`.

6. **Proyecto** (`GET /proyectos/{id}/resumen | ambiguedades | flujo`):
   - *Resumen:* contadores, estados por ciclo y el resumen de cada requisito.
   - *Ambigüedades:* agrupadas por término normalizado; una aparición es un
     término con interpretaciones o uno que los filtros dieron por
     `resuelto_por_lel` (la memoria funcionando). Un grupo es **inconsistente** si
     el humano aprobó significados distintos en requisitos distintos, o si el LEL
     del proyecto tiene entradas del mismo símbolo con nociones distintas. Es
     justo lo que pasa cuando dos requisitos de un mismo lote se debaten antes de
     que el primero entre al LEL. Más listas de vaguedad, regionales y
     estructuras (alcance, anáfora) y totales por tipo y por vía.
   - *Flujo:* métricas por ciclo y del proyecto según las fases de CONTEXTO §5:

     | Fase | Mensajes que cuenta | Entra al pasar por |
     |---|---|---|
     | 1 Enriquecimiento (Extractor + filtros) | `extraccion`, `filtrado` | `extraido` |
     | 2 Generación (Clasificador) | `interpretaciones` | `interpretado` |
     | 3 Discusión (divergencia, Crítico, refinamiento) | `similitud`, `objecion`, `refinamiento`, `consenso`, `arbitraje` | `aceptado_directo`, `en_debate`, `consenso`, `arbitrado` |
     | 4 Validación (humano) | `solicitud_validacion`, `validacion` | `pendiente_validacion` |
     | 5 Enriquecimiento, cierre (Modelador) | `formalizacion` | `formalizado` |

     `debates`, `consensos`, `arbitrajes`, `directos`, `validados`, `rechazados` y
     `formalizados` cuentan requisitos que pasaron por ese estado; los mensajes se
     cuentan sin repetidos.

7. **Formas como contrato.** `app/analisis/formas.py` declara cada forma con
   Pydantic (`extra="forbid"`); las rutas las usan como `response_model` (quedan
   en `/docs`) y las pruebas validan contra ellas la salida de las funciones
   puras. Lo que viene tal cual de un payload (evaluaciones del Crítico, metas,
   entradas del LEL) se declara como `dict` para no duplicar los contratos.

8. **Configuración y catálogos de solo lectura.** `GET /configuracion` devuelve
   la configuración que copiaría una traza nueva (mismos nombres que
   `vista.config`) más el proveedor del Crítico, los modelos auxiliares, la
   rejilla de calibración y los umbrales de comparación, con la nota «se cambia
   en .env; cada traza guarda la suya». `GET /catalogos` devuelve los JSON de
   catálogos tal cual están en disco, con sus versiones. No se editan desde la
   interfaz: cambiar un parámetro a mitad de un experimento rompería la
   reproducibilidad, y cada traza ya guarda lo que usó.

## Alternativas consideradas

- **Reconstruir la vista en el frontend:** duplica el protocolo en otro
  lenguaje, sin pruebas contra trazas reales; es lo que produjo la brecha A/B.
- **Materializar la vista en la base al terminar cada nodo:** segunda fuente de
  verdad que habría que migrar con cada cambio y que no existe para las trazas
  anteriores. Con el volumen de la tesis, recalcular es barato.
- **Conservar la forma A/B** (dos interpretaciones por requisito): pierde `I3..In`,
  los varios términos por requisito y las interpretaciones retiradas.
- **Detectar inconsistencias con embeddings:** toleraría paráfrasis, pero haría
  la vista dependiente de Ollama y no determinista; se prefirió la comparación
  literal y dejar el juicio al humano.
- **Mostrar todos los mensajes, incluidos los repetidos:** la vista mostraría
  rondas duplicadas que nunca ocurrieron en el estado del grafo.

## Consecuencias

- Cada petición recorre la traza completa; las rutas de proyecto leen todas las
  trazas del proyecto. Sirve para decenas o cientos de requisitos (la tesis usa
  15–25), no para miles: no hay caché.
- `extraccion.duracion_ms` se mide desde la transición `cargado`: incluye la
  espera en la cola y, tras un reinicio, el tiempo caído; es una cota superior.
  `duracion_s` de un ciclo incluye la espera de la validación humana.
- La inconsistencia se juzga por comparación literal (minúsculas, sin acentos):
  «periodo de uso» y «periodo de uso del sistema» cuentan como distintos (falso
  positivo posible); los símbolos se agrupan por forma normalizada, no por lema.
- El símbolo del LEL de un término `resuelto_por_lel` se toma del `detalle` que
  escriben los filtros («símbolo del LEL: …»); si ese texto cambia, se usa el
  propio término.
- La deduplicación supone que un nodo reejecutado procesa los mismos términos,
  lo que se cumple porque continúa desde el mismo checkpoint.
- En un rechazo, cada término conserva su `validacion {final, cambio}` (el grafo
  lo registra igual); la decisión está en `validacion.decision` del requisito, y
  en las ambigüedades `interpretacion_final` solo cuenta si se aprobó.
- Un requisito sin términos ambiguos cuenta como `directo` en el flujo: pasa por
  `aceptado_directo` (ADR 0005 §8). El Clasificador aparece en las fases 2 y 3.
- Un tipo de mensaje nuevo aparece solo en los conteos por tipo del flujo; para
  que entre a la vista hay que tocar este módulo y sus formas.
