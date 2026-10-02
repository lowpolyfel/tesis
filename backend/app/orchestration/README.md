# orchestration

Flujo de LangGraph que conecta a los agentes:

- Grafo: Extractor → Clasificador → evaluación de divergencia → (Crítico, si hay
  divergencia) → Modelador.
- Estado compartido: lo que viaja entre nodos (requisito, extracción, interpretaciones,
  debate, artefactos).
- Nodos: envoltorios que llaman a cada agente y al módulo de divergencia.
