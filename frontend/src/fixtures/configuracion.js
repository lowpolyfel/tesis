/* Parámetros calibrables (equivalen a SIMILARITY_THRESHOLD y MAX_DEBATE_ROUNDS del backend) */
export const configuracionInicial = {
  umbral: 0.75,
  maxRondas: 2,
  modeloEmbeddings: "nomic-embed-text",
  modelos: {
    extractor: "llama3.1:8b",
    clasificador: "llama3.1:8b",
    critico: "claude-sonnet-5-5",
    modelador: "qwen2.5:7b",
  },
};

export const modelosDisponibles = {
  ollama: ["llama3.1:8b", "llama3.2:3b", "qwen2.5:7b", "qwen2.5:14b", "mistral:7b", "gemma2:9b"],
  api: ["claude-sonnet-5-5", "claude-haiku-4-5", "gpt-4.1"],
  embeddings: ["nomic-embed-text", "mxbai-embed-large", "bge-m3"],
};
