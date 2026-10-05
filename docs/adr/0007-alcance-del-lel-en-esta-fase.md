# 0007. Alcance del LEL: solo términos resueltos

- **Fecha:** 2026-10-05
- **Estado:** Aceptada para esta fase — **pendiente de revisar con la asesora**
  (Dra. Karla Olmos Sánchez)

## Contexto

El LEL cumple dos papeles: es el producto formalizado (símbolo, tipo, noción,
impacto) y es la **memoria** que usan los filtros (un término ya validado no se
vuelve a debatir) y el vocabulario permitido de la regla R1 del Crítico. El
Clasificador puede marcar un término como unívoco. Había que decidir si esos
términos también se formalizan.

## Decisión

1. **Solo entran al LEL los términos resueltos**: los que tuvieron
   interpretaciones y llegaron por `aceptado_directo`, `consenso` o `arbitraje`,
   y que el humano aprobó (con o sin edición).
2. **Los unívocos se registran en la traza** (`univoco: true` en el mensaje
   `interpretaciones`, y la lista `univocos` en `solicitud_validacion` y
   `formalizacion`), pero **no se formalizan**.
3. **Un requisito sin ambigüedad** pasa igual por `pendiente_validacion` y llega
   a `formalizado` sin entradas nuevas; el mensaje `formalizacion` lo dice.
4. Cada entrada guarda de dónde vino: `req_id`, `termino`, `via`, la
   interpretación validada y `editada_por_humano`.
5. La memoria compara contra el `simbolo` de cada entrada (forma normalizada o
   secuencia de lemas, ADR 0003).

## Justificación

Si los unívocos entraran sin validación humana, ampliarían el vocabulario que R1
acepta como conocido y la debilitarían: cualquier palabra marcada unívoca una
vez quedaría permitida en todas las paráfrasis siguientes.

## Alternativas consideradas

- **Formalizar también los unívocos:** LEL más completo, R1 más débil y entradas
  sin noción debatida.
- **Formalizarlos con una marca `no_validado`:** complica la memoria (¿cuenta o
  no cuenta?) sin una decisión metodológica que la respalde.

## Consecuencias

- El LEL crece más despacio y solo con términos que pasaron por el método.
- Si la asesora decide incluir los unívocos, el cambio está acotado al nodo
  `formalizado` y a cómo se construye el vocabulario de R1.
