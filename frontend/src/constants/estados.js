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
 *                        -> rechazado  (terminal; "reprocesar" vuelve a cargado)
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
});

const E = ESTADOS;

export const TRANSICIONES = Object.freeze({
  [E.CARGADO]: [E.EXTRAIDO],
  [E.EXTRAIDO]: [E.INTERPRETADO],
  [E.INTERPRETADO]: [E.ACEPTADO_DIRECTO, E.EN_DEBATE],
  [E.EN_DEBATE]: [E.CONSENSO, E.ARBITRADO],
  [E.ACEPTADO_DIRECTO]: [E.PENDIENTE_VALIDACION],
  [E.CONSENSO]: [E.PENDIENTE_VALIDACION],
  [E.ARBITRADO]: [E.PENDIENTE_VALIDACION],
  [E.PENDIENTE_VALIDACION]: [E.VALIDADO, E.RECHAZADO],
  [E.VALIDADO]: [E.FORMALIZADO],
  [E.RECHAZADO]: [E.CARGADO], // reprocesar
  [E.FORMALIZADO]: [],
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
    descripcion: "Las interpretaciones coinciden (similitud ≥ umbral); no hubo debate.",
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
    descripcion: "El debate cerró con similitud ≥ umbral antes de agotar las rondas.",
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
    descripcion: "Artefactos generados; esperan revisión humana.",
    clase: "bg-violet-50 text-violet-800 ring-violet-300",
    punto: "bg-violet-500",
  },
  [E.VALIDADO]: {
    etiqueta: "Validado",
    descripcion: "Una persona aprobó los artefactos (con o sin edición).",
    clase: "bg-green-50 text-green-800 ring-green-300",
    punto: "bg-green-600",
  },
  [E.RECHAZADO]: {
    etiqueta: "Rechazado",
    descripcion: "Una persona rechazó los artefactos. Puede reprocesarse.",
    clase: "bg-red-50 text-red-800 ring-red-300",
    punto: "bg-red-500",
  },
  [E.FORMALIZADO]: {
    etiqueta: "Formalizado",
    descripcion: "La entrada se incorporó al LEL acumulado.",
    clase: "bg-slate-800 text-white ring-slate-800",
    punto: "bg-slate-800",
  },
});

/* Orden de presentación (filtros, leyendas) */
export const ORDEN_ESTADOS = [
  E.CARGADO, E.EXTRAIDO, E.INTERPRETADO,
  E.ACEPTADO_DIRECTO, E.EN_DEBATE, E.CONSENSO, E.ARBITRADO,
  E.PENDIENTE_VALIDACION, E.VALIDADO, E.RECHAZADO, E.FORMALIZADO,
];

/* Estados en los que los agentes siguen trabajando: la UI los sondea */
export const ESTADOS_EN_PROCESO = [E.CARGADO, E.EXTRAIDO, E.INTERPRETADO, E.EN_DEBATE];
export const estaEnProceso = (estado) => ESTADOS_EN_PROCESO.includes(estado);

/* Cómo se resolvió la interpretación final */
export const VIAS_RESOLUCION = Object.freeze({
  DIRECTO: "directo",
  CONSENSO: "consenso",
  ARBITRAJE: "arbitraje",
});

export const ESTADO_DE_VIA = Object.freeze({
  [VIAS_RESOLUCION.DIRECTO]: E.ACEPTADO_DIRECTO,
  [VIAS_RESOLUCION.CONSENSO]: E.CONSENSO,
  [VIAS_RESOLUCION.ARBITRAJE]: E.ARBITRADO,
});

/* ¿El requisito ya pasó por `estado`? Se responde con su historial. */
export const alcanzo = (historial, estado) => historial?.some((h) => h.estado === estado) ?? false;

/*
 * Disposición del diagrama de la máquina de estados (LineaEstados):
 * columnas de izquierda a derecha; las ramas alternativas comparten columna.
 */
export const DIAGRAMA = [
  [E.CARGADO],
  [E.EXTRAIDO],
  [E.INTERPRETADO],
  [E.ACEPTADO_DIRECTO, E.EN_DEBATE],
  [E.CONSENSO, E.ARBITRADO],
  [E.PENDIENTE_VALIDACION],
  [E.VALIDADO, E.RECHAZADO],
  [E.FORMALIZADO],
];
