import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { useOrb, usePoseEsfera } from "../components/orb/useOrb";
import { crearRequisitos, extraerTextoDeArchivo, separarRequisitos } from "../services/api";
import { documentoEjemplo } from "../fixtures/documentoEjemplo";
import SelectorProyecto, { proyectoRecordado } from "../components/SelectorProyecto";

/*
 * Analizar, paso 1. La esfera recibe el archivo:
 *   inicio    → la esfera al centro: «suelta tu archivo»
 *   pegar     → la esfera se hace a un lado; aparece el texto
 *   leyendo   → la esfera "lee" (piensa) en el centro
 *   confirmar → la esfera a la izquierda; a la derecha, los requisitos detectados
 */
const POSES = {
  inicio: { d: { x: 0, y: -0.08, s: 1.05 }, m: { x: 0, y: -0.16, s: 0.8 } },
  arrastre: { d: { x: 0, y: -0.08, s: 1.3 }, m: { x: 0, y: -0.16, s: 0.95 } },
  pegar: { d: { x: -0.26, y: 0, s: 0.85 }, m: { x: 0, y: -0.33, s: 0.45 } },
  leyendo: { d: { x: 0, y: -0.04, s: 0.9 }, m: { x: 0, y: -0.1, s: 0.7 } },
  confirmar: { d: { x: -0.29, y: 0.02, s: 0.78 }, m: { x: 0, y: -0.36, s: 0.4 } },
};
const MIN_LECTURA_MS = 1400;

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
      if (f) leerArchivo(f);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fase]);

  const detectar = async (contenido, nombre) => {
    setError(null);
    setFase("leyendo");
    const [lista] = await Promise.all([separarRequisitos(contenido), new Promise((r) => setTimeout(r, MIN_LECTURA_MS))]);
    if (!lista.length) {
      orb.setMood("error", { revertAfter: 1600 });
      setError("No encontré requisitos en ese texto. Cada uno debería decir qué «debe» o «podrá» hacer el sistema.");
      setFase(nombre === "texto pegado" ? "pegar" : "inicio");
      return;
    }
    orb.poke(1.2);
    setPiezas(lista.map((p, i) => ({ ...p, clave: `${Date.now()}-${i}` })));
    setFase("confirmar");
  };

  const leerArchivo = async (f) => {
    setOrigen(f.name);
    setFase("leyendo");
    try {
      const contenido = await extraerTextoDeArchivo(f);
      setTexto(contenido);
      await detectar(contenido, f.name);
    } catch (e) {
      orb.setMood("error", { revertAfter: 1600 });
      setError(e.message);
      setFase("inicio");
    }
  };

  const editar = (i, v) => setPiezas((ps) => ps.map((p, j) => (j === i ? { ...p, texto: v } : p)));
  const quitar = (i) => { setPiezas((ps) => ps.filter((_, j) => j !== i)); orb.poke(-0.4); };
  const unir = (i) => setPiezas((ps) => [...ps.slice(0, i), { ...ps[i], texto: `${ps[i].texto} ${ps[i + 1].texto}` }, ...ps.slice(i + 2)]);
  const validas = piezas.filter((p) => p.texto.trim());

  const analizar = async () => {
    setSaliendo(true);
    orb.poke(1.4);
    const { ids } = await crearRequisitos(validas.map((p) => ({ texto: p.texto, origen })), proyectoId);
    navigate(`/analisis?ids=${ids.join(",")}`);
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
            <button className="pill" disabled={!texto.trim()} onClick={() => { setOrigen("texto pegado"); detectar(texto, "texto pegado"); }}>Detectar requisitos</button>
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
          <p className="mono sube text-[10px] text-[var(--bone-faint)]" style={{ "--i": 0 }}>Paso 2 · confirma la separación · {origen}</p>
          <div className="sube -mt-2 [&>div]:justify-start" style={{ "--i": 0 }}><SelectorProyecto valor={proyectoId} onCambio={setProyectoId} /></div>
          <h1 className="serif sube text-[clamp(40px,4vw,64px)] leading-[.95]" style={{ "--i": 1 }}>
            Encontré <em>{validas.length}</em> {validas.length === 1 ? "requisito" : "requisitos"}.
          </h1>
          <p className="sube text-sm text-[var(--bone-dim)]" style={{ "--i": 2 }}>Corrige el texto, une los que se partieron mal o quita los que sobran.</p>
          <ol className="space-y-1">
            {piezas.map((p, i) => (
              <li key={p.clave} className="sube group flex items-start gap-4 border-b border-[var(--line)] py-2" style={{ "--i": 3 + i }}>
                <span className="mono pt-2.5 text-[10px] text-[var(--bone-faint)]">{String(i + 1).padStart(2, "0")}</span>
                <textarea
                  value={p.texto}
                  rows={Math.max(1, Math.ceil(p.texto.length / 70))}
                  onChange={(e) => editar(i, e.target.value)}
                  onFocus={() => orb.setMood("listening")}
                  onBlur={() => orb.setMood("idle")}
                  className="min-w-0 flex-1 resize-none bg-transparent py-1.5 [field-sizing:content] text-[15px] leading-relaxed text-[var(--bone)] outline-none"
                />
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
          <div className="sube flex flex-wrap gap-3 pt-2" style={{ "--i": 5 + piezas.length }}>
            <button className="pill" disabled={!validas.length || saliendo || !proyectoId} onClick={analizar} onPointerEnter={() => orb.poke(0.3)}>
              Analizar {validas.length} {validas.length === 1 ? "requisito" : "requisitos"}
            </button>
            <button className="pill ghost" onClick={() => { setPiezas([]); setFase("inicio"); }}>Empezar de nuevo</button>
          </div>
        </section>
      )}
    </main>
  );
}
