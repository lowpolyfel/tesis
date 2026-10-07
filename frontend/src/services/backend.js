/*
 * TODAS las llamadas al backend real (FastAPI). Las pantallas no arman URLs.
 * Las formas de las respuestas están documentadas en el backend:
 *   - requisitos y trazas: app/api/routes/requisitos.py
 *   - vista por término, resumen, ambigüedades y flujo: app/analisis (ADR 0015)
 *   - documentos: app/documentos (ADR 0009)
 *   - comparación entre requisitos: app/comparacion (ADR 0012, exploratoria)
 *   - calibración: app/calibracion (ADR 0013)
 *   - corpus y evaluación: app/evaluacion (ADR 0014)
 *   - metas y Big Picture: app/artefactos (ADR 0011)
 */
import { get, patch, post, postArchivo } from "./http";

const id = (x) => encodeURIComponent(x);

/* ======================= Servidor ======================= */
export const salud = () => get("/salud");
export const obtenerConfiguracion = () => get("/configuracion");
export const obtenerCatalogos = () => get("/catalogos");
export const obtenerCola = () => get("/cola");

/* ======================= Proyectos ======================= */
export const listarProyectos = () => get("/proyectos");
export const crearProyecto = ({ nombre, descripcion, contexto }) =>
  post("/proyectos", { nombre, descripcion: descripcion || null, contexto: contexto || null });
/** Límite del contexto general del proyecto (CONTEXTO_MAX en app/api/routes/proyectos.py) */
export const CONTEXTO_MAX = 4000;
export const obtenerProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}`);
export const editarProyecto = (proyectoId, cambios) => patch(`/proyectos/${id(proyectoId)}`, cambios);
export const resumenProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/resumen`);
export const requisitosDeProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/requisitos`);

/* ======================= Documentos y carga ======================= */
/** Sube un PDF (con texto extraíble) o .txt; el backend lo separa en requisitos candidatos */
export const subirDocumento = (proyectoId, archivo) => postArchivo(`/proyectos/${id(proyectoId)}/documentos`, "archivo", archivo);
export const obtenerDocumento = (documentoId) => get(`/documentos/${id(documentoId)}`);
export const documentosDeProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/documentos`);
/** Texto pegado → requisitos candidatos (no guarda nada) */
export const separarRequisitos = (texto) => post("/requisitos/separar", { texto });
/**
 * Los requisitos confirmados por el humano entran a la cola en un ciclo nuevo.
 * requisitos: [{ texto, origen?: {documento_id, archivo, pagina, indice, marca, texto_original, reproceso_de} }]
 * → { proyecto_id, ciclo, req_ids }
 * Límites del contrato (EntradaRequisitos y RequisitoNuevo en app/api/routes/proyectos.py):
 * la separación no los aplica, así que la confirmación los revisa antes de enviar.
 */
export const LIMITES_CARGA = Object.freeze({ requisitos: 200, caracteres: 2000 });
export const cargarRequisitos = (proyectoId, requisitos) => post(`/proyectos/${id(proyectoId)}/requisitos`, { requisitos });
/** Un solo requisito (proyecto General si no se indica) → { req_id, estado } */
export const procesarRequisito = (texto, proyectoId) => post("/procesar", { texto, ...(proyectoId ? { proyecto_id: proyectoId } : {}) });
/** Vuelve a procesar un requisito como uno nuevo del mismo proyecto (el original queda en la historia) */
export const reprocesarRequisito = (vista) => cargarRequisitos(vista.proyecto_id, [{
  texto: vista.texto,
  origen: { ...(vista.origen ?? {}), reproceso_de: vista.req_id },
}]);

/* ======================= Requisitos ======================= */
/** Vista por término (la que usan las pantallas) */
export const obtenerRequisito = (reqId) => get(`/requisitos/${id(reqId)}`);
/** Traza cruda: todos los mensajes del protocolo */
export const obtenerTraza = (reqId) => get(`/traza/${id(reqId)}`);
export const listarTrazas = (proyectoId) => get("/trazas", { proyecto_id: proyectoId });
/**
 * Validación humana. decision: "aprobar" | "rechazar".
 * interpretacionesEditadas: { termino: {id, significado, parafrasis_del_requisito} } para elegir otra o reescribirla.
 */
export const validarRequisito = (reqId, { decision, interpretacionesEditadas = {}, comentario = null }) =>
  post(`/validar/${id(reqId)}`, { decision, interpretaciones_editadas: interpretacionesEditadas, comentario: comentario || null });
export const artefactosDeRequisito = (reqId) => get(`/requisitos/${id(reqId)}/artefactos`);
/**
 * Corregir un resultado ya formalizado (ADR 0017); cada corrección queda en la traza.
 * cambios: { requisito_reescrito?, tipo_requisito?, categoria?, supuestos? }
 */
export const corregirFormalizacion = (reqId, cambios) => patch(`/requisitos/${id(reqId)}/formalizacion`, cambios);
/** cambios: { simbolo?, tipo?, nocion?, impacto? } de la entrada del LEL de `termino` */
export const corregirLel = (reqId, termino, cambios) => patch(`/requisitos/${id(reqId)}/lel/${id(termino)}`, cambios);

/* ======================= LEL y artefactos de proyecto ======================= */
export const obtenerLel = (proyectoId) => get("/lel", { proyecto_id: proyectoId });
/* `reqIds`: solo esos requisitos (lista); vacío o ausente, todos los formalizados */
const seleccion = (reqIds) => ({ req_ids: reqIds?.length ? reqIds.join(",") : undefined });
export const metasDeProyecto = (proyectoId, reqIds) => get(`/proyectos/${id(proyectoId)}/metas`, seleccion(reqIds));
export const bigPictureDeProyecto = (proyectoId, reqIds) => get(`/proyectos/${id(proyectoId)}/big-picture`, seleccion(reqIds));
/** Requisitos funcionales y no funcionales reescritos, con supuestos, y el glosario */
export const especificacionDeProyecto = (proyectoId, reqIds) => get(`/proyectos/${id(proyectoId)}/especificacion`, seleccion(reqIds));

/* ======================= Análisis de proyecto ======================= */
export const ambiguedadesDeProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/ambiguedades`);
export const flujoDeProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/flujo`);

/* ======================= Comparación entre requisitos (exploratoria) ======================= */
export const compararRequisitos = (proyectoId) => post(`/proyectos/${id(proyectoId)}/comparaciones`, {});
export const comparacionesDeProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/comparaciones`);
export const obtenerComparacion = (comparacionId) => get(`/comparaciones/${id(comparacionId)}`);

/* ======================= Calibración (solo análisis de sensibilidad) ======================= */
export const calibracionDeProyecto = (proyectoId, rejilla = {}) => get(`/proyectos/${id(proyectoId)}/calibracion`, rejilla);
export const calibracionGeneral = (rejilla = {}) => get("/calibracion", rejilla);

/* ======================= Corpus y evaluación ======================= */
export const listarCorpus = () => get("/corpus");
export const obtenerCorpus = (nombre) => get(`/corpus/${id(nombre)}`);
export const evaluar = (corpus, nombre) => post("/evaluaciones", { corpus, ...(nombre ? { nombre } : {}) });
export const listarEvaluaciones = () => get("/evaluaciones");
export const obtenerEvaluacion = (evaluacionId) => get(`/evaluaciones/${id(evaluacionId)}`);
