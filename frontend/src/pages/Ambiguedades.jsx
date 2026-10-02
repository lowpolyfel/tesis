import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useApi } from "../hooks/useApi";
import { listarProyectos, obtenerAmbiguedades } from "../services/api";
import TextoMarcado, { TONO_AMBIGUEDAD } from "../components/TextoMarcado";
import { VIA } from "./Analisis";

/*
 * Ambigüedades: cada término ambiguo detectado, dónde aparece y qué lectura
 * se adoptó en cada requisito. Señala cuando el mismo término se resolvió
 * distinto en dos requisitos (posible inconsistencia del léxico) y permite
 * comparar dos requisitos lado a lado.
 */
const norm = (s) => (s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

export default function Ambiguedades() {
  const { datos: grupos, cargando } = useApi(obtenerAmbiguedades);
  const { datos: proyectos } = useApi(listarProyectos);
  const [params, setParams] = useSearchParams();
  const proyecto = params.get("proyecto") ?? "";
  const tipo = params.get("tipo") ?? "";
  const [comparar, setComparar] = useState([null, null]);

  const set = (k, v) => {
    const p = Object.fromEntries(params);
    if (v) p[k] = v; else delete p[k];
    setParams(p, { replace: true });
  };

  const visibles = useMemo(() => {
    if (!grupos) return [];
    return grupos
      .map((g) => ({ ...g, apariciones: g.apariciones.filter((a) => !proyecto || a.proyectoId === proyecto) }))
      .filter((g) => g.apariciones.length && (!tipo || g.tipo === tipo))
      .map((g) => ({ ...g, inconsistente: new Set(g.apariciones.map((a) => norm(a.adoptada)).filter(Boolean)).size > 1 }));
  }, [grupos, proyecto, tipo]);

  // requisito → (término → lectura adoptada)
  const adopciones = useMemo(() => {
    const m = new Map();
    for (const g of visibles) for (const a of g.apariciones) {
      if (!m.has(a.requisitoId)) m.set(a.requisitoId, new Map());
      m.get(a.requisitoId).set(norm(g.termino), a.adoptada);
    }
    return m;
  }, [visibles]);

  const requisitos = useMemo(() => {
    const m = new Map();
    for (const g of visibles) for (const a of g.apariciones) m.set(a.requisitoId, a);
    return [...m.values()].sort((a, b) => a.requisitoId.localeCompare(b.requisitoId));
  }, [visibles]);

  if (cargando) return <p className="text-sm text-[var(--bone-dim)]">Buscando ambigüedades…</p>;

  const apariciones = visibles.reduce((a, g) => a + g.apariciones.length, 0);
  const inconsistentes = visibles.filter((g) => g.inconsistente).length;

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <p className="mono text-[10px] text-[var(--bone-faint)]">{visibles.length} términos · {apariciones} apariciones · {inconsistentes} resueltos de forma distinta</p>
        <h1>Ambigüedades.</h1>
        <p className="max-w-2xl text-sm text-[var(--bone-dim)]">
          Cada término que se marcó como ambiguo, en qué requisitos aparece y qué lectura se adoptó. Si el mismo término se resolvió distinto en dos requisitos, se señala: es una posible contradicción del léxico.
        </p>
        <div className="mono flex flex-wrap items-center gap-4 text-[10px]">
          <select value={proyecto} onChange={(e) => set("proyecto", e.target.value)} className="rounded-full border border-[var(--line)] bg-transparent px-3 py-1.5 text-[11px] normal-case tracking-normal outline-none">
            <option value="" className="bg-[#16130f]">Todos los proyectos</option>
            {(proyectos ?? []).map((p) => <option key={p.id} value={p.id} className="bg-[#16130f]">{p.nombre}</option>)}
          </select>
          {["", "mexicanismo", "vaguedad", "polisemia"].map((t) => (
            <button key={t || "todos"} onClick={() => set("tipo", t)} className={`flex items-center gap-1.5 ${tipo === t ? "text-[var(--bone)]" : "text-[var(--bone-faint)] hover:text-[var(--bone)]"}`}>
              {t && <span className="punto" style={{ background: TONO_AMBIGUEDAD[t] }} />}
              {t || "todos"}
            </button>
          ))}
        </div>
      </header>

      <Comparador requisitos={requisitos} adopciones={adopciones} seleccion={comparar} onSeleccion={setComparar} />

      <ol className="space-y-4">
        {visibles.map((g, gi) => (
          <li key={g.termino} className="sube rounded-2xl border border-[var(--line)] bg-white/[0.02] p-5" style={{ "--i": gi }}>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="serif text-[30px] italic leading-none" style={{ color: TONO_AMBIGUEDAD[g.tipo] }}>«{g.termino}»</span>
              <span className="mono text-[9.5px] text-[var(--bone-faint)]">{g.tipo} · {g.fuente}</span>
              <span className="mono ml-auto text-[9.5px] text-[var(--bone-dim)]">{g.apariciones.length} {g.apariciones.length === 1 ? "requisito" : "requisitos"}</span>
            </div>
            {g.inconsistente && (
              <p className="mt-3 rounded-lg bg-[#ff5265]/10 px-3 py-2 text-sm text-[#ffb3bc]">
                Se resolvió distinto según el requisito. Revisa si el dominio realmente usa dos sentidos o si conviene unificar la entrada del LEL.
              </p>
            )}
            <table className="mt-3 w-full table-fixed text-left text-sm">
              <thead className="mono text-[9px] text-[var(--bone-faint)]">
                <tr>
                  <th className="w-20 py-1.5 font-normal">Requisito</th>
                  <th className="py-1.5 font-normal">Lectura A</th>
                  <th className="py-1.5 font-normal">Lectura B</th>
                  <th className="w-28 py-1.5 font-normal">Se resolvió</th>
                  <th className="w-10 py-1.5" />
                </tr>
              </thead>
              <tbody>
                {g.apariciones.map((a) => {
                  const via = VIA[a.via];
                  const adoptadaA = a.adoptada && norm(a.adoptada) === norm(a.lecturas.A);
                  const adoptadaB = a.adoptada && norm(a.adoptada) === norm(a.lecturas.B);
                  return (
                    <tr key={a.requisitoId} className="border-t border-[var(--line)] align-top">
                      <td className="py-2">
                        <Link to={`/requisitos/${a.requisitoId}`} className="mono text-[10px] hover:text-[var(--c1)]">{a.requisitoId}</Link>
                        <p className="mt-0.5 truncate text-[10.5px] text-[var(--bone-faint)]" title={a.proyecto}>{a.proyecto}</p>
                      </td>
                      <td className={`py-2 pr-3 ${adoptadaA ? "text-[var(--bone)]" : "text-[var(--bone-faint)]"}`}>{adoptadaA && "✓ "}{a.lecturas.A ?? "—"}</td>
                      <td className={`py-2 pr-3 ${adoptadaB ? "text-[var(--bone)]" : "text-[var(--bone-faint)]"}`}>{adoptadaB && "✓ "}{a.lecturas.B ?? "—"}</td>
                      <td className="mono py-2 text-[9.5px] text-[var(--bone-dim)]">
                        {via ? <span className="flex items-center gap-1.5"><span className="punto" style={{ background: via.tono }} />{via.texto}</span> : "en proceso"}
                        {a.similitud != null && <span className="text-[var(--bone-faint)]">sim. {a.similitud.toFixed(2)}{a.rondas ? ` · ${a.rondas}R` : ""}</span>}
                      </td>
                      <td className="py-2 text-right">
                        <button
                          title="Comparar este requisito"
                          className="mono text-[9px] text-[var(--bone-faint)] hover:text-[var(--c1)]"
                          onClick={() => {
                            setComparar(([x, y]) => (!x || x === a.requisitoId ? [a.requisitoId, y] : [x, a.requisitoId]));
                            window.scrollTo({ top: 0, behavior: "smooth" });
                          }}
                        >
                          ⇄
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </li>
        ))}
        {!visibles.length && <p className="text-sm text-[var(--bone-dim)]">No hay ambigüedades con este filtro.</p>}
      </ol>
    </div>
  );
}

/* Dos requisitos lado a lado: términos en común y si se resolvieron igual */
function Comparador({ requisitos, adopciones, seleccion, onSeleccion }) {
  const [a, b] = seleccion.map((id) => requisitos.find((r) => r.requisitoId === id) ?? null);
  const terminos = (r) => new Map((r?.marcados ?? []).map((m) => [norm(m.texto), m.texto]));
  const ta = terminos(a), tb = terminos(b);
  const comunes = [...ta.keys()].filter((k) => tb.has(k));

  return (
    <section className="rounded-2xl border border-[var(--line)] p-5">
      <div className="flex flex-wrap items-center gap-3">
        <p className="mono text-[10px] text-[var(--bone-dim)]">Comparar requisitos</p>
        {[0, 1].map((i) => (
          <select
            key={i}
            value={seleccion[i] ?? ""}
            onChange={(e) => onSeleccion(i === 0 ? [e.target.value || null, seleccion[1]] : [seleccion[0], e.target.value || null])}
            className="mono rounded-full border border-[var(--line)] bg-transparent px-3 py-1.5 text-[10px] outline-none"
          >
            <option value="" className="bg-[#16130f]">{i === 0 ? "Requisito A…" : "Requisito B…"}</option>
            {requisitos.map((r) => <option key={r.requisitoId} value={r.requisitoId} className="bg-[#16130f]">{r.requisitoId} · {r.texto.slice(0, 48)}</option>)}
          </select>
        ))}
      </div>

      {a && b ? (
        <div className="mt-4 space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {[a, b].map((r) => (
              <div key={r.requisitoId} className="rounded-xl bg-white/[0.025] p-4">
                <p className="mono text-[9.5px] text-[var(--bone-faint)]">{r.requisitoId} · {r.proyecto}</p>
                <p className="serif mt-1 text-[21px] leading-snug">«<TextoMarcado texto={r.texto} marcados={r.marcados} />»</p>
                <p className="mono mt-2 text-[9.5px] text-[var(--bone-dim)]">
                  {VIA[r.via]?.texto ?? "en proceso"}{r.similitud != null ? ` · similitud ${r.similitud.toFixed(2)}` : ""}
                </p>
              </div>
            ))}
          </div>
          <div>
            <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Términos en común</p>
            {comunes.length ? (
              <ul className="space-y-1 text-sm">
                {comunes.map((k) => {
                  const la = adopciones.get(a.requisitoId)?.get(k);
                  const lb = adopciones.get(b.requisitoId)?.get(k);
                  const igual = la && lb && norm(la) === norm(lb);
                  return (
                    <li key={k} className="flex flex-wrap items-baseline gap-x-2">
                      <span className="italic text-[#ffb347]">«{ta.get(k)}»</span>
                      <span className="text-[var(--bone-dim)]">{a.requisitoId}: {la ?? "—"} · {b.requisitoId}: {lb ?? "—"}</span>
                      {la && lb && (
                        <span className={`mono text-[9.5px] ${igual ? "text-[#8ff5c0]" : "text-[#ffb3bc]"}`}>{igual ? "se resolvió igual" : "se resolvió distinto"}</span>
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-[var(--bone-dim)]">No comparten términos ambiguos.</p>
            )}
          </div>
          <p className="mono text-[9.5px] text-[var(--bone-faint)]">
            Próximamente: similitud semántica entre requisitos (embeddings) para detectar duplicados y contradicciones.
          </p>
        </div>
      ) : (
        <p className="mt-3 text-sm text-[var(--bone-faint)]">Elige dos requisitos, o usa ⇄ en la lista de términos.</p>
      )}
    </section>
  );
}
