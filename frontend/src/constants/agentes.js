/* Tipos de símbolo del LEL */
export const TIPOS_LEL = ["sujeto", "objeto", "verbo", "estado"];

/* ===================================================================== */
/*  Nodos reales del backend (emisor/receptor de cada mensaje, ADR 0001)  */
/* ===================================================================== */

/* Fases de KMoS-SSA y el componente que las cubre (CONTEXTO §5) */
export const FASES_KMOS = Object.freeze([
  { n: 1, nombre: "Enriquecimiento de conocimiento", nodos: ["extractor", "filtros"] },
  { n: 2, nombre: "Generación de modelo", nodos: ["clasificador"] },
  { n: 3, nombre: "Discusión de modelo", nodos: ["divergencia", "critico"] },
  { n: 4, nombre: "Validación de modelo", nodos: ["humano"] },
  { n: 5, nombre: "Enriquecimiento (cierre)", nodos: ["modelador"] },
]);

export const NODOS = Object.freeze({
  extractor: { id: "extractor", nombre: "Extractor", rol: "Separa el vocabulario del dominio", tipo: "agente", fase: 1, tono: "#41efff" },
  filtros: { id: "filtros", nombre: "Filtros", rol: "LEL como memoria, vaguedad, regionales, alcance y anáfora (deterministas)", tipo: "mecanismo", fase: 1, tono: "#7dd3fc" },
  clasificador: { id: "clasificador", nombre: "Clasificador", rol: "Genera interpretaciones candidatas y su tipo de ambigüedad", tipo: "agente", fase: 2, tono: "#a99bff" },
  divergencia: { id: "divergencia", nombre: "Divergencia", rol: "Embeddings, similitud coseno mínima entre pares y umbral (no es agente)", tipo: "mecanismo", fase: 3, tono: "#e2e8f0" },
  critico: { id: "critico", nombre: "Crítico", rol: "Evalúa R1–R3, objeta y arbitra si se agotan las rondas", tipo: "agente", fase: 3, tono: "#ffc457" },
  humano: { id: "humano", nombre: "Humano", rol: "Valida, elige o edita las interpretaciones", tipo: "persona", fase: 4, tono: "#f9a8d4" },
  modelador: { id: "modelador", nombre: "Modelador", rol: "Formaliza: LEL, requisito reescrito y metas", tipo: "agente", fase: 5, tono: "#57f7a7" },
  sistema: { id: "sistema", nombre: "Sistema", rol: "Orquestación (LangGraph): reglas de consenso, solicitud de validación, errores", tipo: "mecanismo", fase: null, tono: "#94a3b8" },
});

/* Orden en la escena (izquierda a derecha, el flujo del requisito) */
export const ORDEN_NODOS = ["extractor", "filtros", "clasificador", "divergencia", "critico", "humano", "modelador"];

export const nodo = (id) => NODOS[id] ?? { id, nombre: id, rol: "", tipo: "mecanismo", fase: null, tono: "#94a3b8" };

/* Interpretaciones I1…In: mismo color en esferas, tarjetas y gráficas */
const PALETA = [
  { trazo: "#38bdf8", clase: "border-sky-400 bg-sky-50 text-sky-900", solido: "bg-sky-500" },
  { trazo: "#f59e0b", clase: "border-amber-400 bg-amber-50 text-amber-900", solido: "bg-amber-500" },
  { trazo: "#a78bfa", clase: "border-violet-400 bg-violet-50 text-violet-900", solido: "bg-violet-500" },
  { trazo: "#34d399", clase: "border-emerald-400 bg-emerald-50 text-emerald-900", solido: "bg-emerald-500" },
  { trazo: "#f472b6", clase: "border-pink-400 bg-pink-50 text-pink-900", solido: "bg-pink-500" },
  { trazo: "#fb7185", clase: "border-rose-400 bg-rose-50 text-rose-900", solido: "bg-rose-500" },
];
export const colorInterpretacion = (id) => {
  const n = Number(String(id).replace(/\D/g, "")) || 1;
  return { ...PALETA[(n - 1) % PALETA.length], mood: `interp${((n - 1) % PALETA.length) + 1}` };
};

/* Tipos de ambigüedad (Clasificador) y marcas de los filtros, con su presentación */
export const TIPOS = Object.freeze({
  lexica: { etiqueta: "Léxica", descripcion: "La palabra tiene más de un sentido", clase: "bg-sky-100 text-sky-900 decoration-sky-500", debate: true },
  alcance: { etiqueta: "Alcance", descripcion: "No está claro sobre qué aplica un cuantificador, negación, «solo» o una coordinación", clase: "bg-indigo-100 text-indigo-900 decoration-indigo-500", debate: true },
  anaforica: { etiqueta: "Anafórica", descripcion: "Un pronombre o posesivo tiene más de un antecedente posible", clase: "bg-fuchsia-100 text-fuchsia-900 decoration-fuchsia-500", debate: true },
  sintactica: { etiqueta: "Sintáctica", descripcion: "La oración admite más de una estructura", clase: "bg-cyan-100 text-cyan-900 decoration-cyan-500", debate: true },
  vaguedad: { etiqueta: "Vaguedad", descripcion: "Límite impreciso; se marca y no se debate", clase: "bg-violet-100 text-violet-900 decoration-violet-500", debate: false },
  regional: { etiqueta: "Regional", descripcion: "Expresión del español de trabajo en México; pasa al Clasificador", clase: "bg-amber-100 text-amber-900 decoration-amber-500", debate: true },
  lel: { etiqueta: "Resuelto por el LEL", descripcion: "Ya tiene noción validada en el proyecto; no se vuelve a debatir", clase: "bg-emerald-100 text-emerald-900 decoration-emerald-500", debate: false },
});
export const tipo = (t) => TIPOS[t] ?? { etiqueta: t ?? "—", descripcion: "", clase: "bg-slate-100 text-slate-800", debate: false };

/* Reglas del Crítico, versión v1 provisional (ADR 0004) */
export const REGLAS = Object.freeze({
  R1: { nombre: "Consistencia de vocabulario", como: "spaCy (lemas): no introduce términos fuera del requisito, el LEL y el significado" },
  R2: { nombre: "Sin entidades nuevas", como: "spaCy: no introduce sustantivos ni entidades fuera del requisito, el LEL y el significado" },
  R3: { nombre: "Reduce la ambigüedad", como: "LLM con evidencia textual: la paráfrasis asigna un único referente" },
});
