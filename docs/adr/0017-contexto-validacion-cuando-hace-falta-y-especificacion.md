# 0017. Contexto del proyecto, validación solo cuando hace falta y especificación funcional / no funcional

- **Fecha:** 2026-10-07
- **Estado:** Aceptada

## Contexto

Al usar el prototipo de punta a punta aparecieron tres problemas de método:

1. **Cada requisito se leía aislado.** «Ahorita» o «checar», solos, no dicen
   nada; dentro de un dominio («el ticket se imprime al cobrar», «checar
   existencias es verificarlas en el almacén») se entienden. Sin ese contexto el
   Clasificador generaba interpretaciones que no caben en el dominio y el
   Modelador, por regla, no podía concretar lo vago («no inventes una métrica»).
2. **Una persona tenía que validar cada requisito**, aunque los agentes
   hubieran coincidido desde el principio. El flujo esperado era otro: se pegan
   los requisitos, se analizan y, si no hay conflicto, pasan solos al LEL y al
   modelo de metas; la persona interviene solo cuando hace falta y puede corregir
   cualquier resultado después.
3. **La salida no era una especificación.** El requisito reescrito repetía el
   original si no había ambigüedad y no se distinguía lo funcional de lo no
   funcional; el Big Picture solo se podía armar con todo el proyecto.

## Decisión

1. **Contexto general por proyecto** (`Proyecto.contexto`, hasta 4000
   caracteres). Al registrar un requisito, la traza guarda una copia
   (`config.contexto_proyecto`): es el que reciben los agentes aunque después se
   edite. Lo reciben el Clasificador (`clasificador_v3`: una interpretación que no
   cabe en el dominio no cuenta), el Crítico al arbitrar (`critico_arbitraje_v2`:
   si las reglas no distinguen, decide el contexto) y el Modelador
   (`modelador_v2`, `modelador_requisito_v2`). El Extractor y la evaluación R3 no
   cambian. Las versiones anteriores de los prompts se conservan.
2. **Validación humana solo cuando hace falta** (`VALIDACION_HUMANA`):
   - `si_hay_arbitraje` (por omisión): el grafo se detiene en
     `pendiente_validacion` solo si algún término se resolvió por arbitraje, es
     decir, si los agentes agotaron las rondas sin consenso. Lo demás pasa por el
     nodo `validacion_automatica`, que aprueba la propuesta sin cambios y lo
     registra como un mensaje `validacion` del sistema (`automatica: true`,
     `motivo`: `sin_ambiguedad` | `sin_arbitraje`), y sigue a `validado` →
     `formalizado`.
   - `siempre`: el flujo anterior. `nunca`: todo se aprueba solo
     (`motivo: validacion_desactivada`).
   - Los proyectos de evaluación se detienen siempre antes de validar (ADR 0014):
     se evalúa lo que propone el sistema, sin gastar al Modelador.
3. **Requisitos completos, funcionales o no funcionales.** El Modelador reescribe
   el requisito completo (quién, qué, sobre qué, en qué condición) con las
   interpretaciones resueltas y el contexto; sustituye lo vago y lo regional por
   términos precisos y anota en `supuestos` todo lo que concretó a partir del
   contexto y no del texto. Clasifica el requisito (`tipo_requisito`:
   `funcional` | `no_funcional`) y, si es no funcional, su categoría (ISO/IEC
   25010 más `legal`). `GET /proyectos/{id}/especificacion` arma la lista RF/RNF
   numerada y el glosario (LEL), sin LLM.
4. **Cualquier resultado se puede corregir** después de formalizado:
   `PATCH /requisitos/{id}/formalizacion` (texto, tipo, categoría, supuestos) y
   `PATCH /requisitos/{id}/lel/{termino}` (símbolo, tipo, noción, impacto). Cada
   corrección queda en la traza como un mensaje `edicion` (humano → sistema) con
   lo de antes y lo de después; el documento lleva `corregido` y la entrada del
   LEL `corregida` (fecha). Una entrada del LEL corregida es la que usan los
   requisitos que se procesen después (es la memoria).
5. **Big Picture de los requisitos elegidos**: `?req_ids=` en
   `/proyectos/{id}/big-picture`, `/metas` y `/especificacion`. El grafo se arma
   con esos requisitos y solo con los símbolos del LEL que ellos usan, resuelven
   o mencionan.

## Justificación

- KMoS-SSA pide un punto explícito de revisión humana (fase 4). Se conserva,
  pero donde aporta: cuando la discusión del modelo (fase 3) no cerró. Si los
  agentes coincidieron (similitud ≥ umbral) o llegaron a consenso, pedirle a una
  persona que confirme cada caso convierte la herramienta en un formulario. La
  persona sigue teniendo la última palabra: puede corregir cualquier resultado y
  cada corrección queda en la traza (el NFR de trazabilidad).
- El contexto no vuelve consultable la ambigüedad pragmática en general (sigue
  fuera, CONTEXTO §6): es un texto que la persona escribe una vez por dominio y
  que los agentes leen igual que el LEL, como conocimiento del dominio.
- Concretar lo vago sin decirlo sería inventar. Los `supuestos` hacen visible
  cada decisión que no viene del texto, y la persona la confirma o la corrige.

## Alternativas consideradas

- **Validar solo lo que tiene términos ambiguos.** Seguía pidiendo revisión de
  casos en los que los agentes coincidieron sin debate (aceptado directo).
- **Pausar también por vaguedad.** Con el contexto y los supuestos a la vista, una
  pausa por cada «rápido» volvía al problema original.
- **Contexto como entrada del LEL.** El LEL es por término; el contexto describe
  el dominio entero y no tiene símbolo.
- **Recortar el Big Picture en el frontend.** Mermaid y PlantUML se generan en el
  backend; recortar ahí mantiene una sola fuente.

## Consecuencias

- La máquina de estados gana las transiciones `aceptado_directo | consenso |
  arbitrado → validado` (validación automática). El grafo tiene un nodo más que
  no es estado (`validacion_automatica`), como `humano`.
- Las pruebas que recorren el flujo con validación fijan `validacion_humana=
  "siempre"`; las de la validación automática lo cambian. `scripts/
  casos_aceptacion.py` también fija `siempre` (observa hasta la validación).
- Los documentos formalizados antes de esta decisión no traen `tipo_requisito`:
  la especificación los muestra «sin clasificar» y la persona elige su tipo con
  una corrección.
- La validación ya no prueba que una persona leyó cada requisito. Para la
  evaluación con participantes, `VALIDACION_HUMANA=siempre` recupera el flujo
  anterior; cada traza registra el modo con que se procesó.
