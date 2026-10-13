/*
 * Versión 2 (ADR 0024): las fases de un proyecto, de la entrevista a los requisitos.
 * Cada fase tiene su tono: la esfera lo toma al entrar a la fase, y el camino del
 * proyecto lo usa en su punto.
 */
export const FASES = Object.freeze([
  { id: "entrevista", nombre: "Entrevista", que: "Lo que dijo el cliente", mood: "entrevista", tono: "#ffb4a2" },
  { id: "lexico", nombre: "Léxico", que: "Cada término y su intención", mood: "extractor", tono: "#41efff" },
  { id: "mapa", nombre: "Mapa conceptual", que: "Los conceptos y cómo se relacionan", mood: "mapa", tono: "#34d3be" },
  { id: "metas", nombre: "Metas", que: "Organización, estrategia y metas específicas", mood: "metas", tono: "#ffd166" },
  { id: "requisitos", nombre: "Requisitos", que: "Lo que debe hacer el sistema", mood: "modelador", tono: "#57f7a7" },
]);
export const fase = (id) => FASES.find((f) => f.id === id) ?? FASES[0];
/* La sección de la esfera de cada fase (components/orb/secciones.js) */
export const seccionDeFase = (id) => (id === "requisitos" ? "fase_requisitos" : fase(id).id);

/* Estados de una entrevista (app/entrevistas/almacen.py) dichos para una persona */
export const ESTADO_ENTREVISTA = Object.freeze({
  cargada: { texto: "En cola", tono: "#94a3b8", trabajando: true },
  leida: { texto: "Leyendo", tono: "#41efff", trabajando: true },
  extraida: { texto: "Buscando términos", tono: "#41efff", trabajando: true },
  interpretada: { texto: "Interpretando", tono: "#a99bff", trabajando: true },
  en_debate: { texto: "Debatiendo", tono: "#ffc457", trabajando: true },
  arbitrada: { texto: "Formalizando", tono: "#57f7a7", trabajando: true },
  lista: { texto: "Lista", tono: "#57f7a7", trabajando: false },
  error: { texto: "Con error", tono: "#ff7b88", trabajando: false },
  cancelada: { texto: "Cancelada", tono: "#94a3b8", trabajando: false },
});
export const estadoEntrevista = (e) => ESTADO_ENTREVISTA[e] ?? { texto: e ?? "—", tono: "#94a3b8", trabajando: false };
export const TERMINALES_ENTREVISTA = ["lista", "error", "cancelada"];

/* Estados de un término del LEL interactivo */
export const ESTADO_TERMINO = Object.freeze({
  propuesto: { texto: "Por validar", tono: "#ffc457" },
  validado: { texto: "Validado", tono: "#57f7a7" },
  corregido: { texto: "Corregido por ti", tono: "#f9a8d4" },
  descartado: { texto: "Descartado", tono: "#94a3b8" },
});

/* Cómo llegaron los agentes a la intención que proponen */
export const VIA_TERMINO = Object.freeze({
  univoco: "Una sola intención posible",
  aceptado_directo: "Sus intenciones se parecían: sin debate",
  consenso: "Los agentes debatieron y se pusieron de acuerdo",
  arbitraje: "Los agentes no se pusieron de acuerdo: el Crítico eligió",
  memoria: "Lo recordó de lo que ya habías corregido",
  persona: "Lo agregaste tú",
});

export const NIVELES_META = Object.freeze([
  { id: "organizacional", nombre: "De la organización", corto: "Organización", prefijo: "MO", tono: "#ffd166",
    que: "Lo que la organización quiere lograr en su negocio" },
  { id: "estrategica", nombre: "Estratégicas", corto: "Estratégica", prefijo: "ME", tono: "#ff9f6b",
    que: "Lo que el sistema debe conseguir para contribuir" },
  { id: "especifica", nombre: "Específicas", corto: "Específica", prefijo: "MS", tono: "#ff7a8a",
    que: "Concretas y verificables" },
]);
export const nivelMeta = (id) => NIVELES_META.find((n) => n.id === id) ?? NIVELES_META[2];
export const NIVEL_SUPERIOR = { organizacional: null, estrategica: "organizacional", especifica: "estrategica" };
export const PRIORIDADES = ["alta", "media", "baja"];
