# prompts

Plantillas versionadas `<agente>_v<N>.txt`. Son parte del método: el Capítulo 4 debe
poder decir qué prompt produjo qué resultado, y cada mensaje de la traza registra
la `prompt_version` usada.

Formato: secciones `### SISTEMA` y `### USUARIO`; variables como `${nombre}`.
Una modificación de fondo crea una versión nueva (`_v2`) en lugar de editar la vigente.

| Archivo | Agente | Uso |
|---|---|---|
| `extractor_v1` | Extractor | Separar el vocabulario del dominio |
| `clasificador_v1` | Clasificador | Generar interpretaciones candidatas o marcar unívoco (ya no se usa; se conserva para reproducir corridas anteriores) |
| `clasificador_v2` | Clasificador | Igual que v1, más el tipo de ambigüedad (léxica, alcance, anafórica, sintáctica) y candidatos de los detectores (se conserva para reproducir corridas anteriores) |
| `clasificador_v3` | Clasificador | Igual que v2, más el contexto general del proyecto: una interpretación ajena al dominio no cuenta (ADR 0017) |
| `clasificador_refinamiento_v1` | Clasificador | Refinar o retirar interpretaciones ante objeciones |
| `critico_v1` | Crítico | Evaluar R3 (R1 y R2 se evalúan en código) |
| `critico_arbitraje_v1` | Crítico | Elegir una interpretación al agotar las rondas (se conserva para reproducir corridas anteriores) |
| `critico_arbitraje_v2` | Crítico | Igual que v1; si las reglas no distinguen, decide el contexto del proyecto (ADR 0017) |
| `modelador_v1` | Modelador | Entrada del LEL desde la interpretación validada (solo ambigüedad léxica; se conserva para reproducir corridas anteriores) |
| `modelador_v2` | Modelador | Igual que v1, nombrando las cosas como en el dominio del proyecto (ADR 0017) |
| `modelador_requisito_v1` | Modelador | Requisito reescrito sin ambigüedad y sus metas (modelo de metas KMoS-SSA; se conserva para reproducir corridas anteriores) |
| `modelador_requisito_v2` | Modelador | Requisito reescrito completo con el contexto del proyecto (lo vago y lo regional se concreta y se anota como supuesto), funcional o no funcional con su categoría, y sus metas (ADR 0017) |
| `modelador_mapa_v1` | Modelador | Organiza el mapa conceptual del proyecto: elige entre los conceptos candidatos que preparó el código, los agrupa en ramas y nombra las relaciones (ADR 0020) |
| `revisor_ficha_v1` | Revisor | Ordena el contexto general del proyecto en una ficha: actores, conceptos, procesos, reglas, fuera de alcance y vacíos (ADR 0022) |
| `revisor_triaje_v1` | Revisor | Compara requisitos con la ficha: claro, ambiguo o incompleto, con motivo, faltantes y preguntas (ADR 0022) |
| `revisor_separacion_v1` | Revisor | Reconoce los requisitos de un texto pegado o de un documento en cualquier redacción, copiándolos de sus párrafos (ADR 0023) |
| `revisor_entrevista_v1` | Revisor | Versión 2: la ficha de una parte de la entrevista — participantes, objetivo, problemas, necesidades y reglas, con sus turnos (ADR 0024) |
| `extractor_entrevista_v1` | Extractor | Versión 2: los términos del dominio de una parte de la entrevista, copiados como aparecen (ADR 0024) |
| `clasificador_intencion_v1` | Clasificador | Versión 2: la intención de cada término (significado, qué quiere lograr quien lo usa y una cita reescrita); varias si admite más de una interpretación, con los acuerdos del proyecto (ADR 0024) |
| `clasificador_refinamiento_entrevista_v1` | Clasificador | Versión 2: refinar o retirar intenciones ante las objeciones, sobre las citas de la entrevista |
| `critico_entrevista_v1` | Crítico | Versión 2: evaluar R3 de las intenciones (R1 y R2 en código, con las citas como texto) |
| `critico_arbitraje_entrevista_v1` | Crítico | Versión 2: elegir la intención al agotar las rondas |
| `modelador_lexico_v1` | Modelador | Versión 2: las entradas del LEL de los términos de una entrevista, con la intención acordada |
| `modelador_mapa_proposito_v1` | Modelador | Versión 2: el mapa conceptual con su pregunta de enfoque, desde el LEL validado |
| `modelador_metas_v1` | Modelador | Versión 2: metas de la organización, estratégicas y específicas, con símbolos y citas |
| `modelador_requisitos_v1` | Modelador | Versión 2: los requisitos de una meta estratégica, con metas, símbolos, citas, criterios y supuestos |
| `comparador_v1` | Comparador (fuera del núcleo) | Relación entre dos requisitos con citas; módulo exploratorio (ADR 0012) |
| `agente_unico_v1` | Línea base | Un solo agente que detecta, clasifica e interpreta, para la evaluación (ADR 0014) |
