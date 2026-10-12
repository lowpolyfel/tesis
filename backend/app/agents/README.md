# agents

Los agentes basados en LLM, cada uno en su propio paquete:

| Agente | Responsabilidad | LLM |
|---|---|---|
| `extractor/` | Separa el vocabulario del dominio del requisito crudo | Ollama local |
| `clasificador/` | Genera interpretaciones candidatas de los términos que admiten más de una interpretación | Ollama local |
| `critico/` | Conduce el debate acotado y arbitra si se agotan las rondas | API externa |
| `modelador/` | Genera los artefactos a partir de la interpretación validada | Ollama local |
| `revisor/` | Arma la ficha del contexto y hace el triaje de los requisitos antes de analizarlos (ADR 0022) | Ollama local |

Los prompts de los agentes no van aquí; se cargan desde `app/prompts/`.

Cada cuenta puede elegir el proveedor y el modelo de cada agente en Configuración (ADR 0021):
los agentes reciben un `ClienteDinamico` que usa la elección de quien analiza o, si no eligió, la del `.env`.
