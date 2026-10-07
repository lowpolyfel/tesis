import { useEffect, useId, useState } from "react";
import { descargar, svgAPng, urlPlantUML } from "./exportar";

/*
 * Dibuja el Mermaid que arma el backend (app/artefactos/exportar.py) y ofrece
 * sus exportaciones. El texto trae sus propios estilos claros (pensados para la
 * tesis), así que el diagrama va sobre fondo blanco. Mermaid se carga solo al
 * abrir esta vista.
 */
let mermaidListo = null;
const cargarMermaid = () => (mermaidListo ??= import("mermaid").then((m) => m.default));

const TEMA = {
  theme: "base",
  themeVariables: {
    background: "#ffffff",
    primaryColor: "#eef0ff",
    primaryTextColor: "#1b1712",
    primaryBorderColor: "#5b5bd6",
    lineColor: "#4b463f",
    textColor: "#1b1712",
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
    fontSize: "14px",
  },
};

export default function Diagrama({ mermaid, plantuml, nombre }) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [vista, setVista] = useState("diagrama");
  const [svg, setSvg] = useState(null);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);

  useEffect(() => {
    let activo = true;
    setSvg(null);
    setError(null);
    cargarMermaid()
      .then(async (m) => {
        m.initialize({ startOnLoad: false, securityLevel: "strict", flowchart: { htmlLabels: false }, ...TEMA });
        const { svg: s } = await m.render(`bp${uid}${Date.now()}`, mermaid);
        if (activo) setSvg(s);
      })
      .catch((e) => activo && setError(e.message ?? String(e)));
    return () => { activo = false; };
  }, [mermaid, uid]);

  const copiar = async (t) => {
    try { await navigator.clipboard.writeText(t); setAviso("Copiado."); } catch { setAviso("No se pudo copiar."); }
    setTimeout(() => setAviso(null), 1800);
  };

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-2xl border border-[var(--line)] bg-[#ffffff] p-4">
        {error && <p className="text-sm text-[#b42318]">No se pudo dibujar: {error}</p>}
        {!svg && !error && <p className="mono flex items-center gap-2 text-[10px] text-[#6b6255]"><span className="gira" /> Dibujando…</p>}
        {svg && <div className="modelo-svg mx-auto min-w-[560px]" dangerouslySetInnerHTML={{ __html: svg }} />}
      </div>
      <div className="mono flex flex-wrap items-center gap-x-4 gap-y-2 text-[10px] text-[var(--bone-faint)]">
        <span>Descargar</span>
        <button className="hover:text-[var(--bone)] disabled:opacity-40" disabled={!svg} onClick={async () => descargar(`${nombre}.png`, await svgAPng(svg))}>PNG</button>
        <button className="hover:text-[var(--bone)] disabled:opacity-40" disabled={!svg} onClick={() => descargar(`${nombre}.svg`, svg, "image/svg+xml")}>SVG</button>
        <button className="hover:text-[var(--bone)]" onClick={() => descargar(`${nombre}.mmd`, mermaid, "text/plain")}>Mermaid</button>
        <button className="hover:text-[var(--bone)]" onClick={() => descargar(`${nombre}.puml`, plantuml, "text/plain")}>PlantUML</button>
        <button className="ml-auto hover:text-[var(--bone)]" onClick={() => setVista((v) => (v === "diagrama" ? "mermaid" : "diagrama"))}>
          {vista === "diagrama" ? "ver código" : "ocultar código"}
        </button>
      </div>
      {vista !== "diagrama" && (
        <div className="space-y-2">
          <div className="mono flex flex-wrap gap-4 text-[10px]">
            {[["mermaid", "Mermaid"], ["plantuml", "PlantUML"]].map(([k, t]) => (
              <button key={k} onClick={() => setVista(k)} className={vista === k ? "text-[var(--bone)]" : "text-[var(--bone-faint)] hover:text-[var(--bone)]"}>{t}</button>
            ))}
            <button className="text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => copiar(vista === "plantuml" ? plantuml : mermaid)}>copiar</button>
            {vista === "plantuml" && (
              <button className="text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={async () => window.open(await urlPlantUML(plantuml), "_blank", "noopener")}>abrir en PlantUML ↗</button>
            )}
            {aviso && <span className="text-[var(--bone-dim)]">{aviso}</span>}
          </div>
          <pre className="max-h-[50vh] overflow-auto rounded-2xl border border-[var(--line)] bg-white/[0.02] p-4 font-mono text-[11.5px] leading-relaxed text-[var(--bone-dim)]">
            {vista === "mermaid" ? mermaid : plantuml}
          </pre>
        </div>
      )}
    </div>
  );
}
