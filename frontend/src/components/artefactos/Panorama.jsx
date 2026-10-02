import { Link } from "react-router";
import { artefactosDe, descargar } from "./modelo";

/*
 * Big Picture de un conjunto de requisitos: actores, quién hace qué,
 * restricciones y términos resueltos. Se descarga en JSON.
 */
const texto = (x) => (typeof x === "string" ? x : Object.values(x).join(" "));

export default function Panorama({ lista, nombre = "big-picture" }) {
  const piezas = lista.map((r) => ({ id: r.id, bp: artefactosDe(r)?.bigPicture })).filter((p) => p.bp);
  if (!piezas.length) return <p className="text-sm text-[var(--bone-dim)]">Todavía no hay Big Picture: los requisitos siguen en proceso.</p>;

  const actores = [...new Set(piezas.flatMap((p) => p.bp.actores ?? []))];
  const terminos = piezas.flatMap((p) => (p.bp.terminosResueltos ?? []).map((t) => ({ ...t, id: p.id })));
  const combinado = { generado: new Date().toISOString(), requisitos: piezas.map((p) => p.bp) };
  const i = (n) => ({ "--i": n });

  return (
    <div className="space-y-6">
      <div className="sube" style={i(0)}>
        <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Actores</p>
        <div className="flex flex-wrap gap-2">
          {actores.map((a) => <span key={a} className="rounded-full border border-[var(--line)] px-3 py-1 text-sm">{a}</span>)}
        </div>
      </div>

      <div className="sube" style={i(1)}>
        <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Quién hace qué</p>
        <ol className="border-t border-[var(--line)]">
          {piezas.flatMap((p) =>
            (p.bp.acciones ?? []).map((ac, j) => (
              <li key={`${p.id}-${j}`} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-[var(--line)] py-3 text-[15px]">
                <span>{ac.actor}</span>
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
        <div className="sube" style={i(2)}>
          <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Restricciones</p>
          <ul className="space-y-1 text-sm text-[var(--bone-dim)]">
            {piezas.flatMap((p) => (p.bp.restricciones ?? []).map((x, j) => (
              <li key={`${p.id}-${j}`}>{texto(x)} <span className="mono text-[9px] text-[var(--bone-faint)]">· {p.id}</span></li>
            )))}
          </ul>
        </div>
      )}

      {terminos.length > 0 && (
        <div className="sube" style={i(3)}>
          <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Términos resueltos</p>
          <ul className="space-y-1 text-sm">
            {terminos.map((t, j) => (
              <li key={j}>
                <span className="italic text-[#ffb347]">«{t.termino}»</span>
                <span className="text-[var(--bone-dim)]"> = {t.significado}</span>
                <span className="mono text-[9px] text-[var(--bone-faint)]"> · {t.id}{t.via ? ` · ${t.via}` : ""}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <details className="sube rounded-xl border border-[var(--line)] p-4" style={i(4)}>
        <summary className="mono cursor-pointer text-[10px] text-[var(--bone-dim)]">JSON combinado</summary>
        <pre className="mt-3 max-h-80 overflow-auto font-mono text-[11px] leading-relaxed text-[var(--bone-dim)]">{JSON.stringify(combinado, null, 2)}</pre>
      </details>
      <button className="pill ghost sube" style={i(5)} onClick={() => descargar(`${nombre}.json`, JSON.stringify(combinado, null, 2), "application/json")}>
        Descargar JSON
      </button>
    </div>
  );
}
