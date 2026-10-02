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
 * Registra los requisitos confirmados dentro de un proyecto (un ciclo nuevo)
 * y arranca su procesamiento.
 * Futuro: POST /proyectos/:id/requisitos [{ texto, origen }] → { ids }
 */
export const crearRequisitos = (lista, proyectoId) => responder(() => ({ ids: db.crearRequisitos(lista, proyectoId) }));

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

/* ======================= Proyectos ======================= */

/** Futuro: GET /proyectos → resumen de cada proyecto */
export const listarProyectos = () => responder(() => db.proyectos());

/** Futuro: GET /proyectos/:id → proyecto con sus requisitos (traza completa) */
export const obtenerProyecto = (id) => responder(() => db.proyecto(id));

/** Futuro: POST /proyectos { nombre, descripcion } → { id } */
export const crearProyecto = (datos) => responder(() => ({ id: db.crearProyecto(datos) }));

/* ======================= Ambigüedades ======================= */

/**
 * Términos ambiguos detectados en todos los requisitos, con dónde aparecen y
 * qué lectura se adoptó en cada uno. Futuro: GET /ambiguedades
 */
export const obtenerAmbiguedades = () => responder(() => db.ambiguedades());

/* ======================= Flujo de conocimiento ======================= */

/**
 * Métricas por ciclo y por fase del flujo de conocimiento continuo.
 * proyectoId opcional (todos si se omite). Futuro: GET /flujo?proyecto=
 */
export const obtenerFlujo = (proyectoId) => responder(() => db.flujo(proyectoId));

/* ======================= Solo para la simulación ======================= */

/** Restaura los datos de prueba. Desaparece con el backend real. */
export const reiniciarDatosDePrueba = () => responder(() => db.reiniciar());
