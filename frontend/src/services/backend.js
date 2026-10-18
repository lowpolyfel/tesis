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
import { BASE_URL, borrar, get, patch, post, postArchivo, postFlujo, put } from "./http";

const id = (x) => encodeURIComponent(x);

/* ======================= Cuenta (app/api/routes/auth.py) ======================= */
/*
 * La sesión es una cookie HttpOnly que pone el backend. Los errores traen
 * e.detalle = { codigo, mensaje }: "sin_verificar" pide el código del correo,
 * "espera" trae `segundos` para volver a pedirlo.
 * Las que dejan algo pendiente responden { pendiente, correo, sin_smtp, minutos }:
 * sin_smtp = el backend no tiene correo configurado y escribió el código en su consola.
 */
export const miCuenta = () => get("/auth/yo");
export const registrarCuenta = ({ nombre, correo, contrasena }) => post("/auth/registro", { nombre, correo, contrasena });
export const verificarCodigo = (correo, codigo) => post("/auth/verificar", { correo, codigo });
export const reenviarCodigo = (correo) => post("/auth/reenviar", { correo });
/** → la cuenta, o { pendiente: "entrar", … } si el backend pide además un código */
export const entrar = (correo, contrasena) => post("/auth/entrar", { correo, contrasena });
export const salir = () => post("/auth/salir");
export const pedirRestablecer = (correo) => post("/auth/recuperar", { correo });
export const restablecerContrasena = ({ correo, codigo, contrasena }) => post("/auth/restablecer", { correo, codigo, contrasena });
/** Contraseñas: mínimo del backend (Contrasena en app/api/routes/auth.py) */
export const CONTRASENA_MIN = 8;

/* ======================= Servidor ======================= */
export const salud = () => get("/salud");
/**
 * Antes de analizar (app/preparacion.py): { listo, base: {ok, tipo, host, ms, error, aviso},
 * ollama: {ok, url, ms, error} | null, modelos: [{modelo, proveedor, tipo, roles, disponible, cargado, error}] }
 */
export const prepararAnalisis = () => get("/preparacion");
/** Deja en memoria un modelo de Ollama del análisis → { modelo, ms } */
export const cargarModelo = (modelo) => post("/preparacion/cargar", { modelo });
export const obtenerConfiguracion = () => get("/configuracion");
export const obtenerCatalogos = () => get("/catalogos");
export const obtenerCola = () => get("/cola");
/** A qué Mongo está conectado (atlas | local | otro, o el respaldo JSON), medido en el momento */
export const probarConexion = () => get("/conexion");

/* ======================= Proyectos ======================= */
export const listarProyectos = () => get("/proyectos");
export const crearProyecto = ({ nombre, descripcion, contexto }) =>
  post("/proyectos", { nombre, descripcion: descripcion || null, contexto: contexto || null });
/** Límite del contexto general del proyecto (CONTEXTO_MAX en app/api/routes/proyectos.py) */
export const CONTEXTO_MAX = 4000;
export const obtenerProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}`);
export const editarProyecto = (proyectoId, cambios) => patch(`/proyectos/${id(proyectoId)}`, cambios);
/** Borra el proyecto con sus requisitos, léxico, documentos y análisis (409 si algo se está analizando) */
export const borrarProyecto = (proyectoId) => borrar(`/proyectos/${id(proyectoId)}`);
export const resumenProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/resumen`);
export const requisitosDeProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/requisitos`);

/* ======================= Documentos y carga ======================= */
/** Sube un PDF (con texto extraíble) o .txt; el backend lo separa en requisitos candidatos */
export const subirDocumento = (proyectoId, archivo) => postArchivo(`/proyectos/${id(proyectoId)}/documentos`, "archivo", archivo);
export const obtenerDocumento = (documentoId) => get(`/documentos/${id(documentoId)}`);
export const documentosDeProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/documentos`);
/** Texto pegado → requisitos candidatos (no guarda nada) */
/** El Revisor reconoce los requisitos en cualquier redacción (ADR 0023); si falla, patrones. → Separacion con `metodo` */
export const separarRequisitos = (texto, proyectoId) => post("/requisitos/separar", { texto, proyecto_id: proyectoId ?? null });
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
/** Borra el requisito con lo que salió de él (409 si se está analizando o espera turno) */
export const borrarRequisito = (reqId) => borrar(`/requisitos/${id(reqId)}`);
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
/** Mapa conceptual guardado (ADR 0020) → { mapa | null (no hay o ya no está al día), requisitos } */
export const mapaConceptual = (proyectoId, reqIds) => get(`/proyectos/${id(proyectoId)}/mapa-conceptual`, seleccion(reqIds));
/**
 * Genera el mapa conceptual y avisa cada paso: onEvento({tipo: "paso", id, texto, estado, detalle}),
 * ({tipo: "mapa", mapa}) al final o ({tipo: "error", mensaje}). `nuevo` lo regenera aunque esté guardado.
 */
export const generarMapaConceptual = (proyectoId, reqIds, { nuevo = false, onEvento, senal } = {}) =>
  postFlujo(`/proyectos/${id(proyectoId)}/mapa-conceptual`, { req_ids: reqIds ?? [], nuevo }, onEvento, senal);
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

/* ======================= Modelos de los agentes, por cuenta (ADR 0021) ======================= */
/** { catalogo: [{id, nombre, tipo, base_url, pide_clave, pide_url, modelos, ayuda, url_ayuda}],
 *    agentes: [{rol, nombre, proveedor, modelo, propio, servidor}], proveedores: {id: {base_url, tiene_clave, final}} } */
export const obtenerModelos = () => get("/cuenta/modelos");
/** agentes: {rol: {proveedor, modelo} | null}; proveedores: {id: {base_url?, api_key?}} ("" deja la clave, null la borra) */
export const guardarModelos = (cambios) => put("/cuenta/modelos", cambios);
/** → { ok, ms, error } con lo del formulario (sin api_key usa la guardada) */
export const probarModelo = (datos) => post("/cuenta/modelos/probar", datos);
/** Los modelos de texto que el proveedor ofrece ahora con esa clave (o la guardada) → { modelos: [{id, nombre}], error } */
export const listarModelos = (datos) => post("/cuenta/modelos/listar", datos);
/** Vuelve a analizar requisitos que terminaron en error → { ciclo, req_ids } (las versiones nuevas) */
/** Cancela el análisis y descarta por completo → { descartados, deteniendo } (estos se borran al terminar su paso) */
export const cancelarRequisitos = (proyectoId, reqIds) => post(`/proyectos/${id(proyectoId)}/cancelar`, { req_ids: reqIds });
export const reanalizarRequisitos = (proyectoId, reqIds) => post(`/proyectos/${id(proyectoId)}/reanalizar`, { req_ids: reqIds });

/* ======================= Ficha del contexto y triaje (ADR 0022) ======================= */
/** { ficha: {ficha, markdown, modelo, creada} | null, al_dia, tiene_contexto } */
export const fichaContexto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/ficha`);
export const armarFicha = (proyectoId) => post(`/proyectos/${id(proyectoId)}/ficha`, {});
/** → { resultados: [{indice, veredicto: claro|ambiguo|incompleto|null, motivo, faltantes, preguntas,
 *       terminos_ambiguos, origen}], modelo, aviso, ficha } */
/** Igual que separarRequisitos, avisando cada paso (NDJSON): onEvento({tipo: paso|tanda|resultado|error, …}) */
export const separarRequisitosFlujo = (texto, proyectoId, onEvento, senal) =>
  postFlujo("/requisitos/separar/flujo", { texto, proyecto_id: proyectoId ?? null }, onEvento, senal);
/** Igual que triarRequisitos, avisando cada paso (NDJSON) */
export const triarRequisitosFlujo = (proyectoId, textos, onEvento, senal) =>
  postFlujo(`/proyectos/${id(proyectoId)}/triaje/flujo`, { requisitos: textos }, onEvento, senal);
export const triarRequisitos = (proyectoId, textos) => post(`/proyectos/${id(proyectoId)}/triaje`, { requisitos: textos });

/* ======================= Versión 2: de la entrevista a los requisitos (ADR 0024) ======================= */
/** En qué va cada fase → { fases: [{id, disponible, hecho, motivo, …}], siguiente, entrevistas, lexico } */
export const fasesDeProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/fases`);

/* ---- Entrevistas ---- */
/** Cómo se lee el texto (no guarda nada) → { turnos: [{n, hablante, texto, pagina}], modo, hablantes, advertencias, caracteres } */
export const vistaPreviaEntrevista = (proyectoId, texto) => post(`/proyectos/${id(proyectoId)}/entrevistas/vista-previa`, { texto });
/** PDF con texto o .txt → { titulo, texto, origen: {tipo, archivo, paginas}, vista } (no guarda nada) */
export const leerArchivoEntrevista = (proyectoId, archivo) => postArchivo(`/proyectos/${id(proyectoId)}/entrevistas/archivo`, "archivo", archivo);
/** La guarda y la encola: los agentes proponen su LEL → la entrevista (sin turnos), 202 */
export const crearEntrevista = (proyectoId, { titulo, texto, origen }) => post(`/proyectos/${id(proyectoId)}/entrevistas`, { titulo, texto, origen: origen ?? null });
export const entrevistasDeProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/entrevistas`);
/** Completa: turnos, ficha (participantes, necesidades…), vaguedad, resumen, estado */
export const obtenerEntrevista = (entrevistaId) => get(`/entrevistas/${id(entrevistaId)}`);
export const renombrarEntrevista = (entrevistaId, titulo) => patch(`/entrevistas/${id(entrevistaId)}`, { titulo });
export const bitacoraDeEntrevista = (entrevistaId) => get(`/entrevistas/${id(entrevistaId)}/bitacora`);
export const cancelarEntrevista = (entrevistaId) => post(`/entrevistas/${id(entrevistaId)}/cancelar`);
export const reprocesarEntrevista = (entrevistaId) => post(`/entrevistas/${id(entrevistaId)}/reprocesar`);
export const borrarEntrevista = (entrevistaId) => borrar(`/entrevistas/${id(entrevistaId)}`);

/* ---- LEL interactivo y memoria ---- */
/** { entradas, resumen: {propuesto, validado, corregido, descartado, ambiguos, completo}, acuerdos, procesando } */
export const lexicoDeProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/lexico`);
export const validarTermino = (entradaId) => post(`/lexico/${id(entradaId)}/validar`);
/** cambios: {simbolo?, tipo?, nocion?, impacto?, intencion?, sinonimos?}; alternativa: "I2" para partir de otra intención */
export const corregirTermino = (entradaId, cambios, alternativa = null) => post(`/lexico/${id(entradaId)}/corregir`, { cambios, alternativa });
export const descartarTermino = (entradaId, motivo = null) => post(`/lexico/${id(entradaId)}/descartar`, { motivo });
export const restaurarTermino = (entradaId) => post(`/lexico/${id(entradaId)}/restaurar`);
export const agregarTermino = (proyectoId, entrada) => post(`/proyectos/${id(proyectoId)}/lexico`, entrada);
export const validarSinAmbiguedad = (proyectoId) => post(`/proyectos/${id(proyectoId)}/lexico/validar-sin-ambiguedad`);
export const memoriaDeProyecto = (proyectoId) => get(`/proyectos/${id(proyectoId)}/memoria`);
export const olvidarAcuerdo = (aprendizajeId) => borrar(`/memoria/${id(aprendizajeId)}`);

/* ---- Mapa, metas y requisitos (fase = "mapa" | "metas" | "requisitos") ---- */
/** { documento | null, al_dia, disponible, motivo, hecho, generando } */
export const obtenerFase = (proyectoId, fase) => get(`/proyectos/${id(proyectoId)}/fases/${fase}`);
/** NDJSON: onEvento({tipo: "paso", id, texto, estado, detalle} | {tipo: "resultado", documento} | {tipo: "error", mensaje}) */
export const generarFase = (proyectoId, fase, { onEvento, senal } = {}) => postFlujo(`/proyectos/${id(proyectoId)}/fases/${fase}/generar`, {}, onEvento, senal);
/** Lo que la persona editó y validó (el contenido completo) → la vista de la fase con el documento nuevo */
export const guardarFase = (proyectoId, fase, contenido) => put(`/proyectos/${id(proyectoId)}/fases/${fase}`, { contenido });
export const conservarFase = (proyectoId, fase) => post(`/proyectos/${id(proyectoId)}/fases/${fase}/conservar`);
export const urlMermaidMapa = (proyectoId) => `${BASE_URL}/proyectos/${id(proyectoId)}/fases/mapa/mermaid`;
export const urlEspecificacion = (proyectoId) => `${BASE_URL}/proyectos/${id(proyectoId)}/fases/requisitos/markdown`;
export const especificacionMarkdown = (proyectoId) => get(`/proyectos/${id(proyectoId)}/fases/requisitos/markdown`);

/* ---- Calibración sobre entrevistas (ADR 0026) ---- */
/** El informe en vivo: rejilla, distribución y, con ground truth, ROC, AUC, intervalos y por tipo */
export const calibracionEntrevistas = (proyectoId, rejilla = {}) => get(`/proyectos/${id(proyectoId)}/calibracion/entrevistas`, rejilla);
/** Términos de la entrevista y su ground truth; con `sistema`, también la similitud y la decisión */
export const etiquetasEntrevista = (entrevistaId, sistema = false) =>
  get(`/entrevistas/${id(entrevistaId)}/etiquetas`, sistema ? { sistema: true } : undefined);
export const guardarEtiquetas = (entrevistaId, { anotador, a_ciegas, etiquetas }) =>
  put(`/entrevistas/${id(entrevistaId)}/etiquetas`, { anotador, a_ciegas, etiquetas });
export const corridasCalibracion = (proyectoId) => get(`/proyectos/${id(proyectoId)}/calibraciones`);
export const guardarCorridaCalibracion = (proyectoId, nota, rejilla = {}) => {
  const q = new URLSearchParams(Object.entries(rejilla).filter(([, v]) => v != null && v !== "")).toString();
  return post(`/proyectos/${id(proyectoId)}/calibraciones${q ? `?${q}` : ""}`, { nota: nota || null });
};
export const corridaCalibracion = (calibracionId) => get(`/calibraciones/${id(calibracionId)}`);
export const borrarCorridaCalibracion = (calibracionId) => borrar(`/calibraciones/${id(calibracionId)}`);
export const urlOverleaf = (calibracionId) => `${BASE_URL}/calibraciones/${id(calibracionId)}/overleaf.zip`;
