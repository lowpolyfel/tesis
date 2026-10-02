/*
 * Base de datos simulada en memoria (persistida en localStorage).
 * SOLO la usa api.js. Cuando exista el backend, api.js deja de importarla.
 *
 * Cada requisito guarda su material, la configuración con la que se
 * procesó y la hora de inicio; su estado actual se calcula con el reloj,
 * así el proceso "avanza solo" mientras la UI sondea.
 */
import { ESTADOS as E, puedeTransicionar } from "../constants/estados";
import { requisitosSemilla } from "../fixtures/requisitos";
import { mexicanismos, vaguedad } from "../fixtures/catalogos";
import { configuracionInicial, modelosDisponibles } from "../fixtures/configuracion";
import { lelAdicional } from "../fixtures/lel";
import { corpus } from "../fixtures/corpus";
import { generarMaterial, construirProceso, trazaVisible, ubicarMarcados, evaluarCorpus } from "./simulacion";

const CLAVE = "dudamel.mockdb.v1";
const MS_POR_ITEM_CORPUS = 550;
const clonar = (x) => structuredClone(x);

/* ---------- semilla ---------- */
function sembrar() {
  const ahora = Date.now();
  const catalogos = { mexicanismos: clonar(mexicanismos), vaguedad: clonar(vaguedad) };
  const config = clonar(configuracionInicial);

  const requisitos = requisitosSemilla.map((r) => {
    const material = r.extraccion ? clonar(r) : generarMaterial(r, catalogos);
    const inicioMs = r.enProcesoHaceSeg != null ? ahora - r.enProcesoHaceSeg * 1000 : Date.parse(r.creadoEn);
    const humano = (r.humano ?? []).map((h) => ({
      estado: h.estado,
      en: new Date(Date.parse(r.creadoEn) + h.minutosDespues * 60000).toISOString(),
      editado: h.editado ?? false,
      comentario: h.comentario ?? "",
    }));
    const validado = humano.some((h) => h.estado === E.VALIDADO);
    return {
      id: r.id,
      texto: r.texto,
      origen: r.origen,
      creadoEn: r.creadoEn,
      material: { ...material, id: undefined, texto: undefined, humano: undefined },
      config: clonar(config),
      inicioMs,
      humano,
      borrador: null,
      artefactosValidados: validado ? clonar(material.artefactos) : null,
      intentosPrevios: [],
    };
  });

  const db = {
    version: 1,
    config,
    historialConfig: [{ en: new Date(ahora - 86400000 * 2).toISOString(), config: clonar(config), nota: "Valores iniciales" }],
    catalogos,
    lelAdicional: clonar(lelAdicional),
    corpus: clonar(corpus),
    ejecuciones: [],
    requisitos,
    siguienteId: 13,
  };

  // Dos corridas pasadas para comparar calibraciones
  for (const [umbral, horas] of [[0.7, 30], [0.75, 26]]) {
    const cfg = { ...clonar(config), umbral };
    const inicio = ahora - horas * 3600000;
    db.ejecuciones.push({
      id: `EV-${db.ejecuciones.length + 1}`,
      inicioMs: inicio,
      config: cfg,
      total: db.corpus.length,
      resultados: evaluarCorpus(db.corpus, cfg),
    });
  }
  return db;
}

/* ---------- persistencia ---------- */
let db = cargar();

function cargar() {
  try {
    const guardado = JSON.parse(localStorage.getItem(CLAVE));
    if (guardado?.version === 1) return guardado;
  } catch { /* sin almacenamiento: se usa la semilla */ }
  return sembrar();
}

function guardar() {
  try { localStorage.setItem(CLAVE, JSON.stringify(db)); } catch { /* almacenamiento no disponible */ }
}
guardar();

export function reiniciar() {
  db = sembrar();
  guardar();
}

/* ---------- vista calculada de un requisito ---------- */
const cacheProceso = new Map();
function proceso(reg) {
  const clave = `${reg.id}|${reg.inicioMs}|${reg.config.umbral}|${reg.config.maxRondas}|${JSON.stringify(reg.config.modelos)}`;
  if (!cacheProceso.has(clave)) cacheProceso.set(clave, construirProceso(reg.material, reg.config));
  return cacheProceso.get(clave);
}

function vista(reg, { completo = true } = {}) {
  const p = proceso(reg);
  const transcurrido = Date.now() - reg.inicioMs;
  let idx = 0;
  for (let i = 0; i < p.pasos.length; i++) if (p.pasos[i].ms <= transcurrido) idx = i;
  const terminado = idx === p.pasos.length - 1;
  const humano = terminado ? reg.humano : [];

  const historial = [];
  for (const paso of p.pasos.slice(0, idx + 1)) {
    if (historial.at(-1)?.estado === paso.estado) continue;
    historial.push({ estado: paso.estado, en: new Date(reg.inicioMs + paso.ms).toISOString() });
  }
  for (const h of humano) historial.push({ estado: h.estado, en: h.en, comentario: h.comentario, editado: h.editado });

  const estado = historial.at(-1).estado;
  const actualizadoEn = historial.at(-1).en + (p.pasos[idx].rondas ?? "");
  const traza = trazaVisible(p, idx);
  const resumen = {
    id: reg.id,
    texto: reg.texto,
    origen: reg.origen,
    creadoEn: reg.creadoEn,
    estado,
    actualizadoEn,
    similitud: traza.divergencia?.similitud ?? null,
    via: traza.resolucion?.via ?? null,
    rondas: traza.debate?.rondas.length ?? 0,
  };
  if (!completo) return resumen;

  if (traza.extraccion) {
    traza.extraccion = { ...traza.extraccion, marcados: ubicarMarcados(reg.texto, traza.extraccion.marcados) };
  }
  return {
    ...resumen,
    historial,
    configUsada: reg.config,
    simulado: Boolean(reg.material.generado),
    traza,
    artefactos: traza.artefactos
      ? {
          ...traza.artefactos,
          propuesta: reg.material.artefactos,
          borrador: reg.borrador,
          validados: reg.artefactosValidados,
        }
      : null,
    intentosPrevios: reg.intentosPrevios,
  };
}

const buscar = (id) => {
  const reg = db.requisitos.find((r) => r.id === id);
  if (!reg) throw new Error(`No existe el requisito ${id}`);
  return reg;
};

function transicionar(reg, hacia, extra = {}) {
  const actual = vista(reg, { completo: false }).estado;
  if (!puedeTransicionar(actual, hacia)) {
    throw new Error(`Transición no permitida: ${actual} → ${hacia}`);
  }
  reg.humano.push({ estado: hacia, en: new Date().toISOString(), editado: false, comentario: "", ...extra });
}

/* ---------- requisitos ---------- */
export const listarRequisitos = () => db.requisitos.map((r) => vista(r, { completo: false }));
export const obtenerRequisito = (id) => vista(buscar(id));
export const obtenerEstadoRequisito = (id) => {
  const { estado, actualizadoEn } = vista(buscar(id), { completo: false });
  return { id, estado, actualizadoEn };
};

export function crearRequisitos(lista) {
  // Un solo flujo de agentes: cada requisito empieza cuando termina el anterior
  let inicio = Date.now() + 600;
  const ids = lista.map((item) => {
    const id = `REQ-${String(db.siguienteId++).padStart(3, "0")}`;
    const reg = {
      id,
      texto: item.texto.trim(),
      origen: item.origen || "texto pegado",
      creadoEn: new Date().toISOString(),
      material: generarMaterial({ id, texto: item.texto }, db.catalogos),
      config: clonar(db.config),
      inicioMs: inicio,
      humano: [],
      borrador: null,
      artefactosValidados: null,
      intentosPrevios: [],
    };
    db.requisitos.push(reg);
    inicio += proceso(reg).duracionMs + 900;
    return id;
  });
  guardar();
  return ids;
}

export function reprocesar(id) {
  const reg = buscar(id);
  const actual = vista(reg, { completo: false }).estado;
  if (!puedeTransicionar(actual, E.CARGADO)) throw new Error(`No se puede reprocesar desde ${actual}`);
  reg.intentosPrevios.push({ config: reg.config, humano: reg.humano, finalizadoEn: new Date().toISOString() });
  reg.config = clonar(db.config);
  reg.inicioMs = Date.now();
  reg.humano = [];
  reg.borrador = null;
  reg.artefactosValidados = null;
  guardar();
}

/* ---------- validación ---------- */
export function guardarBorrador(id, artefactos) {
  buscar(id).borrador = clonar(artefactos);
  guardar();
}

export function validar(id, artefactos, { comentario = "", editado = false } = {}) {
  const reg = buscar(id);
  transicionar(reg, E.VALIDADO, { comentario, editado });
  reg.artefactosValidados = clonar(artefactos);
  reg.borrador = null;
  guardar();
}

export function rechazar(id, comentario) {
  const reg = buscar(id);
  transicionar(reg, E.RECHAZADO, { comentario });
  guardar();
}

export function formalizar(id) {
  const reg = buscar(id);
  transicionar(reg, E.FORMALIZADO);
  guardar();
}

/* ---------- LEL ---------- */
export function lel() {
  const principales = db.requisitos
    .filter((r) => vista(r, { completo: false }).estado === E.FORMALIZADO && r.artefactosValidados)
    .map((r) => ({ id: `lel-${r.id}`, ...r.artefactosValidados.lel, requisitoId: r.id, principal: true }));
  return [...principales, ...db.lelAdicional];
}

/* ---------- catálogos ---------- */
export const catalogo = (tipo) => db.catalogos[tipo];
export function guardarCatalogo(tipo, filas) {
  db.catalogos[tipo] = clonar(filas);
  guardar();
}

/* ---------- configuración ---------- */
export const configuracion = () => ({
  config: db.config,
  disponibles: modelosDisponibles,
  historial: db.historialConfig,
});
export function guardarConfiguracion(config, nota = "") {
  db.config = clonar(config);
  db.historialConfig.unshift({ en: new Date().toISOString(), config: clonar(config), nota });
  guardar();
}

/* ---------- corpus y evaluación ---------- */
export const obtenerCorpus = () => db.corpus;

export function lanzarEjecucion() {
  const ej = {
    id: `EV-${db.ejecuciones.length + 1}`,
    inicioMs: Date.now(),
    config: clonar(db.config),
    total: db.corpus.length,
    resultados: evaluarCorpus(db.corpus, db.config),
  };
  db.ejecuciones.push(ej);
  guardar();
  return ej.id;
}

function vistaEjecucion(ej) {
  const procesados = Math.min(ej.total, Math.floor((Date.now() - ej.inicioMs) / MS_POR_ITEM_CORPUS));
  const terminada = procesados >= ej.total;
  return {
    id: ej.id,
    inicio: new Date(ej.inicioMs).toISOString(),
    config: ej.config,
    total: ej.total,
    procesados,
    estado: terminada ? "terminada" : "en_curso",
    resultados: terminada ? ej.resultados : null,
  };
}
export const ejecuciones = () => db.ejecuciones.map(vistaEjecucion).reverse();
export const ejecucion = (id) => vistaEjecucion(db.ejecuciones.find((e) => e.id === id));
