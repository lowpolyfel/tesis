import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useOrb, usePoseEsfera } from "../components/orb/useOrb";
import { useLote } from "../hooks/useLote";

/*
 * Generar Big Picture: el panorama del lote. Quién hace qué sobre qué, qué
 * restricciones aparecieron y qué términos se resolvieron. Se descarga en JSON.
 */
const POSE = { d: { x: -0.31, y: 0, s: 0.72 }, m: { x: 0, y: -0.36, s: 0.38 } };
const ARMADO_MS = 1500;

const bigPictureDe = (r) => (r.artefactos?.validados ?? r.artefactos?.borrador ?? r.artefactos?.propuesta)?.bigPicture;
const texto = (x) => (typeof x === "string" ? x : Object.values(x).join(" "));

export default function BigPicture() {
  const orb = useOrb();
  const [params] = useSearchParams();
  const ids = useMemo(() => (params.get("ids") ?? "").split(",").filter(Boolean), [params]);
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

  const piezas = (lista ?? []).map((r) => ({ id: r.id, bp: bigPictureDe(r) })).filter((p) => p.bp);
  const actores = [...new Set(piezas.flatMap((p) => p.bp.actores ?? []))];
  const terminos = piezas.flatMap((p) => (p.bp.terminosResueltos ?? []).map((t) => ({ ...t, id: p.id })));
  const combinado = { generado: new Date().toISOString(), requisitos: piezas.map((p) => p.bp) };

  const descargar = () => {
    const blob = new Blob([JSON.stringify(combinado, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `big-picture-${ids[0] ?? "lote"}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <main className="relative z-10 mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-5 px-6 pt-[30vh] pb-16 md:mr-[7vw] md:pt-28">
      <p className="mono sube text-[10px] text-[var(--bone-faint)]">Big Picture</p>
      <h1 className="serif sube text-[clamp(44px,4.6vw,72px)] leading-[.95]" style={{ "--i": 1 }}>
        {listo ? <>El <em>panorama</em>.</> : <>Uniendo las piezas<em>…</em></>}
      </h1>

      {listo && lista && (
        <>
          <div className="sube" style={{ "--i": 2 }}>
            <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Actores</p>
            <div className="flex flex-wrap gap-2">
              {actores.map((a) => (
                <span key={a} className="rounded-full border border-[var(--line)] px-3 py-1 text-sm">{a}</span>
              ))}
            </div>
          </div>

          <div className="sube" style={{ "--i": 3 }}>
            <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Quién hace qué</p>
            <ol className="border-t border-[var(--line)]">
              {piezas.flatMap((p) =>
                (p.bp.acciones ?? []).map((ac, j) => (
                  <li key={`${p.id}-${j}`} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-[var(--line)] py-3 text-[15px]">
                    <span className="text-[var(--bone)]">{ac.actor}</span>
                    <span className="serif text-[22px] italic text-[var(--c1)]">{ac.verbo}</span>
                    <span>{ac.objeto}</span>
                    {Object.entries(ac)
                      .filter(([k]) => !["actor", "verbo", "objeto"].includes(k))
                      .map(([k, v]) => <span key={k} className="text-xs text-[var(--bone-faint)]">{k}: {Array.isArray(v) ? v.join(", ") : v}</span>)}
                    <Link to={`/requisitos/${p.id}`} className="mono ml-auto text-[9.5px] text-[var(--bone-faint)] hover:text-[var(--bone)]">{p.id}</Link>
                  </li>
                ))
              )}
            </ol>
          </div>

          {piezas.some((p) => p.bp.restricciones?.length) && (
            <div className="sube" style={{ "--i": 4 }}>
              <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Restricciones</p>
              <ul className="space-y-1 text-sm text-[var(--bone-dim)]">
                {piezas.flatMap((p) => (p.bp.restricciones ?? []).map((x, j) => <li key={`${p.id}-${j}`}>{texto(x)} <span className="mono text-[9px] text-[var(--bone-faint)]">· {p.id}</span></li>))}
              </ul>
            </div>
          )}

          {terminos.length > 0 && (
            <div className="sube" style={{ "--i": 5 }}>
              <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Términos resueltos</p>
              <ul className="space-y-1 text-sm">
                {terminos.map((t, j) => (
                  <li key={j}>
                    <span className="italic text-[#ffb347]">«{t.termino}»</span>
                    <span className="text-[var(--bone-dim)]"> = {t.significado}</span>
                    {t.via && <span className="mono text-[9px] text-[var(--bone-faint)]"> · {t.via}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <details className="sube rounded-xl border border-[var(--line)] p-4" style={{ "--i": 6 }}>
            <summary className="mono cursor-pointer text-[10px] text-[var(--bone-dim)]">JSON combinado</summary>
            <pre className="mt-3 max-h-80 overflow-auto font-mono text-[11px] leading-relaxed text-[var(--bone-dim)]">{JSON.stringify(combinado, null, 2)}</pre>
          </details>

          <div className="sube flex flex-wrap items-center gap-3" style={{ "--i": 7 }}>
            <button className="pill" onClick={descargar}>Descargar JSON</button>
            <Link to={`/lel/generar?ids=${ids.join(",")}`} className="pill ghost">Generar LEL</Link>
          </div>
        </>
      )}
    </main>
  );
}
