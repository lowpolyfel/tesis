import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useOrb, usePoseEsfera } from "../components/orb/useOrb";
import { useLote } from "../hooks/useLote";
import Panorama from "../components/artefactos/Panorama";
import ModeloConceptual from "../components/artefactos/ModeloConceptual";

/*
 * Generar Big Picture: el panorama del lote y su modelo conceptual (UML de
 * clases con Mermaid, exportable a PlantUML).
 */
const POSE = { d: { x: -0.33, y: 0, s: 0.62 }, m: { x: 0, y: -0.38, s: 0.34 } };
const ARMADO_MS = 1500;

export default function BigPicture() {
  const orb = useOrb();
  const [params, setParams] = useSearchParams();
  const ids = useMemo(() => (params.get("ids") ?? "").split(",").filter(Boolean), [params]);
  const vista = params.get("vista") === "modelo" ? "modelo" : "panorama";
  const { lista } = useLote(ids);
  const [listo, setListo] = useState(false);

  usePoseEsfera(POSE, []);
  useEffect(() => {
    orb.setMood("lecturaA");
    orb.update("core", { label: "Big Picture", sub: "uniendo las piezas…", active: true });
    const t = setTimeout(() => { setListo(true); orb.update("core", { sub: null, active: false }); }, ARMADO_MS);
    return () => {
      clearTimeout(t);
      orb.update("core", { label: null, sub: null, active: false });
      orb.setMood("idle");
    };
  }, [orb]);

  useEffect(() => {
    if (listo) orb.update("core", { sub: vista === "modelo" ? "modelo conceptual" : null });
  }, [listo, vista, orb]);

  const cambiar = (v) => {
    const p = Object.fromEntries(params);
    setParams(v === "modelo" ? { ...p, vista: "modelo" } : { ids: p.ids }, { replace: true });
    orb.poke(0.5);
  };

  return (
    <main className="relative z-10 mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-5 px-6 pt-[30vh] pb-16 md:mr-[5vw] md:pt-28">
      <p className="mono sube text-[10px] text-[var(--bone-faint)]">Big Picture</p>
      <h1 className="serif sube text-[clamp(44px,4.6vw,72px)] leading-[.95]" style={{ "--i": 1 }}>
        {!listo ? <>Uniendo las piezas<em>…</em></> : vista === "modelo" ? <>Modelo <em>conceptual</em>.</> : <>El <em>panorama</em>.</>}
      </h1>

      {listo && lista && (
        <>
          <div className="mono sube flex gap-5 text-[10px]" style={{ "--i": 2 }}>
            {[["panorama", "Panorama"], ["modelo", "Modelo conceptual (UML)"]].map(([k, t]) => (
              <button key={k} onClick={() => cambiar(k)} className={vista === k ? "text-[var(--bone)] underline decoration-[var(--c1)] underline-offset-[6px]" : "text-[var(--bone-faint)] hover:text-[var(--bone)]"}>
                {t}
              </button>
            ))}
          </div>
          {vista === "panorama" ? (
            <Panorama lista={lista} nombre={`big-picture-${ids[0] ?? "lote"}`} />
          ) : (
            <ModeloConceptual lista={lista} nombre={`modelo-conceptual-${ids[0] ?? "lote"}`} />
          )}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link to={`/lel/generar?ids=${ids.join(",")}`} className="pill ghost">Generar LEL</Link>
            {lista[0]?.proyectoId && (
              <Link to={`/proyectos/${lista[0].proyectoId}`} className="mono px-2 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]">Ver el proyecto →</Link>
            )}
          </div>
        </>
      )}
    </main>
  );
}
