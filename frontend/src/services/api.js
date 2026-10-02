/*
 * TODAS las llamadas al backend.
 *
 * Hoy cada función es un stub que responde con datos de prueba (mockDb) tras
 * un pequeño retardo. Cuando exista la API de FastAPI, solo cambia el
 * cuerpo de estas funciones: el comentario de cada una indica el endpoint
 * previsto. Las pantallas no saben de dónde vienen los datos.
 *
 * El sondeo de estado (proceso lento de los agentes) vive en polling.js y
 * solo usa obtenerEstadoRequisito / obtenerRequisito / obtenerEjecucion.
 */
import * as db from "./mockDb";
import { leerArchivo } from "./documentos";

// export const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const LATENCIA_MS = 250;
const responder = (fn) => new Promise((resolve, reject) => {
  setTimeout(() => {
    try { resolve(structuredClone(fn())); } catch (e) { reject(e); }
  }, LATENCIA_MS);
});

/* ======================= Carga de requisitos ======================= */

/** Texto de un archivo .txt o .pdf. Se lee en el navegador (pdfjs-dist). */
export const extraerTextoDeArchivo = (file) => leerArchivo(file);

/**
 * Separa un texto en requisitos individuales para que el usuario confirme.
 * Futuro: POST /requisitos/separar { texto } → [{ texto }]
 */
export function separarRequisitos(texto) {
  return responder(() => {
    // Reconstruye párrafos: en un PDF un requisito largo ocupa varios renglones.
    // Empieza uno nuevo con una viñeta/numeración, tras un renglón vacío o
    // cuando el anterior cerró con punto; si no, el renglón es continuación.
    const MARCA = /^(?:[-•*]|\d+[.)-]|RF-?\d+[:.)-]?|R\d+[:.)-]?)\s*/i;
    const bloques = [];
    let corte = true;
    for (const crudo of texto.split(/\r?\n/)) {
      const l = crudo.trim();
      if (!l) { corte = true; continue; }
      const limpio = l.replace(MARCA, "").trim();
      const previo = bloques.at(-1);
      if (corte || MARCA.test(l) || /[.:;]$/.test(previo)) bloques.push(limpio);
      else if (previo.endsWith("-")) bloques[bloques.length - 1] = previo.slice(0, -1) + limpio; // palabra partida
      else bloques[bloques.length - 1] = `${previo} ${limpio}`;
      corte = false;
    }
    const lineas = bloques.filter(Boolean);
    const piezas = [];
    for (const linea of lineas) {
      // Una línea con varias oraciones obligatorias se separa por oración
      const oraciones = linea.split(/(?<=\.)\s+(?=[A-ZÁÉÍÓÚÑ])/);
      for (const o of oraciones) {
        if (/(?<!\p{L})(debe|deber[áa]|podr[áa]|permitir[áa]|tiene que)(?!\p{L})/iu.test(o)) piezas.push({ texto: o.trim() });
      }
    }
    return piezas;
  });
}

/**
 * Registra los requisitos confirmados y arranca su procesamiento.
 * Futuro: POST /requisitos [{ texto, origen }] → { ids }
 */
export const crearRequisitos = (lista) => responder(() => ({ ids: db.crearRequisitos(lista) }));

/* ======================= Requisitos ======================= */

/** Futuro: GET /requisitos → resumen de cada requisito */
export const listarRequisitos = () => responder(() => db.listarRequisitos());

/** Futuro: GET /requisitos/:id → requisito con traza completa */
export const obtenerRequisito = (id) => responder(() => db.obtenerRequisito(id));

/** Ligero, para el sondeo. Futuro: GET /requisitos/:id/estado → { estado, actualizadoEn } */
export const obtenerEstadoRequisito = (id) => responder(() => db.obtenerEstadoRequisito(id));

/** rechazado → cargado, con la configuración vigente. Futuro: POST /requisitos/:id/reprocesar */
export const reprocesarRequisito = (id) => responder(() => db.reprocesar(id));

/* ======================= Validación de artefactos ======================= */

/** Futuro: PUT /requisitos/:id/artefactos/borrador */
export const guardarBorrador = (id, artefactos) => responder(() => db.guardarBorrador(id, artefactos));

/** pendiente_validacion → validado. Futuro: POST /requisitos/:id/validar { artefactos, comentario, editado } */
export const validarArtefactos = (id, artefactos, opciones) => responder(() => db.validar(id, artefactos, opciones));

/** pendiente_validacion → rechazado. Futuro: POST /requisitos/:id/rechazar { comentario } */
export const rechazarArtefactos = (id, comentario) => responder(() => db.rechazar(id, comentario));

/** validado → formalizado (entra al LEL). Futuro: POST /requisitos/:id/formalizar */
export const formalizarRequisito = (id) => responder(() => db.formalizar(id));

/* ======================= LEL ======================= */

/** Futuro: GET /lel */
export const obtenerLel = () => responder(() => db.lel());

/* ======================= Catálogos ======================= */

/** tipo: "mexicanismos" | "vaguedad". Futuro: GET /catalogos/:tipo */
export const obtenerCatalogo = (tipo) => responder(() => db.catalogo(tipo));

/** Futuro: PUT /catalogos/:tipo */
export const guardarCatalogo = (tipo, filas) => responder(() => db.guardarCatalogo(tipo, filas));

/* ======================= Calibración ======================= */

/** Futuro: GET /configuracion → { config, disponibles, historial } */
export const obtenerConfiguracion = () => responder(() => db.configuracion());

/** Se aplica a lo que se procese después, sin reiniciar. Futuro: PUT /configuracion */
export const guardarConfiguracion = (config, nota) => responder(() => db.guardarConfiguracion(config, nota));

/* ======================= Corpus y evaluación ======================= */

/** Futuro: GET /corpus */
export const obtenerCorpus = () => responder(() => db.obtenerCorpus());

/** Lanza el corpus completo. Futuro: POST /evaluaciones → { id } */
export const ejecutarCorpus = () => responder(() => ({ id: db.lanzarEjecucion() }));

/** Futuro: GET /evaluaciones/:id → { estado, procesados, total, resultados } */
export const obtenerEjecucion = (id) => responder(() => db.ejecucion(id));

/** Futuro: GET /evaluaciones */
export const listarEjecuciones = () => responder(() => db.ejecuciones());

/* ======================= Solo para la simulación ======================= */

/** Restaura los datos de prueba. Desaparece con el backend real. */
export const reiniciarDatosDePrueba = () => responder(() => db.reiniciar());
