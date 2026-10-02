# agents

Los cuatro agentes basados en LLM, cada uno en su propio paquete:

| Agente | Responsabilidad | LLM |
|---|---|---|
| `extractor/` | Separa el vocabulario del dominio del requisito crudo | Ollama local |
| `clasificador/` | Genera interpretaciones candidatas de términos con más de una lectura | Ollama local |
| `critico/` | Conduce el debate acotado y arbitra si se agotan las rondas | API externa |
| `modelador/` | Genera los artefactos a partir de la interpretación validada | Ollama local |

Los prompts de los agentes no van aquí; se cargan desde `app/prompts/`.
