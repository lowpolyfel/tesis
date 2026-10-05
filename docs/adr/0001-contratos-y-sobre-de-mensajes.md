# 0001. Contratos de los agentes y sobre común de mensajes

- **Fecha:** 2026-10-05
- **Estado:** Aceptada

## Contexto

El NFR central del sistema es la **trazabilidad**: cualquier debate debe poder
reconstruirse después (KMoS-SSA exige un punto explícito de revisión humana).
Además, los evaluadores pidieron que la función de cada agente quede clara; la
respuesta es el contrato de cada uno, no más prosa.

## Decisión

1. **Contratos Pydantic primero** (`backend/app/models/`). Ningún agente devuelve
   texto libre: la salida del LLM se valida contra su modelo. Si no valida, se
   reintenta **una vez** con el error de validación en el prompt; si vuelve a
   fallar, se registra un mensaje `error` con las dos salidas crudas y el
   requisito pasa al estado `error`.
2. **Lo que pide el LLM vs. lo que calcula el código.** Los modelos `*LLM` son lo
   único que se le pide al modelo. Lo determinista lo hace el código:
   - La `posicion` de cada término la calcula el código buscando el término en el
     texto. Si el término no aparece literal, se descarta y se registra. No se
     confía en offsets producidos por un LLM.
   - En el Crítico, el LLM solo juzga R3; R1 y R2 se evalúan en código (ADR 0004).
   - En el Modelador, metas y Big Picture son un stub JSON generado en código.
3. **Un concepto, un nombre.** El campo que la especificación llamaba `lectura`
   se llama `significado`: el sentido que una **interpretación** le da al término.
   El código nunca usa *lectura*, *visión* ni *postura*.
4. **Sobre común** (`Mensaje`): `req_id`, `secuencia`, `ronda`, `emisor`,
   `receptor`, `tipo`, `payload`, `modelo`, `prompt_version`, `timestamp`. Cada
   mensaje se agrega a la traza del requisito en el momento en que se emite.
5. **Enum `tipo` cerrado y controlado.** `extraccion`, `filtrado`,
   `interpretaciones`, `similitud`, `objecion`, `refinamiento`, `consenso`,
   `arbitraje`, `solicitud_validacion`, `validacion`, `formalizacion`, `error`.
   Se agregó `filtrado` a la lista original: los filtros deterministas son un
   paso distinto de la extracción y no se fuerzan dentro de `extraccion`
   ("cerrado significa controlado, no congelado"). Su mensaje lleva
   `emisor: filtros` y un `decision_filtro` por término.
6. **Estado `error`.** No forma parte del flujo normal de la máquina de estados;
   marca los casos en que un agente no produjo salida válida tras el reintento.

## Justificación

Los contratos convierten la función de cada agente en algo verificable y
testeable con LLM falsos. Separar lo que decide el LLM de lo que calcula el
código hace que la parte determinista sea reproducible y defendible.

## Alternativas consideradas

- `with_structured_output` de LangChain: oculta la salida cruda cuando falla. Se
  prefirió pedir JSON con el esquema (`format` de Ollama) y validar con Pydantic,
  para poder guardar en la traza exactamente qué devolvió el modelo.
- Registrar los filtros como `extraccion` con un campo extra: mezclaba dos
  conceptos en un nombre.

## Consecuencias

- Agregar un tipo de mensaje requiere tocar el enum y este ADR.
- Los términos que el LLM del Extractor devuelve y no aparecen literalmente en el
  texto se pierden (quedan registrados como descartados en la traza).
