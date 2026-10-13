import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useOrb, usePoseEsfera } from "../components/orb/useOrb";
import {
  CONTEXTO_MAX, LIMITES_CARGA, cargarRequisitos, editarProyecto, obtenerProyecto, subirDocumento,
  separarRequisitosFlujo, triarRequisitos, triarRequisitosFlujo,
} from "../services/backend";
import Pasos from "../escena/Pasos";
import { recordarProyecto } from "../components/proyectoRecordado";
import { Volver } from "../components/ui";

/*
 * Analizar requisitos dentro de un proyecto. La esfera recibe el archivo:
 *   inicio    → la esfera al centro: «suelta tu archivo»
 *   contexto  → la esfera a un lado; se escribe el contexto general del proyecto
 *   pegar     → la esfera se hace a un lado; aparece el texto
 *   leyendo   → la esfera "lee" (piensa) en el centro
 *   confirmar → la esfera a la izquierda; a la derecha, los requisitos detectados
 *   revisando → la esfera piensa: el Revisor los compara con la ficha del contexto
 *   triaje    → separados: los que se entienden, los ambiguos (irán con revisión
 *               humana) y los poco detallados, que hay que precisar antes (ADR 0022)
 *
 * El backend lee el PDF (texto extraíble; sin OCR por alcance) y lo separa en
 * requisitos candidatos con su página y numeración original. Lo que descarta
 * se muestra y lo que la limpieza quitó también: nada se pierde en silencio.
 * La persona confirma la separación; el Revisor compara cada requisito con el
 * contexto y los poco detallados se precisan antes de analizar. Desde ahí todo
 * sigue solo y se le pregunta si los agentes no llegan a un acuerdo (ADR 0017) o
 * si el requisito era ambiguo.
 */
const POSES = {
  inicio: { d: { x: 0, y: -0.08, s: 1.05 }, m: { x: 0, y: -0.16, s: 0.8 } },
  arrastre: { d: { x: 0, y: -0.08, s: 1.3 }, m: { x: 0, y: -0.16, s: 0.95 } },
  contexto: { d: { x: 0.3, y: 0.02, s: 0.85 }, m: { x: 0, y: -0.33, s: 0.45 } },
  pegar: { d: { x: -0.26, y: 0, s: 0.85 }, m: { x: 0, y: -0.33, s: 0.45 } },
  leyendo: { d: { x: 0, y: -0.04, s: 0.9 }, m: { x: 0, y: -0.1, s: 0.7 } },
  confirmar: { d: { x: -0.29, y: 0.02, s: 0.78 }, m: { x: 0, y: -0.36, s: 0.4 } },
};
POSES.revisando = POSES.leyendo;
POSES.triaje = POSES.confirmar;
const MIN_LECTURA_MS = 1400;
// la esfera respira por estos tonos mientras el Revisor lee o revisa (sin amarillo)
const RESPIRO = ["listening", "clasificador", "mapa", "humano", "modelador"];
const RESPIRO_MS = 1800;
const PROGRESO_VACIO = { pasos: [], barra: null, sub: null, inicio: null };
const MOTIVOS = { titulo: "título", sin_verbo_obligacion: "sin «debe» ni «podrá»", sin_texto: "sin texto", no_es_requisito: "no es requisito" };

/* Un 422 del backend señala el requisito por su posición (base 0) en lo enviado; aquí se numeran desde 1 */
function explicar(e, enviadas) {
  if (!Array.isArray(e.detalle)) return e.message;
  return e.detalle.map((x) => {
    const [, campo, i] = x.loc ?? [];
    if (campo === "requisitos" && Number.isInteger(i)) return `Requisito ${enviadas[i]?.n ?? i + 1}: ${x.msg}`;
    return `${(x.loc ?? []).slice(1).join(".")}: ${x.msg}`;
  }).join(" · ");
}

/* Los que faltan por precisar se pueden apartar: se guardan en este navegador y se retoman al volver a Analizar */
const llaveApartados = (pid) => `apartados:${pid}`;
function leerApartados(pid) {
  try { return JSON.parse(localStorage.getItem(llaveApartados(pid)) || "[]"); } catch { return []; }
}
function guardarApartados(pid, textos) {
  try {
    if (textos.length) localStorage.setItem(llaveApartados(pid), JSON.stringify(textos));
    else localStorage.removeItem(llaveApartados(pid));
  } catch { /* sin almacenamiento: no se recuerdan */ }
}

export default function Analizar() {
  const orb = useOrb();
  const navigate = useNavigate();
  const { id: proyectoId } = useParams();
  const [proyecto, setProyecto] = useState(null);
  const [fase, setFase] = useState("inicio");
  const [arrastrando, setArrastrando] = useState(false);
  const [texto, setTexto] = useState("");
  const [origen, setOrigen] = useState("texto pegado");
  const [piezas, setPiezas] = useState([]);
  const [documento, setDocumento] = useState(null); // { documento_id, proyecto_id, archivo, paginas } si vino de un archivo
  const [descartados, setDescartados] = useState({ lista: [], total: 0 });
  const [advertencias, setAdvertencias] = useState([]); // lo que la limpieza quitó o no pudo leer
  const [error, setError] = useState(null);
  const [saliendo, setSaliendo] = useState(false);
  const [avisoTriaje, setAvisoTriaje] = useState(null);
  const [progreso, setProgreso] = useState(PROGRESO_VACIO); // pasos en vivo de la lectura o la revisión
  const [metodo, setMetodo] = useState(null); // { metodo: "ia" | "patrones", modelo } de la separación
  const archivo = useRef(null);
  // cada lectura o revisión abre un turno; cancelar lo cierra y lo que llegue después se ignora
  const turno = useRef({ n: 0, control: null, volver: "inicio" });
  const abrirTurno = (volver) => {
    turno.current.control?.abort();
    turno.current = { n: turno.current.n + 1, control: new AbortController(), volver };
    return turno.current;
  };
  const vigente = (t) => turno.current.n === t.n;
  const cancelarProceso = () => {
    const { volver, control } = turno.current;
    turno.current = { n: turno.current.n + 1, control: null, volver };
    control?.abort();
    setProgreso(PROGRESO_VACIO);
    setError(null);
    orb.setMood("idle");
    setFase(volver);
  };
  useEffect(() => () => turno.current.control?.abort(), []);
  const [apartados, setApartados] = useState(() => leerApartados(proyectoId));

  usePoseEsfera(POSES[arrastrando ? "arrastre" : fase], [fase, arrastrando]);

  useEffect(() => {
    recordarProyecto(proyectoId);
    obtenerProyecto(proyectoId).then(setProyecto).catch((e) => setError(e.message));
  }, [proyectoId]);

  const trabajando = fase === "leyendo" || fase === "revisando";
  useEffect(() => {
    if (!trabajando) orb.setMood(arrastrando || fase === "contexto" ? "listening" : "idle");
    orb.update("core", {
      label: fase === "leyendo" ? "Leyendo" : fase === "revisando" ? "Revisando" : fase === "confirmar" || fase === "triaje" ? `${piezas.length} requisitos` : null,
      sub: trabajando ? progreso.sub ?? (fase === "leyendo" ? origen : "con el contexto del proyecto") : null,
    });
  }, [orb, fase, trabajando, arrastrando, origen, piezas.length, progreso.sub]);
  // mientras el Revisor trabaja, la esfera respira cambiando de color: se nota que sigue vivo
  useEffect(() => {
    if (!trabajando) return undefined;
    let i = 0;
    const paso = () => { orb.setMood(RESPIRO[i++ % RESPIRO.length]); orb.poke(0.35); };
    paso();
    const t = setInterval(paso, RESPIRO_MS);
    return () => clearInterval(t);
  }, [orb, trabajando]);
  // cronómetro arriba de la esfera: se reinicia en cada fase que toma tiempo
  useEffect(() => {
    orb.update("core", { desde: trabajando ? Date.now() : null });
  }, [orb, fase, trabajando]);
  useEffect(() => () => orb.update("core", { label: null, sub: null, desde: null }), [orb]);

  /* ---- arrastrar y soltar sobre toda la pantalla (la esfera lo "atrae") ---- */
  // el manejador lee siempre la versión vigente (con el proyecto elegido ahora)
  const leerVigente = useRef(null);
  useEffect(() => {
    if (fase !== "inicio" && fase !== "pegar") return;
    let profundidad = 0;
    const entra = (e) => { if (e.dataTransfer?.types?.includes("Files")) { profundidad++; setArrastrando(true); } };
    const sale = () => { profundidad = Math.max(0, profundidad - 1); if (!profundidad) setArrastrando(false); };
    const sobre = (e) => e.preventDefault();
    const suelta = (e) => {
      e.preventDefault();
      profundidad = 0;
      setArrastrando(false);
      const f = e.dataTransfer.files?.[0];
      if (f) leerVigente.current?.(f);
    };
    window.addEventListener("dragenter", entra);
    window.addEventListener("dragleave", sale);
    window.addEventListener("dragover", sobre);
    window.addEventListener("drop", suelta);
    return () => {
      window.removeEventListener("dragenter", entra);
      window.removeEventListener("dragleave", sale);
      window.removeEventListener("dragover", sobre);
      window.removeEventListener("drop", suelta);
    };
  }, [fase]);

  /* r: una Separacion (texto pegado) o un Documento (archivo); los dos traen lo mismo */
  const mostrar = (r, volverA) => {
    const propuestos = r.requisitos_propuestos ?? [];
    setDescartados({ lista: r.fragmentos_descartados ?? [], total: r.total_descartados ?? 0 });
    setAdvertencias(r.advertencias ?? []);
    setMetodo({ metodo: r.metodo ?? "patrones", modelo: r.modelo ?? null });
    if (!propuestos.length && !r.total_descartados) {
      orb.setMood("error", { revertAfter: 1600 });
      setError(r.metodo === "ia"
        ? "No encontré requisitos: el Revisor no vio nada que el sistema deba hacer. Revisa el texto."
        : "No encontré requisitos. Cada uno debería decir qué «debe», «podrá» o «permitirá» hacer el sistema.");
      setFase(volverA);
      return;
    }
    // sin propuestos pero con descartados: se confirma igual, para rescatar los que sí son requisitos
    orb.poke(propuestos.length ? 1.2 : 0.4);
    setPiezas(propuestos.map((p, i) => ({ ...p, clave: `${Date.now()}-${i}` })));
    setFase("confirmar");
  };

  /* Pasos en vivo (NDJSON) → la lista bajo la esfera, la barra y el texto de la esfera */
  const seguir = (tipoTanda) => {
    const pasos = [];
    const poner = (p) => {
      const i = pasos.findIndex((x) => x.id === p.id);
      if (i === -1) pasos.push(p); else pasos[i] = { ...pasos[i], ...p };
    };
    return (e) => {
      if (e.tipo === "paso") {
        const texto = e.texto ?? { limpieza: "Limpiando el texto", patrones: "Buscando verbos como «debe»", ficha: "Ficha del contexto" }[e.id] ?? e.id;
        poner({ id: e.id, texto, estado: e.estado, detalle: e.detalle });
        setProgreso((g) => ({ ...g, pasos: [...pasos] }));
      } else if (e.tipo === "tanda") {
        const total = e.parrafos ?? e.requisitos;
        const texto = tipoTanda === "lectura"
          ? `El Revisor lee los párrafos ${e.desde}–${e.hasta} de ${total}`
          : `El Revisor compara los requisitos ${e.desde}–${e.hasta} de ${total} con el contexto`;
        const detalle = e.estado === "curso" ? (e.total > 1 ? `parte ${e.i} de ${e.total}` : "pensando…")
          : e.cuenta ? `${e.cuenta.claro} claros · ${e.cuenta.ambiguo} ambiguos · ${e.cuenta.incompleto} por precisar`
            : e.estado === "aviso" ? "no respondió" : `${e.encontrados} requisitos encontrados`;
        poner({ id: `tanda-${e.i}`, texto, estado: e.estado, detalle });
        setProgreso((g) => ({ ...g, pasos: [...pasos], barra: (e.i - (e.estado === "curso" ? 1 : 0)) / e.total,
          sub: e.total > 1 ? `parte ${e.i} de ${e.total}` : null }));
      }
    };
  };

  const detectar = async (contenido) => {
    setError(null);
    setDocumento(null);
    setProgreso({ ...PROGRESO_VACIO, inicio: Date.now() });
    setFase("leyendo");
    const t = abrirTurno("pegar");
    try {
      let r = null;
      const avanzar = seguir("lectura");
      await Promise.all([separarRequisitosFlujo(contenido, proyectoId, (e) => {
        if (!vigente(t)) return;
        if (e.tipo === "resultado") r = e.separacion;
        else if (e.tipo === "error") throw new Error(e.mensaje);
        else avanzar(e);
      }, t.control.signal), new Promise((ok) => setTimeout(ok, MIN_LECTURA_MS))]);
      if (!vigente(t)) return;
      if (!r) throw new Error("El servidor cerró la conexión antes de terminar.");
      mostrar(r, "pegar");
    } catch (e) {
      if (!vigente(t)) return;
      orb.setMood("error", { revertAfter: 1600 });
      setError(e.message);
      setFase("pegar");
    }
  };

  const leerArchivo = async (f) => {
    setOrigen(f.name);
    setError(null);
    setProgreso({ ...PROGRESO_VACIO, inicio: Date.now(),
      pasos: [{ id: "archivo", texto: `Leyendo ${f.name}`, estado: "curso", detalle: "extrae el texto y el Revisor reconoce cada requisito" }] });
    setFase("leyendo");
    const t = abrirTurno("inicio");
    try {
      const [doc] = await Promise.all([subirDocumento(proyectoId, f), new Promise((ok) => setTimeout(ok, MIN_LECTURA_MS))]);
      if (!vigente(t)) return;
      setDocumento({ documento_id: doc.documento_id, proyecto_id: doc.proyecto_id, archivo: doc.archivo, paginas: doc.paginas });
      mostrar(doc, "inicio");
    } catch (e) {
      if (!vigente(t)) return;
      orb.setMood("error", { revertAfter: 1600 });
      setError(e.message);
      setFase("inicio");
    }
  };
  leerVigente.current = leerArchivo;

  const editar = (i, v) => setPiezas((ps) => ps.map((p, j) => (j === i ? { ...p, texto: v } : p)));
  const quitar = (i) => { setPiezas((ps) => ps.filter((_, j) => j !== i)); orb.poke(-0.4); };
  const unir = (i) => setPiezas((ps) => [...ps.slice(0, i), { ...ps[i], texto: `${ps[i].texto} ${ps[i + 1].texto}` }, ...ps.slice(i + 2)]);
  const validas = piezas.map((p, i) => ({ ...p, n: i + 1 })).filter((p) => p.texto.trim());
  // límites del backend: se avisa antes de enviar en lugar de recibir un 422
  const largo = (p) => p.texto.trim().length > LIMITES_CARGA.caracteres;
  const largos = validas.filter(largo);
  const sobran = Math.max(0, validas.length - LIMITES_CARGA.requisitos);
  const destino = proyectoId;

  const analizar = async (apartar = false) => {
    setSaliendo(true);
    setError(null);
    orb.poke(1.4);
    const enviar = apartar ? validas.filter((p) => !porPrecisar(p)) : validas;
    try {
      const requisitos = enviar.map((p) => ({
        texto: p.texto.trim(),
        triaje: p.triaje ? {
          veredicto: p.triaje.veredicto, motivo: p.triaje.motivo, faltantes: p.triaje.faltantes, preguntas: p.triaje.preguntas,
          terminos_ambiguos: p.triaje.terminos_ambiguos, precisado: p.texto.trim() !== p.textoInicial, forzado: Boolean(p.forzado),
        } : null,
        origen: {
          documento_id: documento?.documento_id ?? null,
          archivo: documento?.archivo ?? "texto pegado",
          pagina: p.pagina ?? null,
          indice: p.indice ?? null,
          marca: p.marca ?? null,
          texto_original: p.texto_original ?? null,
        },
      }));
      const { req_ids: ids } = await cargarRequisitos(destino, requisitos);
      if (apartar) guardarApartados(destino, [...apartados, ...validas.filter(porPrecisar).map((p) => p.texto.trim())]);
      navigate(`/analisis?proyecto=${destino}&ids=${ids.join(",")}`);
    } catch (e) {
      setSaliendo(false);
      orb.setMood("error", { revertAfter: 1600 });
      setError(explicar(e, enviar));
    }
  };

  /* El Revisor compara cada requisito con la ficha del contexto (POST /proyectos/{id}/triaje) */
  const revisar = async () => {
    setError(null);
    setProgreso({ ...PROGRESO_VACIO, inicio: Date.now() });
    setFase("revisando");
    const t = abrirTurno("confirmar");
    try {
      let r = null;
      const avanzar = seguir("revision");
      await Promise.all([triarRequisitosFlujo(proyectoId, validas.map((p) => p.texto.trim()), (e) => {
        if (!vigente(t)) return;
        if (e.tipo === "resultado") r = e.triaje;
        else if (e.tipo === "error") throw new Error(e.mensaje);
        else avanzar(e);
      }, t.control.signal), new Promise((ok) => setTimeout(ok, MIN_LECTURA_MS))]);
      if (!vigente(t)) return;
      if (!r) throw new Error("El servidor cerró la conexión antes de terminar.");
      setPiezas(validas.map((p, i) => ({ ...p, triaje: r.resultados[i], revisado: p.texto.trim(), textoInicial: p.texto.trim(), forzado: false })));
      setAvisoTriaje(r.aviso);
      orb.setMood("success");
      orb.poke(1);
      setFase("triaje");
    } catch (e) {
      if (!vigente(t)) return;
      orb.setMood("error", { revertAfter: 1600 });
      setError(`No se pudo revisar con el contexto: ${e.message}`);
      setFase("confirmar");
    }
  };

  const revisarUna = async (i) => {
    const p = piezas[i];
    setPiezas((ps) => ps.map((x, j) => (j === i ? { ...x, revisando: true } : x)));
    try {
      const r = await triarRequisitos(proyectoId, [p.texto.trim()]);
      setPiezas((ps) => ps.map((x, j) => (j === i ? { ...x, triaje: r.resultados[0], revisado: x.texto.trim(), revisando: false, forzado: false } : x)));
    } catch (e) {
      setPiezas((ps) => ps.map((x, j) => (j === i ? { ...x, revisando: false } : x)));
      setError(e.message);
    }
  };
  const forzar = (i) => setPiezas((ps) => ps.map((x, j) => (j === i ? { ...x, forzado: true, revisado: x.texto.trim() } : x)));

  return (
    <main className="relative z-10 min-h-screen">
      <input ref={archivo} type="file" accept=".txt,.pdf" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) leerArchivo(f); }} />

      {(fase === "inicio" || fase === "pegar" || fase === "contexto") && (
        <div className="fixed top-20 left-5 z-20 md:top-24 md:left-10">
          <Volver a={`/proyectos/${proyectoId}/v1`}>{proyecto?.nombre ?? "Proyecto"}</Volver>
        </div>
      )}

      {fase === "inicio" && (
        <section key="inicio" className="aparece fixed inset-x-0 bottom-[7vh] flex flex-col items-center gap-6 px-6 text-center">
          <h1 className="serif text-[clamp(44px,5.6vw,84px)] leading-[.95]">
            ¿Qué <em>analizamos</em> hoy?
          </h1>
          <p className="max-w-md text-[15px] leading-relaxed text-[var(--bone-dim)]">
            {arrastrando ? "Suéltalo sobre la esfera." : "Suelta tu documento sobre la esfera, o pega el texto."}
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <button className="pill" onClick={() => archivo.current.click()} onPointerEnter={() => orb.poke(0.25)}>Sube tu archivo</button>
            <button className="pill ghost" onClick={() => setFase("pegar")} onPointerEnter={() => orb.poke(0.25)}>Pegar texto</button>
          </div>
          {apartados.length > 0 && (
            <p className="text-[13px] text-[var(--bone-dim)]">
              Tienes {apartados.length} {apartados.length === 1 ? "requisito apartado" : "requisitos apartados"} por precisar ·{" "}
              <button className="underline hover:text-[var(--bone)]" onClick={() => {
                setTexto(apartados.map((t, i) => `${i + 1}. ${t}`).join("\n"));
                guardarApartados(proyectoId, []);
                setApartados([]);
                setFase("pegar");
              }}>retomarlos</button>
            </p>
          )}
          <LineaContexto proyecto={proyecto} onEditar={() => setFase("contexto")} />
          {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
        </section>
      )}

      {fase === "contexto" && proyecto && (
        <EditarContexto proyecto={proyecto} onListo={(nuevo) => { if (nuevo) setProyecto(nuevo); setFase("inicio"); }} />
      )}

      {fase === "pegar" && (
        <section key="pegar" className="aparece mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-5 px-6 pt-[40vh] pb-12 md:mr-[8vw] md:pt-24">
          <h1 className="serif text-[clamp(40px,4vw,64px)] leading-[.95]">Pega tus <em>requisitos</em>.</h1>
          <p className="text-[14px] text-[var(--bone-dim)]">Uno por renglón o numerados; el sistema los separa.</p>
          <textarea
            autoFocus
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onFocus={() => orb.setMood("listening")}
            onBlur={() => orb.setMood("idle")}
            onInput={() => orb.poke(0.05)}
            rows={10}
            placeholder={"1. El sistema debe…\n2. El usuario podrá…"}
            className="linea w-full resize-none rounded-none border-b bg-transparent py-3 text-[15px] leading-relaxed"
          />
          {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
          <div className="flex flex-wrap items-center gap-3">
            <button className="pill" disabled={!texto.trim()} onClick={() => { setOrigen("texto pegado"); detectar(texto); }}>Separar requisitos</button>
            <button className="pill ghost" onClick={() => setFase("inicio")}>Volver</button>
          </div>
        </section>
      )}

      {trabajando && (
        <Progreso key={fase} progreso={progreso} onCancelar={cancelarProceso}
          titulo={fase === "leyendo" ? "El Revisor lee el texto y reconoce cada requisito" : "El Revisor compara cada requisito con la ficha del contexto"} />
      )}

      {fase === "triaje" && (
        <Triaje piezas={piezas} proyecto={proyecto} aviso={avisoTriaje} error={error} saliendo={saliendo}
          onEditar={editar} onQuitar={quitar} onRevisar={revisarUna} onForzar={forzar} onAnalizar={analizar}
          onVolver={() => { setError(null); setFase("confirmar"); }} />
      )}

      {fase === "confirmar" && (
        <section key="confirmar" className={`aparece mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-5 px-6 pt-[34vh] pb-12 md:mr-[6vw] md:pt-28 ${saliendo ? "sale" : ""}`}>
          <p className="mono text-[10px] text-[var(--bone-faint)]">
            {proyecto?.nombre ?? proyectoId} · {origen}{documento ? ` · ${documento.paginas} pág.` : ""}
            {metodo && <> · {metodo.metodo === "ia" ? `separados por el Revisor${metodo.modelo ? ` (${metodo.modelo})` : ""}` : "separados por patrones"}</>}
          </p>
          <h1 className="serif text-[clamp(40px,4vw,64px)] leading-[.95]">
            Encontré <em>{validas.length}</em> {validas.length === 1 ? "requisito" : "requisitos"}.
          </h1>
          <p className="text-[14.5px] text-[var(--bone-dim)]">
            {piezas.length
              ? "Revisa la separación: corrige, une o quita. Después los comparo con el contexto del proyecto."
              : metodo?.metodo === "ia"
                ? "No reconocí requisitos. Rescata los que sí lo sean con «+ usar»."
                : "No encontré oraciones con «debe», «podrá» o «permitirá». Rescata los que sí sean requisitos con «+ usar»."}
          </p>
          {advertencias.length > 0 && (
            <ul className="text-[12px] text-amber-200/80">
              {advertencias.map((a) => <li key={a}>⚠ {a}</li>)}
            </ul>
          )}
          <ol className="space-y-1">
            {piezas.map((p, i) => (
              <li key={p.clave} className="group flex items-start gap-4 border-b border-[var(--line)] py-2">
                <span className="mono flex w-16 shrink-0 flex-col pt-2.5 text-[10px] text-[var(--bone-faint)]">
                  {String(i + 1).padStart(2, "0")}
                  {p.marca && <span className="text-[var(--bone-dim)] normal-case tracking-normal">{p.marca}</span>}
                  {p.pagina && <span>p. {p.pagina}</span>}
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                <textarea
                  value={p.texto}
                  rows={Math.max(1, Math.ceil(p.texto.length / 70))}
                  onChange={(e) => editar(i, e.target.value)}
                  onFocus={() => orb.setMood("listening")}
                  onBlur={() => orb.setMood("idle")}
                  className="min-w-0 flex-1 resize-none bg-transparent py-1.5 [field-sizing:content] text-[15px] leading-relaxed text-[var(--bone)] outline-none"
                />
                {p.advertencias?.length > 0 && (
                  <span className="text-[11.5px] text-amber-200/70">{p.advertencias.join(" · ")}</span>
                )}
                {largo(p) && (
                  <span className="text-[11.5px] text-[var(--danger)]">
                    Tiene {p.texto.trim().length} caracteres; el backend acepta hasta {LIMITES_CARGA.caracteres} por requisito. Pártelo («+ agregar requisito») o recórtalo.
                  </span>
                )}
                </span>
                <span className="flex gap-3 pt-2.5 opacity-40 transition-opacity group-hover:opacity-100">
                  {i < piezas.length - 1 && (
                    <button title="Unir con el siguiente" className="mono text-[10px] hover:text-[var(--c1)]" onClick={() => unir(i)}>unir ↓</button>
                  )}
                  <button title="Quitar" className="mono text-[10px] hover:text-[var(--danger)]" onClick={() => quitar(i)}>quitar</button>
                </span>
              </li>
            ))}
          </ol>
          <button
            className="mono self-start text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]"
            onClick={() => setPiezas((ps) => [...ps, { texto: "", clave: `n-${Date.now()}` }])}
          >
            + agregar requisito
          </button>
          {descartados.total > 0 && (
            <details open={!piezas.length} className="text-[12.5px] text-[var(--bone-dim)]">
              <summary className="mono cursor-pointer text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]">
                {descartados.total} fragmento{descartados.total === 1 ? "" : "s"} descartado{descartados.total === 1 ? "" : "s"} · ver
              </summary>
              <ul className="mt-2 space-y-1 border-l border-[var(--line)] pl-3">
                {descartados.lista.map((d, i) => (
                  <li key={i}>
                    <span className="mono mr-2 text-[9.5px] text-[var(--bone-faint)]">{d.pagina ? `p. ${d.pagina}` : ""} {d.detalle ?? MOTIVOS[d.motivo] ?? d.motivo}</span>
                    {d.texto}
                    <button className="mono ml-2 text-[9.5px] text-[var(--c1)]"
                      onClick={() => setPiezas((ps) => [...ps, { texto: d.texto, pagina: d.pagina, marca: d.marca, clave: `d-${Date.now()}-${i}` }])}>
                      + usar
                    </button>
                  </li>
                ))}
                {descartados.total > descartados.lista.length && <li className="text-[var(--bone-faint)]">… y {descartados.total - descartados.lista.length} más</li>}
              </ul>
            </details>
          )}
          {/* Fija abajo: con muchos requisitos el botón no se pierde */}
          <div className="sticky bottom-4 z-10 -mx-3 flex flex-wrap items-center gap-3 rounded-[28px] px-3 py-2 bg-[color-mix(in_oklab,var(--bg)_90%,transparent)]">
            {(error || sobran > 0 || largos.length > 0) && (
              <div className="basis-full space-y-1 px-2 text-sm text-[var(--danger)]">
                {sobran > 0 && <p>El backend acepta hasta {LIMITES_CARGA.requisitos} requisitos por carga (cada carga abre un ciclo): quita {sobran} o reparte el documento en varias cargas.</p>}
                {largos.length > 0 && <p>{largos.length === 1 ? "El requisito" : "Los requisitos"} {largos.map((p) => p.n).join(", ")} {largos.length === 1 ? "pasa" : "pasan"} de {LIMITES_CARGA.caracteres} caracteres.</p>}
                {error && <p>{error}</p>}
              </div>
            )}
            <button className="pill" disabled={!validas.length || saliendo || !destino || sobran > 0 || largos.length > 0} onClick={revisar} onPointerEnter={() => orb.poke(0.3)}>
              Revisar {validas.length} con el contexto
            </button>
            <button className="pill ghost" onClick={() => { setPiezas([]); setError(null); setFase("inicio"); }}>Empezar de nuevo</button>
            <Link className="mono px-2 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" to={`/proyectos/${proyectoId}/v1`}>cancelar</Link>
          </div>
        </section>
      )}
    </main>
  );
}

/* El contexto general, en una línea: los agentes lo leen con cada requisito */
function LineaContexto({ proyecto, onEditar }) {
  if (!proyecto || proyecto.tipo === "evaluacion") return null;
  return (
    <p className="max-w-lg text-[13px] text-[var(--bone-faint)]">
      {proyecto.contexto
        ? <>Contexto: <span className="text-[var(--bone-dim)]">{proyecto.contexto.length > 90 ? `${proyecto.contexto.slice(0, 89)}…` : proyecto.contexto}</span></>
        : "Sin contexto general: los agentes leerán cada requisito por sí solo."}
      {" "}<button className="enlace" onClick={onEditar}>{proyecto.contexto ? "editar" : "agregar contexto"}</button>
    </p>
  );
}

function EditarContexto({ proyecto, onListo }) {
  const orb = useOrb();
  const [contexto, setContexto] = useState(proyecto.contexto ?? "");
  const [error, setError] = useState(null);
  const guardar = async (e) => {
    e.preventDefault();
    try {
      const nuevo = await editarProyecto(proyecto.proyecto_id, { contexto });
      orb.setMood("success", { revertAfter: 900 });
      onListo(nuevo);
    } catch (err) {
      setError(err.message);
    }
  };
  return (
    <section className="aparece mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-5 px-6 pt-[40vh] pb-12 md:ml-[8vw] md:pt-24">
      <h1 className="serif text-[clamp(36px,3.6vw,56px)] leading-[.95]">El <em>contexto</em> del proyecto.</h1>
      <p className="text-[14.5px] leading-relaxed text-[var(--bone-dim)]">
        De qué trata el sistema, quién lo usa y cómo hablan en ese trabajo. Con esto, «ahorita» o «checar» se entienden dentro de tu dominio.
      </p>
      <form onSubmit={guardar} className="space-y-4">
        <textarea autoFocus value={contexto} maxLength={CONTEXTO_MAX} rows={7} onChange={(e) => setContexto(e.target.value)}
          className="campo text-[15px]" placeholder="Ej.: Sistema de caja para una ferretería de Ciudad Juárez; lo usan cajeros y el encargado; «checar» es revisar existencias." />
        {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
        <div className="flex gap-3">
          <button className="pill">Guardar</button>
          <button type="button" className="pill ghost" onClick={() => onListo(null)}>Volver</button>
        </div>
      </form>
    </section>
  );
}

/*
 * Los requisitos separados por el Revisor (ADR 0022). Los poco detallados se precisan
 * (se reescriben y se vuelven a revisar), se mandan así a propósito o se quitan: sin
 * eso no se puede analizar. Los ambiguos van al análisis y se detienen para que una
 * persona los revise. Un requisito editado después de revisarlo se vuelve a revisar.
 */
const GRUPOS_TRIAJE = [
  { id: "incompleto", titulo: "Hay que precisarlos", nota: "No se entienden con el contexto sin inventar información. Reescríbelos con lo que falta.", tono: "var(--danger)" },
  { id: "ambiguo", titulo: "Ambiguos", nota: "Se entiende qué piden, pero algo admite más de una interpretación. Se analizan y te los pregunto antes de formalizarlos.", tono: "var(--aviso)" },
  { id: "sin", titulo: "Sin revisar", nota: "El Revisor no respondió: se analizan como vienen.", tono: "var(--bone-faint)" },
  { id: "claro", titulo: "Se entienden con el contexto", nota: "Van directo al análisis.", tono: "var(--ok)" },
];

function grupoDe(p) {
  if (p.forzado) return "ambiguo";
  return p.triaje?.veredicto ?? "sin";
}

// sin precisar o editado sin volver a revisar: no se puede analizar todavía
function porPrecisar(p) {
  return Boolean(p.texto.trim()) && (p.texto.trim() !== p.revisado || grupoDe(p) === "incompleto");
}

function Triaje({ piezas, proyecto, aviso, error, saliendo, onEditar, onQuitar, onRevisar, onForzar, onAnalizar, onVolver }) {
  const editado = (p) => p.texto.trim() !== p.revisado;
  const pendientes = piezas.filter(porPrecisar).length;
  const total = piezas.filter((p) => p.texto.trim()).length;
  const cuenta = (g) => piezas.filter((p) => grupoDe(p) === g).length;

  return (
    <section key="triaje" className={`aparece mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6 pt-[34vh] pb-12 md:mr-[6vw] md:pt-28 ${saliendo ? "sale" : ""}`}>
      <p className="mono text-[10px] text-[var(--bone-faint)]">{proyecto?.nombre} · revisados con el contexto</p>
      <h1 className="serif text-[clamp(36px,3.6vw,56px)] leading-[.95]">
        {cuenta("incompleto") ? <>Hay <em>{cuenta("incompleto")}</em> por precisar.</> : <>Listos para <em>analizar</em>.</>}
      </h1>
      <p className="text-[14.5px] text-[var(--bone-dim)]">
        {cuenta("claro")} se entienden · {cuenta("ambiguo")} ambiguos · {cuenta("incompleto")} poco detallados
        {!proyecto?.contexto && <> · <span className="text-[var(--aviso)]">el proyecto no tiene contexto: los revisé solo por sí mismos</span></>}
      </p>
      {aviso && <p className="text-[13px] text-[var(--aviso)]">{aviso}</p>}

      {GRUPOS_TRIAJE.map((g) => {
        const del = piezas.map((p, i) => ({ p, i })).filter(({ p }) => grupoDe(p) === g.id);
        if (!del.length) return null;
        return (
          <section key={g.id} className="space-y-2">
            <h2 className="flex items-center gap-2"><span className="punto" style={{ background: g.tono }} />{g.titulo} <span className="text-[var(--bone-faint)]">({del.length})</span></h2>
            <p className="text-[13px] text-[var(--bone-faint)]">{g.nota}</p>
            <ol className="space-y-2">
              {del.map(({ p, i }) => (
                <PiezaRevisada key={p.clave ?? i} p={p} compacta={g.id === "claro" && !editado(p)} editado={editado(p)}
                  onEditar={(v) => onEditar(i, v)} onQuitar={() => onQuitar(i)} onRevisar={() => onRevisar(i)} onForzar={() => onForzar(i)} />
              ))}
            </ol>
          </section>
        );
      })}

      <div className="sticky bottom-4 z-10 -mx-3 flex flex-wrap items-center gap-3 rounded-[28px] bg-[color-mix(in_oklab,var(--bg)_90%,transparent)] px-3 py-2">
        {error && <p className="basis-full px-2 text-sm text-[var(--danger)]">{error}</p>}
        <button className="pill" disabled={!total || pendientes > 0 || saliendo} onClick={() => onAnalizar(false)}>
          {pendientes ? `Faltan ${pendientes} por precisar o revisar` : `Analizar ${total} ${total === 1 ? "requisito" : "requisitos"}`}
        </button>
        {pendientes > 0 && pendientes < total && (
          <button className="pill" disabled={saliendo} onClick={() => onAnalizar(true)}
            title="Los que faltan por precisar quedan guardados; los retomas al volver a Analizar">
            Apartar {pendientes} y analizar {total - pendientes}
          </button>
        )}
        <button className="pill ghost" onClick={onVolver}>Volver a la separación</button>
      </div>
    </section>
  );
}

function PiezaRevisada({ p, compacta, editado, onEditar, onQuitar, onRevisar, onForzar }) {
  const t = p.triaje;
  const incompleto = grupoDe(p) === "incompleto";
  return (
    <li className={`group rounded-2xl border border-[var(--line)] px-4 py-3 ${incompleto ? "bg-[color-mix(in_oklab,var(--danger)_5%,transparent)]" : ""}`}>
      <div className="flex items-start gap-3">
        <span className="mono w-6 shrink-0 pt-2 text-[10px] text-[var(--bone-faint)]">{String(p.n).padStart(2, "0")}</span>
        <textarea value={p.texto} rows={Math.max(1, Math.ceil(p.texto.length / 70))} onChange={(e) => onEditar(e.target.value)}
          className="min-w-0 flex-1 resize-none bg-transparent py-1.5 [field-sizing:content] text-[15px] leading-relaxed text-[var(--bone)] outline-none" />
      </div>
      {!compacta && t && (
        <div className="ml-9 space-y-1.5 pb-1 text-[13px]">
          {t.motivo && <p className="text-[var(--bone-dim)]">{t.motivo}</p>}
          {t.terminos_ambiguos?.length > 0 && (
            <p className="flex flex-wrap gap-1.5">{t.terminos_ambiguos.map((x) => <span key={x} className="rounded-full border border-[var(--line)] px-2 text-[12px] text-[var(--aviso)]">«{x}»</span>)}</p>
          )}
          {t.faltantes?.length > 0 && <p className="text-[var(--bone-faint)]">Falta: {t.faltantes.join(", ")}</p>}
          {t.preguntas?.length > 0 && (
            <ul className="list-disc space-y-0.5 pl-5 text-[var(--bone-dim)]">{t.preguntas.map((q) => <li key={q}>{q}</li>)}</ul>
          )}
          {p.forzado && <p className="text-[var(--aviso)]">Lo mandas así: te lo preguntaré antes de formalizarlo.</p>}
        </div>
      )}
      <div className="mono ml-9 flex flex-wrap gap-x-4 gap-y-1 pt-1 text-[10px] text-[var(--bone-faint)]">
        {editado && <span className="text-[var(--aviso)]">cambió: vuelve a revisarlo</span>}
        {(incompleto || editado) && (
          <button className="hover:text-[var(--bone)] disabled:opacity-40" disabled={p.revisando || !p.texto.trim()} onClick={onRevisar}>
            {p.revisando ? "revisando…" : "volver a revisar"}
          </button>
        )}
        {incompleto && !editado && <button className="hover:text-[var(--bone)]" onClick={onForzar} title="Se analiza y se detiene para que lo revises">analizar así</button>}
        <button className="hover:text-[var(--danger)]" onClick={onQuitar}>quitar</button>
      </div>
    </li>
  );
}

/* Lo que está haciendo el Revisor: título, pasos en vivo, barra y tiempo transcurrido */
function Progreso({ progreso, titulo, onCancelar }) {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setAhora(Date.now()), 500);
    return () => clearInterval(t);
  }, []);
  const segundos = progreso.inicio ? Math.max(0, Math.round((ahora - progreso.inicio) / 1000)) : 0;
  const pasos = progreso.pasos.length ? progreso.pasos : [{ id: "servidor", texto: "Conectando con el servidor", estado: "curso" }];
  return (
    <section className="aparece fixed inset-x-0 bottom-[7vh] z-10 px-6" aria-live="polite">
      <div className="mx-auto max-w-lg space-y-4">
        <p className="mono flex items-center justify-between gap-3 text-[10px] text-[var(--bone-dim)]">
          <span>{titulo}</span><span className="tabular-nums text-[var(--bone-faint)]">{segundos} s</span>
        </p>
        <div className="h-[3px] overflow-hidden rounded-full bg-[var(--line)]">
          {progreso.barra == null
            ? <div className="barra-indeterminada h-full w-1/3 rounded-full bg-[var(--c1)]" />
            : <div className="h-full rounded-full bg-[var(--c1)] transition-[width] duration-700" style={{ width: `${Math.max(4, progreso.barra * 100)}%` }} />}
        </div>
        <Pasos pasos={pasos} />
        <button className="pill ghost sm" onClick={onCancelar}>Cancelar</button>
      </div>
    </section>
  );
}
