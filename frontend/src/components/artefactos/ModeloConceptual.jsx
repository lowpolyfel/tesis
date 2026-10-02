import { useEffect, useId, useMemo, useState } from "react";
import { construirModelo, aMermaid, aPlantUML, urlPlantUML, descargar } from "./modelo";

/*
 * Modelo conceptual (UML de clases) del conjunto de requisitos.
 * Se dibuja con Mermaid en el navegador y se exporta a SVG, PNG, .mmd y .puml.
 * Mermaid se carga solo al abrir esta vista.
 */
let mermaidListo = null;
const cargarMermaid = () => (mermaidListo ??= import("mermaid").then((m) => m.default));

const TEMAS = {
  oscuro: {
    theme: "base",
    themeVariables: {
      background: "transparent",
      primaryColor: "#1c1830",
      primaryTextColor: "#efe9de",
      primaryBorderColor: "#a99bff",
      lineColor: "#bfb6a6",
      textColor: "#efe9de",
      noteBkgColor: "#221d16",
      noteTextColor: "#efe9de",
      noteBorderColor: "#6b6255",
      fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      fontSize: "14px",
    },
  },
  claro: {
    theme: "base",
    themeVariables: {
      background: "#ffffff",
      primaryColor: "#eef0ff",
      primaryTextColor: "#1b1712",
      primaryBorderColor: "#5b5bd6",
      lineColor: "#4b463f",
      textColor: "#1b1712",
      noteBkgColor: "#fffbe8",
      noteTextColor: "#1b1712",
      noteBorderColor: "#c9b98a",
      fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      fontSize: "14px",
    },
  },
};

async function dibujar(codigo, tema, id) {
  const mermaid = await cargarMermaid();
  mermaid.initialize({ startOnLoad: false, securityLevel: "strict", htmlLabels: false, ...TEMAS[tema], class: { htmlLabels: false } });
  const { svg } = await mermaid.render(id, codigo);
  return svg;
}

/* PNG a partir del SVG (escala 2 para que se lea en la tesis) */
async function svgAPng(svg, fondo) {
  const img = new Image();
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  await new Promise((ok, mal) => { img.onload = ok; img.onerror = mal; img.src = url; });
  const doc = new DOMParser().parseFromString(svg, "image/svg+xml").documentElement;
  const vb = (doc.getAttribute("viewBox") ?? `0 0 ${img.width} ${img.height}`).split(/\s+/).map(Number);
  const [w, h] = [vb[2] || img.width, vb[3] || img.height];
  const canvas = document.createElement("canvas");
  canvas.width = w * 2;
  canvas.height = h * 2;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = fondo;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  URL.revokeObjectURL(url);
  return new Promise((ok) => canvas.toBlob(ok, "image/png"));
}

export default function ModeloConceptual({ lista, nombre = "modelo-conceptual", titulo = "Modelo conceptual" }) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [tema, setTema] = useState("oscuro");
  const [vista, setVista] = useState("diagrama");
  const [svg, setSvg] = useState(null);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);

  const modelo = useMemo(() => construirModelo(lista), [lista]);
  const mermaidCodigo = useMemo(() => aMermaid(modelo, { claro: tema === "claro" }), [modelo, tema]);
  const plantuml = useMemo(() => aPlantUML(modelo, { titulo }), [modelo, titulo]);

  useEffect(() => {
    if (!modelo.clases.length) return;
    let activo = true;
    setError(null);
    dibujar(mermaidCodigo, tema, `mmd${uid}${Date.now()}`)
      .then((s) => activo && setSvg(s))
      .catch((e) => activo && setError(e.message ?? String(e)));
    return () => { activo = false; };
  }, [mermaidCodigo, tema, uid, modelo.clases.length]);

  if (!modelo.clases.length) {
    return <p className="text-sm text-[var(--bone-dim)]">Todavía no hay artefactos con actores u objetos para dibujar el modelo.</p>;
  }

  const fondo = tema === "claro" ? "#ffffff" : "#0d0b0a";
  const abrirPlantUML = async () => window.open(await urlPlantUML(plantuml), "_blank", "noopener");
  const copiar = async (t) => {
    try { await navigator.clipboard.writeText(t); setAviso("Copiado."); } catch { setAviso("No se pudo copiar."); }
    setTimeout(() => setAviso(null), 1800);
  };
  const actores = modelo.clases.filter((c) => c.tipo === "actor").length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <p className="mono text-[9.5px] text-[var(--bone-faint)]">
          {actores} actores · {modelo.clases.length - actores} entidades · {modelo.relaciones.length} asociaciones
        </p>
        <div className="mono ml-auto flex gap-4 text-[9.5px]">
          {["diagrama", "mermaid", "plantuml"].map((v) => (
            <button key={v} onClick={() => setVista(v)} className={vista === v ? "text-[var(--bone)] underline decoration-[var(--c1)] underline-offset-4" : "text-[var(--bone-faint)] hover:text-[var(--bone)]"}>
              {v === "diagrama" ? "Diagrama" : v === "mermaid" ? "Código Mermaid" : "Código PlantUML"}
            </button>
          ))}
        </div>
      </div>

      {vista === "diagrama" && (
        <div className={`overflow-x-auto rounded-2xl border border-[var(--line)] p-4 ${tema === "claro" ? "bg-white" : "bg-white/[0.02]"}`}>
          {error && <p className="text-sm text-[var(--danger)]">No se pudo dibujar: {error}</p>}
          {!svg && !error && <p className="mono flex items-center gap-2 text-[10px] text-[var(--bone-faint)]"><span className="gira" /> Dibujando…</p>}
          {svg && <div className="modelo-svg mx-auto" dangerouslySetInnerHTML={{ __html: svg }} />}
        </div>
      )}
      {vista !== "diagrama" && (
        <pre className="max-h-[60vh] overflow-auto rounded-2xl border border-[var(--line)] bg-white/[0.02] p-4 font-mono text-[11.5px] leading-relaxed text-[var(--bone-dim)]">
          {vista === "mermaid" ? mermaidCodigo : plantuml}
        </pre>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button className="pill" disabled={!svg} onClick={async () => descargar(`${nombre}.png`, await svgAPng(svg, fondo))}>PNG</button>
        <button className="pill ghost" disabled={!svg} onClick={() => descargar(`${nombre}.svg`, svg, "image/svg+xml")}>SVG</button>
        <button className="pill ghost" onClick={() => descargar(`${nombre}.puml`, plantuml, "text/plain")}>.puml</button>
        <button className="pill ghost" onClick={() => descargar(`${nombre}.mmd`, mermaidCodigo, "text/plain")}>.mmd</button>
        <label className="mono ml-2 flex cursor-pointer items-center gap-2 text-[10px] text-[var(--bone-dim)]">
          <input type="checkbox" checked={tema === "claro"} onChange={(e) => setTema(e.target.checked ? "claro" : "oscuro")} className="accent-[var(--c1)]" />
          fondo claro (para la tesis)
        </label>
      </div>
      <div className="mono flex flex-wrap gap-4 text-[9.5px] text-[var(--bone-faint)]">
        <button className="hover:text-[var(--bone)]" onClick={abrirPlantUML}>Abrir en el servidor de PlantUML ↗</button>
        <button className="hover:text-[var(--bone)]" onClick={() => copiar(vista === "plantuml" ? plantuml : mermaidCodigo)}>
          Copiar código {vista === "plantuml" ? "PlantUML" : "Mermaid"}
        </button>
        {aviso && <span className="text-[var(--bone-dim)]">{aviso}</span>}
      </div>
    </div>
  );
}
