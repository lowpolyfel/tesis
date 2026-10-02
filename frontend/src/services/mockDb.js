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
import { proyectosSemilla, asignacionSemilla } from "../fixtures/proyectos";
import { generarMaterial, construirProceso, trazaVisible, ubicarMarcados, evaluarCorpus } from "./simulacion";

const CLAVE = "dudamel.mockdb.v2";
const VERSION = 2;
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
    const [proyectoId, ciclo] = asignacionSemilla[r.id] ?? ["P-01", 1];
    return {
      id: r.id,
      texto: r.texto,
      origen: r.origen,
      creadoEn: r.creadoEn,
      proyectoId,
      ciclo,
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
    version: VERSION,
    proyectos: clonar(proyectosSemilla),
    siguienteProyecto: proyectosSemilla.length + 1,
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
    if (guardado?.version === VERSION) return guardado;
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
    proyectoId: reg.proyectoId,
    ciclo: reg.ciclo,
    reprocesos: reg.intentosPrevios.length,
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

export function crearRequisitos(lista, proyectoId) {
  if (!db.proyectos.some((p) => p.id === proyectoId)) throw new Error(`No existe el proyecto ${proyectoId}`);
  // Cada lote analizado es un ciclo nuevo del proyecto
  const ciclo = Math.max(0, ...db.requisitos.filter((r) => r.proyectoId === proyectoId).map((r) => r.ciclo)) + 1;
  // Un solo flujo de agentes: cada requisito empieza cuando termina el anterior
  let inicio = Date.now() + 600;
  const ids = lista.map((item) => {
    const id = `REQ-${String(db.siguienteId++).padStart(3, "0")}`;
    const reg = {
      id,
      texto: item.texto.trim(),
      origen: item.origen || "texto pegado",
      creadoEn: new Date().toISOString(),
      proyectoId,
      ciclo,
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
  const proyectoDe = Object.fromEntries(db.requisitos.map((r) => [r.id, r.proyectoId]));
  return [...principales, ...db.lelAdicional].map((e) => ({ ...e, proyectoId: proyectoDe[e.requisitoId] }));
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

/* ---------- proyectos ---------- */
function resumenProyecto(p) {
  const reqs = db.requisitos.filter((r) => r.proyectoId === p.id).map((r) => vista(r));
  const cuenta = (f) => reqs.filter(f).length;
  return {
    ...p,
    requisitos: reqs.length,
    ciclos: new Set(reqs.map((r) => r.ciclo)).size,
    enProceso: cuenta((r) => [E.CARGADO, E.EXTRAIDO, E.INTERPRETADO, E.EN_DEBATE].includes(r.estado)),
    porValidar: cuenta((r) => r.estado === E.PENDIENTE_VALIDACION),
    formalizados: cuenta((r) => r.estado === E.FORMALIZADO),
    ambiguedades: reqs.reduce((a, r) => a + (r.traza.extraccion?.marcados.length ?? 0), 0),
    actualizadoEn: reqs.map((r) => r.historial.at(-1).en).sort().at(-1) ?? p.creadoEn,
  };
}

export const proyectos = () => db.proyectos.map(resumenProyecto);

export function proyecto(id) {
  const p = db.proyectos.find((x) => x.id === id);
  if (!p) throw new Error(`No existe el proyecto ${id}`);
  return {
    ...resumenProyecto(p),
    lista: db.requisitos.filter((r) => r.proyectoId === id).map((r) => vista(r)),
  };
}

export function crearProyecto({ nombre, descripcion = "" }) {
  const id = `P-${String(db.siguienteProyecto++).padStart(2, "0")}`;
  db.proyectos.push({ id, nombre: nombre.trim(), descripcion: descripcion.trim(), creadoEn: new Date().toISOString() });
  guardar();
  return id;
}

/* ---------- ambigüedades: cada término y dónde/cómo se resolvió ---------- */
const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

export function ambiguedades() {
  const nombres = Object.fromEntries(db.proyectos.map((p) => [p.id, p.nombre]));
  const grupos = new Map();
  for (const reg of db.requisitos) {
    const r = vista(reg);
    const t = r.traza;
    for (const m of t.extraccion?.marcados ?? []) {
      const clave = norm(m.texto);
      if (!grupos.has(clave)) grupos.set(clave, { termino: m.texto, tipo: m.tipo, fuente: m.fuente, apariciones: [] });
      // Lectura adoptada: la del arbitraje, o la A si hubo consenso o aceptación directa
      const clave2 = t.resolucion?.via === "arbitraje" ? t.resolucion.eleccion : "A";
      const lectura = (k) => t.clasificacion?.interpretaciones[k]?.lecturas.find((l) => norm(l.termino) === clave)?.significado ?? null;
      grupos.get(clave).apariciones.push({
        requisitoId: r.id,
        texto: r.texto,
        marcados: t.extraccion.marcados,
        proyectoId: r.proyectoId,
        proyecto: nombres[r.proyectoId],
        estado: r.estado,
        via: t.resolucion?.via ?? null,
        similitud: t.divergencia?.similitud ?? null,
        rondas: t.debate?.rondas.length ?? 0,
        lecturas: { A: lectura("A"), B: lectura("B") },
        adoptada: t.resolucion ? lectura(clave2) : null,
      });
    }
  }
  return [...grupos.values()]
    .map((g) => {
      const resueltas = [...new Set(g.apariciones.map((a) => a.adoptada).filter(Boolean).map(norm))];
      return { ...g, inconsistente: resueltas.length > 1 };
    })
    .sort((a, b) => b.apariciones.length - a.apariciones.length || a.termino.localeCompare(b.termino, "es"));
}

/* ---------- flujo de conocimiento continuo (al estilo KMoS-SSA) ---------- */
export function flujo(proyectoId) {
  const reqs = db.requisitos.filter((r) => !proyectoId || r.proyectoId === proyectoId).map((r) => ({ v: vista(r), reg: r }));
  const ciclos = [...new Set(reqs.map((x) => x.v.ciclo))].sort((a, b) => a - b);
  const medir = (lista) => {
    const n = (f) => lista.reduce((a, x) => a + f(x), 0);
    const t = (x) => x.v.traza;
    const h = (x, e) => x.reg.humano.filter((y) => y.estado === e).length + x.reg.intentosPrevios.reduce((a, i) => a + i.humano.filter((y) => y.estado === e).length, 0);
    return {
      elicitacion: { requisitos: lista.length, terminos: n((x) => t(x).extraccion?.terminos.length ?? 0), marcados: n((x) => t(x).extraccion?.marcados.length ?? 0) },
      estructuracion: { interpretaciones: n((x) => (t(x).clasificacion ? 2 : 0)), similitudes: n((x) => (t(x).divergencia ? 1 : 0)), directos: n((x) => (t(x).divergencia?.decision === "directo" ? 1 : 0)) },
      enriquecimiento: { debates: n((x) => (t(x).debate ? 1 : 0)), rondas: n((x) => t(x).debate?.rondas.length ?? 0), consensos: n((x) => (t(x).resolucion?.via === "consenso" ? 1 : 0)), arbitrajes: n((x) => (t(x).resolucion?.via === "arbitraje" ? 1 : 0)) },
      generacion: { artefactos: n((x) => (t(x).artefactos ? 3 : 0)), lel: n((x) => (t(x).artefactos ? 1 : 0)) },
      validacion: { validados: n((x) => h(x, E.VALIDADO)), rechazados: n((x) => h(x, E.RECHAZADO)), formalizados: n((x) => h(x, E.FORMALIZADO)), reprocesos: n((x) => x.reg.intentosPrevios.length) },
    };
  };
  const porCiclo = ciclos.map((c) => ({ ciclo: c, ...medir(reqs.filter((x) => x.v.ciclo === c)) }));
  const total = medir(reqs);
  const humanas = total.validacion.validados + total.validacion.rechazados + total.validacion.formalizados;
  const agentes = {
    extractor: total.elicitacion.requisitos - reqs.filter((x) => !x.v.traza.extraccion).length,
    clasificador: total.estructuracion.interpretaciones / 2 + total.enriquecimiento.rondas * 2,
    critico: total.enriquecimiento.rondas + total.enriquecimiento.arbitrajes,
    modelador: total.generacion.lel,
    humano: humanas,
  };
  return {
    ciclos: porCiclo,
    total,
    agentes,
    interacciones: Object.values(agentes).reduce((a, b) => a + b, 0) + total.estructuracion.similitudes,
  };
}
