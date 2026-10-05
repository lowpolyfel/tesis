# 0003. Filtros deterministas antes del Clasificador

- **Fecha:** 2026-10-05
- **Estado:** Aceptada

## Contexto

No todo lo que el Extractor separa debe llegar al Clasificador. La taxonomía del
proyecto (CONTEXTO §6) distingue la **vaguedad**, que no produce dos
interpretaciones discretas y no se debate, de la ambigüedad léxica, de alcance y
anafórica, que sí. Además, el LEL es la **memoria** del sistema: un término ya
debatido y validado no se vuelve a debatir. Y los términos regionales (*jalar*,
*checar*, *dar de alta*) deben llegar siempre al Clasificador aunque el modelo
no los considere relevantes.

## Decisión

1. **Precedencia por término:** `resuelto_por_lel` > `vaguedad` > `regional` >
   `candidato`. Solo `regional` y `candidato` pasan al Clasificador.
2. **Los catálogos se buscan en todo el texto,** no solo entre los términos que
   devolvió el Extractor. Si el LLM omite *ahorita*, el catálogo lo recupera; el
   término se marca con "detectado por catálogo, no por el Extractor".
3. **Detección con `PhraseMatcher` de spaCy en dos capas:**
   - `LOWER` con las `formas` declaradas en el catálogo (con y sin acento).
   - `LEMMA` con la expresión canónica, para flexiones de frases multipalabra
     (*da de alta*, *dé de alta*).
   Si dos coincidencias se solapan gana la más larga.
4. **LEL como memoria:** un término coincide con un símbolo del LEL por forma
   normalizada (minúsculas, sin acentos) o por secuencia de lemas (*sesiones* →
   *sesión*). Las entradas del LEL solo existen si un humano las validó (ADR 0007).
5. **Mensaje propio:** el resultado se registra como mensaje `filtrado`
   (`emisor: filtros`) con `decision_filtro` y el detalle por término.
6. **Catálogos en JSON versionado** (`data/catalogos/regionales.json` y
   `vaguedad.json`), con la versión registrada en la traza. *Ahorita* está en
   vaguedad aunque sea mexicanismo: marca un límite temporal impreciso.

## Justificación

Hallazgo al implementar: el lematizador de `es_core_news_sm` falla justo con las
formas regionales (*jale* → *jalir*; *jala* se etiqueta como preposición;
*ahorita* aislado → *ahoritar*). Por eso las formas se declaran explícitamente y
el lema solo complementa. Que los filtros sean deterministas los hace
reproducibles y evita debatir lo que no tiene dos interpretaciones.

## Alternativas consideradas

- Solo lemas: no detecta *jale* ni *jala*.
- Dejar que el LLM decida qué es vago o regional: no es reproducible y es
  justamente lo que el catálogo debe garantizar.
- Debatir los términos del LEL de nuevo: contradice el papel del LEL como memoria.

## Consecuencias

- Agregar un término regional o vago requiere declarar sus formas flexionadas.
- Un término de vaguedad no se resuelve: se marca y se muestra al humano en la
  validación para que decida si pedir una métrica.
