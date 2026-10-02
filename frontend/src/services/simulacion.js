/*
 * Simulación del proceso de los agentes. SOLO la usa mockDb.js; cuando
 * exista el backend este archivo desaparece.
 *
 * - generarMaterial(): inventa lo que "dirían" los agentes para un texto
 *   nuevo, usando los catálogos para marcar términos.
 * - construirProceso(): a partir del material y la configuración vigente
 *   (umbral, rondas) decide el camino y arma la traza y la línea de tiempo.
 * - trazaVisible(): recorta la traza a lo que ya ocurrió en un paso dado,
 *   para que el sondeo vea el avance etapa por etapa.
 */
import { ESTADOS as E, VIAS_RESOLUCION as V } from "../constants/estados";

const DUR = { divergencia: 1500, ronda: 5000, consenso: 1500, arbitraje: 3500, modelador: 3000 };

/* ---------- utilidades de texto ---------- */
const sinAcento = (c) => c.normalize("NFD")[0].toLowerCase();
const normalizar = (s) => [...s].map(sinAcento).join("");

function hash01(s) {
  let h = 2166136261;
  for (const ch of s) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return ((h >>> 0) % 1000) / 1000;
}

const redondear = (x) => Math.round(Math.min(0.97, x) * 100) / 100;

/* Posición de cada término marcado dentro del texto (sin importar mayúsculas ni acentos) */
export function ubicarMarcados(texto, marcados) {
  const base = normalizar(texto);
  return marcados
    .map((m) => {
      const inicio = base.indexOf(normalizar(m.texto));
      return inicio < 0 ? null : { ...m, inicio, fin: inicio + m.texto.length };
    })
    .filter(Boolean)
    .sort((a, b) => a.inicio - b.inicio);
}

/* Expresiones de los catálogos presentes en el texto */
export function buscarEnCatalogos(texto, catalogos) {
  const base = ` ${normalizar(texto).replace(/[^a-z0-9ñ ]/g, " ")} `;
  const hits = [];
  for (const [tipo, filas] of [["mexicanismo", catalogos.mexicanismos], ["vaguedad", catalogos.vaguedad]]) {
    for (const fila of filas) {
      const exp = normalizar(fila.expresion);
      if (exp && base.includes(` ${exp} `)) hits.push({ ...fila, tipo });
    }
  }
  return hits;
}

/* ---------- material simulado para textos sin fixture ---------- */
const MODALES = ["debe", "debera", "podra", "puede", "deberia", "permitira"];
const ARTICULOS = ["el", "la", "los", "las", "un", "una", "al", "del", "a", "de", "su", "sus", "cada", "todo", "toda", "todos", "todas", "este", "esta"];

function extraerTerminos(texto) {
  const palabras = texto.replace(/[.,;:¿?¡!]/g, "").split(/\s+/).filter(Boolean);
  const n = palabras.map(normalizar);
  const terminos = [];
  const i0 = ARTICULOS.includes(n[0]) ? 1 : 0;
  if (palabras[i0]) terminos.push({ texto: palabras[i0], categoria: "sujeto", lema: n[i0] });
  let iv = n.findIndex((w) => MODALES.includes(w));
  if (iv >= 0) {
    iv += 1;
    if (n[iv] === "poder") iv += 1;
    if (palabras[iv]) terminos.push({ texto: palabras[iv], categoria: "verbo", lema: n[iv] });
    let io = iv + 1;
    while (io < n.length && ARTICULOS.includes(n[io])) io++;
    if (palabras[io]) terminos.push({ texto: palabras[io], categoria: "objeto", lema: n[io] });
  }
  return terminos;
}

export function generarMaterial({ id, texto }, catalogos) {
  const h = hash01(id + texto);
  const terminos = extraerTerminos(texto);
  const hits = buscarEnCatalogos(texto, catalogos);
  const verbo = terminos.find((t) => t.categoria === "verbo")?.texto ?? "atender";
  const objeto = terminos.find((t) => t.categoria === "objeto")?.texto ?? "solicitud";
  const sujeto = terminos.find((t) => t.categoria === "sujeto")?.texto ?? "sistema";

  for (const hit of hits) {
    if (!terminos.some((t) => normalizar(t.texto) === normalizar(hit.expresion))) {
      terminos.push({ texto: hit.expresion, categoria: hit.tipo === "vaguedad" ? "restriccion" : "verbo", lema: normalizar(hit.expresion) });
    }
  }

  const marcados = hits.map((hit) => ({
    texto: hit.expresion,
    tipo: hit.tipo,
    fuente: `Catálogo de ${hit.tipo === "vaguedad" ? "vaguedad" : "mexicanismos"} (${hit.id})`,
  }));

  const principal = hits[0];
  const l0 = principal?.lecturas[0] ?? "lectura literal";
  const l1 = principal?.lecturas[1] ?? "lectura literal con otro alcance";
  const ambiguo = Boolean(principal);

  const s0 = ambiguo ? 0.42 + h * 0.25 : 0.84 + h * 0.1;
  const r1 = s0 + 0.12 + h * 0.1;
  const r2 = r1 + 0.08;
  const r3 = r2 + 0.05;

  const rondaGenerica = (sim, n) => ({
    intervenciones: [
      { postura: "A", argumento: ambiguo ? `En este contexto «${principal.expresion}» se entiende como «${l0}». (argumento simulado, ronda ${n})` : `La lectura literal basta. (argumento simulado, ronda ${n})` },
      { postura: "B", argumento: ambiguo ? `El interesado podría querer decir «${l1}». (argumento simulado, ronda ${n})` : `Coincido con matices menores. (argumento simulado, ronda ${n})` },
      { postura: "moderador", argumento: `Se recalcula la similitud tras los argumentos. (simulado)` },
    ],
    similitudCierre: redondear(sim),
  });

  const interpretacionA = ambiguo ? `${texto.replace(/\.$/, "")} — entendiendo «${principal.expresion}» como «${l0}».` : texto;

  return {
    generado: true,
    extraccion: { duracionMs: 2500 + Math.round(h * 1200), terminos, marcados },
    clasificacion: {
      duracionMs: 3200 + Math.round(h * 1500),
      enDisputa: hits.map((x) => x.expresion),
      interpretaciones: {
        A: {
          texto: interpretacionA,
          lecturas: ambiguo ? [{ termino: principal.expresion, significado: l0 }] : [],
        },
        B: {
          texto: ambiguo ? `${texto.replace(/\.$/, "")} — entendiendo «${principal.expresion}» como «${l1}».` : `${texto.replace(/\.$/, "")} (paráfrasis equivalente).`,
          lecturas: ambiguo ? [{ termino: principal.expresion, significado: l1 }] : [],
        },
      },
    },
    similitudInicial: redondear(s0),
    rondas: [rondaGenerica(r1, 1), rondaGenerica(r2, 2), rondaGenerica(r3, 3)],
    consenso: { interpretacion: interpretacionA },
    arbitraje: {
      eleccion: "A",
      interpretacion: interpretacionA,
      criterios: [
        { criterio: "Catálogo regional", aplicacion: ambiguo ? `«${l0}» es la primera lectura registrada para «${principal.expresion}».` : "Sin términos de catálogo.", favorece: "A" },
        { criterio: "Tratamiento sugerido", aplicacion: principal?.tratamiento ?? "Ninguno", favorece: "A" },
        { criterio: "Verificabilidad", aplicacion: "La lectura A puede probarse sin información adicional.", favorece: "A" },
      ],
      justificacion: "Arbitraje simulado: todos los criterios favorecen la lectura A.",
    },
    artefactos: {
      lel: {
        simbolo: principal?.expresion ?? objeto,
        tipo: principal ? (principal.tipo === "vaguedad" ? "estado" : "verbo") : "objeto",
        sinonimos: [],
        nocion: [ambiguo ? `En este dominio, «${principal.expresion}» significa «${l0}».` : `«${objeto}» tal como se usa en el requisito ${id}.`],
        impacto: [`El ${sujeto} puede ${verbo} ${objeto}.`],
      },
      metas: {
        metaEstrategica: `Cumplir el requisito ${id}`,
        submetas: [{ id: "M1", descripcion: `${verbo} ${objeto}`, tipo: "dura" }],
      },
      bigPicture: {
        requisito: id,
        actores: [sujeto],
        acciones: [{ actor: sujeto, verbo, objeto }],
        restricciones: [],
        terminosResueltos: ambiguo ? [{ termino: principal.expresion, significado: l0 }] : [],
      },
    },
  };
}

/* ---------- camino y línea de tiempo según la configuración ---------- */
export function construirProceso(material, config) {
  const { umbral, maxRondas } = config;
  const pasos = [];
  let t = 0;
  const paso = (estado, extra = {}) => pasos.push({ estado, ms: t, ...extra });

  paso(E.CARGADO);
  t += material.extraccion.duracionMs;
  paso(E.EXTRAIDO);
  t += material.clasificacion.duracionMs;
  paso(E.INTERPRETADO);
  t += DUR.divergencia;

  const similitud = material.similitudInicial;
  const directo = similitud >= umbral;
  const traza = {
    extraccion: { ...material.extraccion, modelo: config.modelos.extractor },
    clasificacion: { ...material.clasificacion, modelo: config.modelos.clasificador },
    divergencia: {
      modeloEmbeddings: config.modeloEmbeddings,
      similitud,
      umbral,
      decision: directo ? "directo" : "debate",
    },
  };

  if (directo) {
    paso(E.ACEPTADO_DIRECTO);
    traza.resolucion = {
      via: V.DIRECTO,
      interpretacion: material.consenso?.interpretacion ?? material.clasificacion.interpretaciones.A.texto,
      explicacion: `La similitud inicial (${similitud.toFixed(2)}) es mayor o igual que el umbral (${umbral.toFixed(2)}): las interpretaciones coinciden y se aceptó sin debate.`,
    };
  } else {
    paso(E.EN_DEBATE, { rondas: 0 });
    const disponibles = material.rondas ?? [];
    const rondas = [];
    let consensoEn = 0;
    for (let i = 0; i < maxRondas; i++) {
      const previa = rondas[i - 1]?.similitudCierre ?? similitud;
      const base = disponibles[i] ?? {
        intervenciones: [
          { postura: "A", argumento: "Sin argumentos nuevos. (ronda adicional simulada)" },
          { postura: "B", argumento: "Sin argumentos nuevos. (ronda adicional simulada)" },
          { postura: "moderador", argumento: "La similitud apenas cambia." },
        ],
        similitudCierre: redondear(previa + 0.02),
      };
      rondas.push({
        numero: i + 1,
        intervenciones: base.intervenciones.map((x) => ({ ...x, agente: x.postura === "moderador" ? "critico" : "clasificador" })),
        ajustes: base.ajustes ?? null,
        similitudCierre: base.similitudCierre,
        similitudApertura: previa,
      });
      t += DUR.ronda;
      paso(E.EN_DEBATE, { rondas: i + 1 });
      if (base.similitudCierre >= umbral) { consensoEn = i + 1; break; }
    }

    const consenso = consensoEn > 0;
    traza.debate = {
      maxRondas,
      umbral,
      rondas,
      resultado: consenso ? "consenso" : "agotado",
    };
    const ultima = rondas[rondas.length - 1];
    if (consenso) {
      t += DUR.consenso;
      paso(E.CONSENSO, { rondas: rondas.length });
      traza.resolucion = {
        via: V.CONSENSO,
        ronda: consensoEn,
        interpretacion: material.consenso?.interpretacion ?? material.clasificacion.interpretaciones.A.texto,
        explicacion: `Al cerrar la ronda ${consensoEn} la similitud llegó a ${ultima.similitudCierre.toFixed(2)}, mayor o igual que el umbral (${umbral.toFixed(2)}): los agentes alcanzaron consenso.`,
      };
    } else {
      t += DUR.arbitraje;
      paso(E.ARBITRADO, { rondas: rondas.length });
      traza.debate.arbitraje = { ...material.arbitraje, modelo: config.modelos.critico };
      traza.resolucion = {
        via: V.ARBITRAJE,
        interpretacion: material.arbitraje.interpretacion,
        eleccion: material.arbitraje.eleccion,
        explicacion: `Tras ${rondas.length} ${rondas.length === 1 ? "ronda" : "rondas"} (máximo configurado) la similitud quedó en ${ultima.similitudCierre.toFixed(2)}, por debajo del umbral (${umbral.toFixed(2)}). Se agotaron las rondas y el Crítico arbitró.`,
      };
    }
  }

  t += DUR.modelador;
  paso(E.PENDIENTE_VALIDACION);
  traza.artefactos = { modelo: config.modelos.modelador };

  return { traza, pasos, duracionMs: t };
}

/* Traza recortada a lo ocurrido hasta el paso `idx` */
export function trazaVisible({ traza, pasos }, idx) {
  const hechos = new Set(pasos.slice(0, idx + 1).map((p) => p.estado));
  const actual = pasos[idx];
  const v = {};
  if (hechos.has(E.EXTRAIDO)) v.extraccion = traza.extraccion;
  if (hechos.has(E.INTERPRETADO)) v.clasificacion = traza.clasificacion;
  if (hechos.has(E.ACEPTADO_DIRECTO) || hechos.has(E.EN_DEBATE)) v.divergencia = traza.divergencia;
  if (traza.debate && hechos.has(E.EN_DEBATE)) {
    const terminado = hechos.has(E.CONSENSO) || hechos.has(E.ARBITRADO);
    v.debate = {
      ...traza.debate,
      rondas: traza.debate.rondas.slice(0, actual.rondas ?? traza.debate.rondas.length),
      resultado: terminado ? traza.debate.resultado : "en_curso",
      arbitraje: hechos.has(E.ARBITRADO) ? traza.debate.arbitraje : undefined,
    };
  }
  if (hechos.has(E.ACEPTADO_DIRECTO) || hechos.has(E.CONSENSO) || hechos.has(E.ARBITRADO)) v.resolucion = traza.resolucion;
  if (hechos.has(E.PENDIENTE_VALIDACION)) v.artefactos = traza.artefactos;
  return v;
}

/* ---------- evaluación contra el ground truth ---------- */
export function evaluarCorpus(corpus, config) {
  const filas = corpus.map((c) => {
    const verdad = c.verdad.terminos.map(normalizar);
    const detectados = c.sistema.terminos.map(normalizar);
    const aciertos = c.sistema.terminos.filter((t) => verdad.includes(normalizar(t)));
    const falsasAlarmas = c.sistema.terminos.filter((t) => !verdad.includes(normalizar(t)));
    const omitidos = c.verdad.terminos.filter((t) => !detectados.includes(normalizar(t)));
    const debate = c.sistema.similitud < config.umbral;
    return {
      ...c,
      aciertos,
      falsasAlarmas,
      omitidos,
      debate,
      debateDeMas: debate && !c.verdad.ambiguo,
      debateFaltante: !debate && c.verdad.ambiguo,
    };
  });
  const suma = (f) => filas.reduce((a, x) => a + f(x), 0);
  const tp = suma((x) => x.aciertos.length);
  const fp = suma((x) => x.falsasAlarmas.length);
  const fn = suma((x) => x.omitidos.length);
  const precision = tp + fp ? tp / (tp + fp) : 0;
  const recall = tp + fn ? tp / (tp + fn) : 0;
  return {
    filas,
    resumen: {
      requisitos: filas.length,
      ambiguedadesReales: tp + fn,
      detectadas: tp,
      falsasAlarmas: fp,
      omitidas: fn,
      precision,
      recall,
      f1: precision + recall ? (2 * precision * recall) / (precision + recall) : 0,
      debatesActivados: suma((x) => (x.debate ? 1 : 0)),
      debatesNecesarios: suma((x) => (x.verdad.ambiguo ? 1 : 0)),
      debatesDeMas: suma((x) => (x.debateDeMas ? 1 : 0)),
      debatesFaltantes: suma((x) => (x.debateFaltante ? 1 : 0)),
    },
  };
}
