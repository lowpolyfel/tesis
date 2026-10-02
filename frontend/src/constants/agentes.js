/* Los cuatro agentes del sistema y el mecanismo de divergencia (que no es agente) */
export const AGENTES = Object.freeze({
  extractor: {
    id: "extractor",
    nombre: "Extractor",
    rol: "Separa el vocabulario del dominio del requisito crudo",
    proveedor: "ollama",
  },
  clasificador: {
    id: "clasificador",
    nombre: "Clasificador",
    rol: "Genera interpretaciones candidatas de términos con más de una lectura",
    proveedor: "ollama",
  },
  critico: {
    id: "critico",
    nombre: "Crítico",
    rol: "Conduce el debate acotado y arbitra si se agotan las rondas",
    proveedor: "api",
  },
  modelador: {
    id: "modelador",
    nombre: "Modelador",
    rol: "Genera los artefactos desde la interpretación validada",
    proveedor: "ollama",
  },
});

export const ORDEN_AGENTES = ["extractor", "clasificador", "critico", "modelador"];

/* Lecturas en competencia: mismo color en tarjetas, debate y gráficas */
export const LECTURAS = Object.freeze({
  A: { etiqueta: "Lectura A", borde: "border-sky-400", fondo: "bg-sky-50", texto: "text-sky-800", solido: "bg-sky-500", trazo: "#0ea5e9" },
  B: { etiqueta: "Lectura B", borde: "border-amber-400", fondo: "bg-amber-50", texto: "text-amber-800", solido: "bg-amber-500", trazo: "#f59e0b" },
});

/* Clasificación de términos marcados en el texto */
export const TIPOS_AMBIGUEDAD = Object.freeze({
  mexicanismo: { etiqueta: "Mexicanismo", clase: "bg-amber-100 text-amber-900 decoration-amber-500" },
  vaguedad: { etiqueta: "Vaguedad", clase: "bg-violet-100 text-violet-900 decoration-violet-500" },
  polisemia: { etiqueta: "Polisemia", clase: "bg-sky-100 text-sky-900 decoration-sky-500" },
});

/* Tipos de símbolo del LEL */
export const TIPOS_LEL = ["sujeto", "objeto", "verbo", "estado"];
