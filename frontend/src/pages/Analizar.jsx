import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useOrb, usePoseEsfera } from "../components/orb/useOrb";
import {
  CONTEXTO_MAX, LIMITES_CARGA, cargarRequisitos, editarProyecto, obtenerProyecto, separarRequisitos, subirDocumento,
} from "../services/backend";
import { documentoEjemplo } from "../fixtures/documentoEjemplo";
import { recordarProyecto } from "../components/proyectoRecordado";
import { Volver } from "../components/ui";

/*
 * Analizar requisitos dentro de un proyecto. La esfera recibe el archivo:
 *   inicio    → la esfera al centro: «suelta tu archivo»
 *   contexto  → la esfera a un lado; se escribe el contexto general del proyecto
 *   pegar     → la esfera se hace a un lado; aparece el texto
 *   leyendo   → la esfera "lee" (piensa) en el centro
 *   confirmar → la esfera a la izquierda; a la derecha, los requisitos detectados
 *
 * El backend lee el PDF (texto extraíble; sin OCR por alcance) y lo separa en
 * requisitos candidatos con su página y numeración original. Lo que descarta
 * se muestra y lo que la limpieza quitó también: nada se pierde en silencio.
 * La persona confirma la separación; desde ahí todo sigue solo y solo se le
 * pregunta si los agentes no llegan a un acuerdo (ADR 0017).
 */
const POSES = {
  inicio: { d: { x: 0, y: -0.08, s: 1.05 }, m: { x: 0, y: -0.16, s: 0.8 } },
  arrastre: { d: { x: 0, y: -0.08, s: 1.3 }, m: { x: 0, y: -0.16, s: 0.95 } },
  contexto: { d: { x: 0.3, y: 0.02, s: 0.85 }, m: { x: 0, y: -0.33, s: 0.45 } },
  pegar: { d: { x: -0.26, y: 0, s: 0.85 }, m: { x: 0, y: -0.33, s: 0.45 } },
  leyendo: { d: { x: 0, y: -0.04, s: 0.9 }, m: { x: 0, y: -0.1, s: 0.7 } },
  confirmar: { d: { x: -0.29, y: 0.02, s: 0.78 }, m: { x: 0, y: -0.36, s: 0.4 } },
};
const MIN_LECTURA_MS = 1400;

/* Un 422 del backend señala el requisito por su posición (base 0) en lo enviado; aquí se numeran desde 1 */
function explicar(e, enviadas) {
  if (!Array.isArray(e.detalle)) return e.message;
  return e.detalle.map((x) => {
    const [, campo, i] = x.loc ?? [];
    if (campo === "requisitos" && Number.isInteger(i)) return `Requisito ${enviadas[i]?.n ?? i + 1}: ${x.msg}`;
    return `${(x.loc ?? []).slice(1).join(".")}: ${x.msg}`;
  }).join(" · ");
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
  const archivo = useRef(null);

  usePoseEsfera(POSES[arrastrando ? "arrastre" : fase], [fase, arrastrando]);

  useEffect(() => {
    recordarProyecto(proyectoId);
    obtenerProyecto(proyectoId).then(setProyecto).catch((e) => setError(e.message));
  }, [proyectoId]);

  useEffect(() => {
    orb.setMood(fase === "leyendo" ? "thinking" : arrastrando || fase === "contexto" ? "listening" : "idle");
    orb.update("core", {
      label: fase === "leyendo" ? "Leyendo" : fase === "confirmar" ? `${piezas.length} requisitos` : null,
      sub: fase === "leyendo" ? origen : null,
    });
  }, [orb, fase, arrastrando, origen, piezas.length]);
  useEffect(() => () => orb.update("core", { label: null, sub: null }), [orb]);

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
    if (!propuestos.length && !r.total_descartados) {
      orb.setMood("error", { revertAfter: 1600 });
      setError("No encontré requisitos. Cada uno debería decir qué «debe», «podrá» o «permitirá» hacer el sistema.");
      setFase(volverA);
      return;
    }
    // sin propuestos pero con descartados: se confirma igual, para rescatar los que sí son requisitos
    orb.poke(propuestos.length ? 1.2 : 0.4);
    setPiezas(propuestos.map((p, i) => ({ ...p, clave: `${Date.now()}-${i}` })));
    setFase("confirmar");
  };

  const detectar = async (contenido) => {
    setError(null);
    setDocumento(null);
    setFase("leyendo");
    try {
      const [r] = await Promise.all([separarRequisitos(contenido), new Promise((ok) => setTimeout(ok, MIN_LECTURA_MS))]);
      mostrar(r, "pegar");
    } catch (e) {
      orb.setMood("error", { revertAfter: 1600 });
      setError(e.message);
      setFase("pegar");
    }
  };

  const leerArchivo = async (f) => {
    setOrigen(f.name);
    setError(null);
    setFase("leyendo");
    try {
      const [doc] = await Promise.all([subirDocumento(proyectoId, f), new Promise((ok) => setTimeout(ok, MIN_LECTURA_MS))]);
      setDocumento({ documento_id: doc.documento_id, proyecto_id: doc.proyecto_id, archivo: doc.archivo, paginas: doc.paginas });
      mostrar(doc, "inicio");
    } catch (e) {
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

  const analizar = async () => {
    setSaliendo(true);
    setError(null);
    orb.poke(1.4);
    try {
      const requisitos = validas.map((p) => ({
        texto: p.texto.trim(),
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
      navigate(`/analisis?proyecto=${destino}&ids=${ids.join(",")}`);
    } catch (e) {
      setSaliendo(false);
      orb.setMood("error", { revertAfter: 1600 });
      setError(explicar(e, validas));
    }
  };

  return (
    <main className="relative z-10 min-h-screen">
      <input ref={archivo} type="file" accept=".txt,.pdf" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) leerArchivo(f); }} />

      {(fase === "inicio" || fase === "pegar" || fase === "contexto") && (
        <div className="fixed top-20 left-5 z-20 md:top-24 md:left-10">
          <Volver a={`/proyectos/${proyectoId}`}>{proyecto?.nombre ?? "Proyecto"}</Volver>
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
            <button className="mono text-[10px] text-[var(--bone-faint)] underline underline-offset-4 hover:text-[var(--bone)]" onClick={() => setTexto(documentoEjemplo)}>
              Usar ejemplo
            </button>
          </div>
        </section>
      )}

      {fase === "leyendo" && (
        <p key="leyendo" className="mono aparece fixed inset-x-0 bottom-[16vh] text-center text-[10px] text-[var(--bone-dim)]">
          Separando el documento en requisitos…
        </p>
      )}

      {fase === "confirmar" && (
        <section key="confirmar" className={`aparece mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-5 px-6 pt-[34vh] pb-12 md:mr-[6vw] md:pt-28 ${saliendo ? "sale" : ""}`}>
          <p className="mono text-[10px] text-[var(--bone-faint)]">
            {proyecto?.nombre ?? proyectoId} · {origen}{documento ? ` · ${documento.paginas} pág.` : ""}
          </p>
          <h1 className="serif text-[clamp(40px,4vw,64px)] leading-[.95]">
            Encontré <em>{validas.length}</em> {validas.length === 1 ? "requisito" : "requisitos"}.
          </h1>
          <p className="text-[14.5px] text-[var(--bone-dim)]">
            {piezas.length
              ? "Revisa la separación: corrige, une o quita. Después todo sigue solo."
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
                    <span className="mono mr-2 text-[9.5px] text-[var(--bone-faint)]">{d.pagina ? `p. ${d.pagina}` : ""} {d.motivo}</span>
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
          <div className="sticky bottom-4 z-10 -mx-3 flex flex-wrap items-center gap-3 rounded-[28px] px-3 py-2 backdrop-blur-xl">
            {(error || sobran > 0 || largos.length > 0) && (
              <div className="basis-full space-y-1 px-2 text-sm text-[var(--danger)]">
                {sobran > 0 && <p>El backend acepta hasta {LIMITES_CARGA.requisitos} requisitos por carga (cada carga abre un ciclo): quita {sobran} o reparte el documento en varias cargas.</p>}
                {largos.length > 0 && <p>{largos.length === 1 ? "El requisito" : "Los requisitos"} {largos.map((p) => p.n).join(", ")} {largos.length === 1 ? "pasa" : "pasan"} de {LIMITES_CARGA.caracteres} caracteres.</p>}
                {error && <p>{error}</p>}
              </div>
            )}
            <button className="pill" disabled={!validas.length || saliendo || !destino || sobran > 0 || largos.length > 0} onClick={analizar} onPointerEnter={() => orb.poke(0.3)}>
              Analizar {validas.length} {validas.length === 1 ? "requisito" : "requisitos"}
            </button>
            <button className="pill ghost" onClick={() => { setPiezas([]); setError(null); setFase("inicio"); }}>Empezar de nuevo</button>
            <Link className="mono px-2 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" to={`/proyectos/${proyectoId}`}>cancelar</Link>
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
