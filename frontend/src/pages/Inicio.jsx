import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { useOrb, usePoseEsfera } from "../components/orb/useOrb";
import { LIMITES_CARGA, cargarRequisitos, separarRequisitos, subirDocumento } from "../services/backend";
import { documentoEjemplo } from "../fixtures/documentoEjemplo";
import SelectorProyecto, { proyectoRecordado } from "../components/SelectorProyecto";

/*
 * Analizar, paso 1. La esfera recibe el archivo:
 *   inicio    → la esfera al centro: «suelta tu archivo»
 *   pegar     → la esfera se hace a un lado; aparece el texto
 *   leyendo   → la esfera "lee" (piensa) en el centro
 *   confirmar → la esfera a la izquierda; a la derecha, los requisitos detectados
 *
 * El backend lee el PDF (texto extraíble; sin OCR por alcance) y lo separa en
 * requisitos candidatos con su página y numeración original. Lo que descarta
 * se muestra (aunque no proponga ninguno) y lo que la limpieza quitó también:
 * nada se pierde en silencio. La persona confirma antes de analizar; un
 * documento subido ya quedó en su proyecto, así que ahí el proyecto no cambia.
 */
const POSES = {
  inicio: { d: { x: 0, y: -0.08, s: 1.05 }, m: { x: 0, y: -0.16, s: 0.8 } },
  arrastre: { d: { x: 0, y: -0.08, s: 1.3 }, m: { x: 0, y: -0.16, s: 0.95 } },
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

export default function Inicio() {
  const orb = useOrb();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [proyectoId, setProyectoId] = useState(() => params.get("proyecto") ?? proyectoRecordado());
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
    orb.setMood(fase === "leyendo" ? "thinking" : arrastrando ? "listening" : "idle");
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
    if (!proyectoId) { setError("Elige o crea un proyecto antes de subir el documento."); return; }
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
  // un documento ya quedó guardado en su proyecto: sus requisitos van ahí
  const destino = documento?.proyecto_id ?? proyectoId;

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

      {fase === "inicio" && (
        <section key="inicio" className="fixed inset-x-0 bottom-[7vh] flex flex-col items-center gap-6 px-6 text-center">
          <div className="sube" style={{ "--i": 0 }}><SelectorProyecto valor={proyectoId} onCambio={setProyectoId} /></div>
          <h1 className="serif sube text-[clamp(44px,5.6vw,84px)] leading-[.95]" style={{ "--i": 0 }}>
            ¿Qué <em>analizamos</em> hoy?
          </h1>
          <p className="sube max-w-md text-sm leading-relaxed text-[var(--bone-dim)]" style={{ "--i": 1 }}>
            {arrastrando ? "Suéltalo sobre la esfera." : "Suelta tu documento de requisitos sobre la esfera, o elige cómo dárselo."}
          </p>
          <div className="sube flex flex-wrap justify-center gap-3" style={{ "--i": 2 }}>
            <button className="pill" onClick={() => archivo.current.click()} onPointerEnter={() => orb.poke(0.25)}>Sube tu archivo</button>
            <button className="pill ghost" onClick={() => setFase("pegar")} onPointerEnter={() => orb.poke(0.25)}>Pegar texto</button>
          </div>
          <p className="mono sube text-[10px] text-[var(--bone-faint)]" style={{ "--i": 3 }}>.txt · .pdf</p>
          {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
        </section>
      )}

      {fase === "pegar" && (
        <section key="pegar" className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-5 px-6 pt-[40vh] pb-12 md:mr-[8vw] md:pt-24">
          <p className="mono sube text-[10px] text-[var(--bone-faint)]" style={{ "--i": 0 }}>Paso 1 · el texto</p>
          <h1 className="serif sube text-[clamp(40px,4vw,64px)] leading-[.95]" style={{ "--i": 1 }}>Pega tus <em>requisitos</em>.</h1>
          <textarea
            autoFocus
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onFocus={() => orb.setMood("listening")}
            onBlur={() => orb.setMood("idle")}
            onInput={() => orb.poke(0.05)}
            rows={10}
            placeholder={"1. El sistema debe…\n2. El usuario podrá…"}
            className="sube linea w-full resize-none rounded-none border-b bg-transparent py-3 text-[15px] leading-relaxed"
            style={{ "--i": 2 }}
          />
          {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
          <div className="sube flex flex-wrap items-center gap-3" style={{ "--i": 3 }}>
            <button className="pill" disabled={!texto.trim()} onClick={() => { setOrigen("texto pegado"); detectar(texto); }}>Detectar requisitos</button>
            <button className="pill ghost" onClick={() => setFase("inicio")}>Volver</button>
            <button className="mono text-[10px] text-[var(--bone-faint)] underline underline-offset-4 hover:text-[var(--bone)]" onClick={() => setTexto(documentoEjemplo)}>
              Usar ejemplo
            </button>
          </div>
        </section>
      )}

      {fase === "leyendo" && (
        <p key="leyendo" className="mono sube fixed inset-x-0 bottom-[16vh] text-center text-[10px] text-[var(--bone-dim)]">
          Separando el documento en requisitos…
        </p>
      )}

      {fase === "confirmar" && (
        <section key="confirmar" className={`mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-5 px-6 pt-[34vh] pb-12 md:mr-[6vw] md:pt-28 ${saliendo ? "sale" : ""}`}>
          <p className="mono sube text-[10px] text-[var(--bone-faint)]" style={{ "--i": 0 }}>
            Paso 2 · confirma la separación · {origen}{documento ? ` · ${documento.paginas} pág. · ${documento.documento_id}` : ""}
          </p>
          {documento ? (
            <p className="mono sube -mt-2 text-[10px] text-[var(--bone-faint)]" style={{ "--i": 0 }}>
              Proyecto <span className="text-[var(--bone)]">{documento.proyecto_id}</span> · el documento quedó guardado ahí; para cargarlo en otro proyecto, empieza de nuevo y elígelo antes de subirlo
            </p>
          ) : (
            <div className="sube -mt-2 [&>div]:justify-start" style={{ "--i": 0 }}><SelectorProyecto valor={proyectoId} onCambio={setProyectoId} /></div>
          )}
          <h1 className="serif sube text-[clamp(40px,4vw,64px)] leading-[.95]" style={{ "--i": 1 }}>
            Encontré <em>{validas.length}</em> {validas.length === 1 ? "requisito" : "requisitos"}.
          </h1>
          <p className="sube text-sm text-[var(--bone-dim)]" style={{ "--i": 2 }}>
            {piezas.length
              ? "Corrige el texto, une los que se partieron mal o quita los que sobran."
              : "Ninguna oración dice qué «debe», «podrá» o «permitirá» hacer el sistema. Revisa los fragmentos descartados: los que sí sean requisitos se rescatan con «+ usar»."}
          </p>
          {advertencias.length > 0 && (
            <ul className="sube text-[12px] text-amber-200/80" style={{ "--i": 2 }}>
              {advertencias.map((a) => <li key={a}>⚠ {a}</li>)}
            </ul>
          )}
          <ol className="space-y-1">
            {piezas.map((p, i) => (
              <li key={p.clave} className="sube group flex items-start gap-4 border-b border-[var(--line)] py-2" style={{ "--i": 3 + Math.min(i, 8) }}>
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
            className="mono sube self-start text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]"
            style={{ "--i": 4 + piezas.length }}
            onClick={() => setPiezas((ps) => [...ps, { texto: "", clave: `n-${Date.now()}` }])}
          >
            + agregar requisito
          </button>
          {descartados.total > 0 && (
            <details open={!piezas.length} className="sube text-[12.5px] text-[var(--bone-dim)]" style={{ "--i": 4 + piezas.length }}>
              <summary className="mono cursor-pointer text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]">
                {descartados.total} fragmento{descartados.total === 1 ? "" : "s"} no parece{descartados.total === 1 ? "" : "n"} requisito · ver
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
          <div className="sube sticky bottom-4 z-10 -mx-3 flex flex-wrap items-center gap-3 rounded-[28px] px-3 py-2 backdrop-blur-xl" style={{ "--i": 5 + Math.min(piezas.length, 8) }}>
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
          </div>
        </section>
      )}
    </main>
  );
}
