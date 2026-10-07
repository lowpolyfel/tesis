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
| `clasificador_v2` | Clasificador | Igual que v1, más el tipo de ambigüedad (léxica, alcance, anafórica, sintáctica) y candidatos de los detectores |
| `clasificador_refinamiento_v1` | Clasificador | Refinar o retirar interpretaciones ante objeciones |
| `critico_v1` | Crítico | Evaluar R3 (R1 y R2 se evalúan en código) |
| `critico_arbitraje_v1` | Crítico | Elegir una interpretación al agotar las rondas |
| `modelador_v1` | Modelador | Entrada del LEL desde la interpretación validada (solo ambigüedad léxica) |
| `modelador_requisito_v1` | Modelador | Requisito reescrito sin ambigüedad y sus metas (modelo de metas KMoS-SSA) |
| `comparador_v1` | Comparador (fuera del núcleo) | Relación entre dos requisitos con citas; módulo exploratorio (ADR 0012) |
| `agente_unico_v1` | Línea base | Un solo agente que detecta, clasifica e interpreta, para la evaluación (ADR 0014) |
