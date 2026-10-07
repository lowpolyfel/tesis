/*
 * Máquina de estados de un requisito. ÚNICA fuente de verdad de la UI:
 * ninguna pantalla escribe nombres de estado a mano, todas leen de aquí.
 *
 *   cargado -> extraido -> interpretado
 *      |
 *      +-- similitud >= umbral -> aceptado_directo
 *      +-- similitud <  umbral -> en_debate -> (rondas) -> consenso
 *                                                       -> arbitrado
 *      v
 *   pendiente_validacion -> validado -> formalizado
 *                        -> rechazado  (terminal; "reprocesar" crea un requisito nuevo)
 *   aceptado_directo | consenso | arbitrado -> validado  (validación automática, ADR 0017:
 *      no hace falta una persona; con VALIDACION_HUMANA=si_hay_arbitraje solo espera el arbitrado)
 *   cualquier estado no terminal -> error (un agente no produjo salida válida tras el reintento)
 *
 * Es la misma máquina del backend (app/models/comunes.py, ADR 0005).
 */

export const ESTADOS = Object.freeze({
  CARGADO: "cargado",
  EXTRAIDO: "extraido",
  INTERPRETADO: "interpretado",
  ACEPTADO_DIRECTO: "aceptado_directo",
  EN_DEBATE: "en_debate",
  CONSENSO: "consenso",
  ARBITRADO: "arbitrado",
  PENDIENTE_VALIDACION: "pendiente_validacion",
  VALIDADO: "validado",
  RECHAZADO: "rechazado",
  FORMALIZADO: "formalizado",
  ERROR: "error",
});

const E = ESTADOS;

export const TRANSICIONES = Object.freeze({
  [E.CARGADO]: [E.EXTRAIDO],
  [E.EXTRAIDO]: [E.INTERPRETADO],
  [E.INTERPRETADO]: [E.ACEPTADO_DIRECTO, E.EN_DEBATE],
  [E.EN_DEBATE]: [E.CONSENSO, E.ARBITRADO],
  [E.ACEPTADO_DIRECTO]: [E.PENDIENTE_VALIDACION, E.VALIDADO],
  [E.CONSENSO]: [E.PENDIENTE_VALIDACION, E.VALIDADO],
  [E.ARBITRADO]: [E.PENDIENTE_VALIDACION, E.VALIDADO],
  [E.PENDIENTE_VALIDACION]: [E.VALIDADO, E.RECHAZADO],
  [E.VALIDADO]: [E.FORMALIZADO],
  [E.RECHAZADO]: [],
  [E.FORMALIZADO]: [],
  [E.ERROR]: [],
});

export const puedeTransicionar = (desde, hacia) => TRANSICIONES[desde]?.includes(hacia) ?? false;

/*
 * Presentación de cada estado. `clase` son utilidades de Tailwind para la
 * etiqueta; `punto` el color sólido (leyendas, diagrama).
 */
export const INFO_ESTADO = Object.freeze({
  [E.CARGADO]: {
    etiqueta: "Cargado",
    descripcion: "Texto recibido, aún sin procesar.",
    clase: "bg-slate-100 text-slate-700 ring-slate-300",
    punto: "bg-slate-400",
  },
  [E.EXTRAIDO]: {
    etiqueta: "Extraído",
    descripcion: "El Extractor separó el vocabulario del dominio.",
    clase: "bg-sky-50 text-sky-800 ring-sky-200",
    punto: "bg-sky-400",
  },
  [E.INTERPRETADO]: {
    etiqueta: "Interpretado",
    descripcion: "El Clasificador generó interpretaciones candidatas.",
    clase: "bg-blue-50 text-blue-800 ring-blue-200",
    punto: "bg-blue-500",
  },
  [E.ACEPTADO_DIRECTO]: {
    etiqueta: "Aceptado directo",
    descripcion: "Ningún término fue a debate: sus interpretaciones coinciden (similitud ≥ umbral) o no hubo interpretaciones que comparar.",
    clase: "bg-teal-50 text-teal-800 ring-teal-200",
    punto: "bg-teal-500",
  },
  [E.EN_DEBATE]: {
    etiqueta: "En debate",
    descripcion: "Las interpretaciones divergen (similitud < umbral); los agentes debaten.",
    clase: "bg-amber-50 text-amber-800 ring-amber-300",
    punto: "bg-amber-500",
  },
  [E.CONSENSO]: {
    etiqueta: "Consenso",
    descripcion: "El debate cerró sin arbitraje: en cada término la similitud llegó al umbral o quedó una sola interpretación (a más tardar en la última ronda).",
    clase: "bg-emerald-50 text-emerald-800 ring-emerald-200",
    punto: "bg-emerald-500",
  },
  [E.ARBITRADO]: {
    etiqueta: "Arbitrado",
    descripcion: "Se agotaron las rondas sin consenso; decidió el Crítico.",
    clase: "bg-orange-50 text-orange-800 ring-orange-300",
    punto: "bg-orange-500",
  },
  [E.PENDIENTE_VALIDACION]: {
    etiqueta: "Pendiente de validación",
    descripcion: "Interpretaciones propuestas; esperan la validación de una persona.",
    clase: "bg-violet-50 text-violet-800 ring-violet-300",
    punto: "bg-violet-500",
  },
  [E.VALIDADO]: {
    etiqueta: "Validado",
    descripcion: "Una persona aprobó las interpretaciones (con o sin edición); el Modelador formaliza.",
    clase: "bg-green-50 text-green-800 ring-green-300",
    punto: "bg-green-600",
  },
  [E.RECHAZADO]: {
    etiqueta: "Rechazado",
    descripcion: "Una persona rechazó la propuesta. Puede reprocesarse como requisito nuevo.",
    clase: "bg-red-50 text-red-800 ring-red-300",
    punto: "bg-red-500",
  },
  [E.FORMALIZADO]: {
    etiqueta: "Formalizado",
    descripcion: "El Modelador formalizó: entradas del LEL (términos léxicos), requisito reescrito y metas.",
    clase: "bg-slate-800 text-sobre ring-slate-800",
    punto: "bg-[#efe9de]", // claro en todos los fondos: slate-800 se perdía sobre la escena oscura
  },
  [E.ERROR]: {
    etiqueta: "Error",
    descripcion: "Un agente no produjo una salida válida tras el reintento; la traza registra el fallo.",
    clase: "bg-rose-100 text-rose-900 ring-rose-400",
    punto: "bg-rose-600",
  },
});

/* Etiqueta segura aunque llegue un estado desconocido */
export const infoEstado = (estado) =>
  INFO_ESTADO[estado] ?? { etiqueta: estado ?? "—", descripcion: "", clase: "bg-slate-100 text-slate-700 ring-slate-300", punto: "bg-slate-400" };

/* Orden de presentación (filtros, leyendas) */
export const ORDEN_ESTADOS = [
  E.CARGADO, E.EXTRAIDO, E.INTERPRETADO,
  E.ACEPTADO_DIRECTO, E.EN_DEBATE, E.CONSENSO, E.ARBITRADO,
  E.PENDIENTE_VALIDACION, E.VALIDADO, E.RECHAZADO, E.FORMALIZADO, E.ERROR,
];

/* Terminales: el grafo ya no avanza */
export const ESTADOS_TERMINALES = [E.RECHAZADO, E.FORMALIZADO, E.ERROR];
export const esTerminal = (estado) => ESTADOS_TERMINALES.includes(estado);

/*
 * En proceso: los agentes siguen trabajando sin esperar a nadie. Incluye los
 * estados de paso (aceptado_directo, consenso, arbitrado van solos a
 * pendiente_validacion; validado va solo a formalizado).
 */
export const ESTADOS_EN_PROCESO = [
  E.CARGADO, E.EXTRAIDO, E.INTERPRETADO, E.ACEPTADO_DIRECTO, E.EN_DEBATE, E.CONSENSO, E.ARBITRADO, E.VALIDADO,
];
export const estaEnProceso = (estado) => ESTADOS_EN_PROCESO.includes(estado);

/* Cómo se resolvió un término con interpretaciones (mismos valores que el backend) */
export const VIAS_RESOLUCION = Object.freeze({
  DIRECTO: "aceptado_directo",
  CONSENSO: "consenso",
  ARBITRAJE: "arbitraje",
});

export const INFO_VIA = Object.freeze({
  aceptado_directo: { etiqueta: "aceptado directo", tono: "#57f7a7", simple: "Los agentes coincidieron" },
  consenso: { etiqueta: "consenso", tono: "#a99bff", simple: "Acordado tras debatir" },
  arbitraje: { etiqueta: "arbitraje", tono: "#ffc457", simple: "Lo decidió el Crítico" },
});

/*
 * Lo que ve la persona: cinco estados en lenguaje claro. Los doce estados de la
 * máquina siguen en la traza (detalles técnicos).
 */
export const SIMPLE = Object.freeze({
  cola: { texto: "En cola", tono: "#94a3b8", descripcion: "Espera su turno." },
  analizando: { texto: "Analizando", tono: "#fbbf24", descripcion: "Los agentes están trabajando en él." },
  revisar: { texto: "Por revisar", tono: "#f9a8d4", descripcion: "Los agentes no se pusieron de acuerdo: elige tú." },
  listo: { texto: "Listo", tono: "#57f7a7", descripcion: "Reescrito sin ambigüedad y en la especificación." },
  descartado: { texto: "Descartado", tono: "#94a3b8", descripcion: "Lo descartaste; puedes volver a analizarlo." },
  error: { texto: "Error", tono: "#ff7b88", descripcion: "Un agente falló; puedes volver a analizarlo." },
});
export const estadoSimple = (estado) => {
  if (estado === E.CARGADO) return { id: "cola", ...SIMPLE.cola };
  if (estado === E.PENDIENTE_VALIDACION) return { id: "revisar", ...SIMPLE.revisar };
  if (estado === E.FORMALIZADO) return { id: "listo", ...SIMPLE.listo };
  if (estado === E.RECHAZADO) return { id: "descartado", ...SIMPLE.descartado };
  if (estado === E.ERROR) return { id: "error", ...SIMPLE.error };
  return { id: "analizando", ...SIMPLE.analizando };
};

/* Tono de la esfera para cada estado simple */
export const MOOD_SIMPLE = { cola: "sistema", analizando: "thinking", revisar: "humano", listo: "success", descartado: "sistema", error: "error" };
