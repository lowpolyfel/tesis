import { useMemo } from "react";
import { Link, useSearchParams } from "react-router";
import { useApi } from "../hooks/useApi";
import { ambiguedadesDeProyecto } from "../services/backend";
import ElegirProyecto, { useProyectoElegido } from "../components/ElegirProyecto";
import { INFO_VIA, infoEstado } from "../constants/estados";
import { TIPOS, tipo as infoTipo } from "../constants/agentes";

/*
 * Ambigüedades de un proyecto (GET /proyectos/{id}/ambiguedades, ADR 0015):
 *   - cada término con ambigüedad, en qué requisitos aparece, cómo se resolvió
 *     en cada uno y qué significado validó la persona;
 *   - un término es inconsistente si quedó validado con significados distintos
 *     en dos requisitos, o si su símbolo del LEL tiene nociones distintas;
 *   - las estructuras de alcance y anáfora que detectaron los filtros;
 *   - la vaguedad, que se marca y no se debate, y los regionalismos, que pasan
 *     al Clasificador como cualquier candidato;
 *   - un término que los filtros dieron por resuelto con el LEL aparece con esa
 *     marca: es la memoria funcionando, no un veredicto del Clasificador.
 * La contradicción ENTRE requisitos es otro módulo (Comparaciones, exploratorio).
 */
const TIPOS_DEBATIDOS = ["lexica", "alcance", "anaforica", "sintactica"];
const ETIQUETA_FILTRO = { alcance: "Alcance", anafora: "Anáfora" };

export default function Ambiguedades() {
  const { proyectoId, proyecto, proyectos, elegir } = useProyectoElegido();
  const [params, setParams] = useSearchParams();
  const tipo = params.get("tipo") ?? "";
  const soloInconsistentes = params.get("inconsistentes") === "1";
  const { datos: a, error, cargando } = useApi(
    () => (proyectoId ? ambiguedadesDeProyecto(proyectoId) : Promise.resolve(null)),
    [proyectoId],
  );

  const set = (k, v) => setParams((prev) => {
    const p = new URLSearchParams(prev);
    if (v) p.set(k, v); else p.delete(k);
    return p;
  }, { replace: true });

  const visibles = useMemo(() => (a?.terminos ?? [])
    .filter((g) => !tipo || g.tipos.includes(tipo))
    .filter((g) => !soloInconsistentes || g.inconsistente), [a, tipo, soloInconsistentes]);

  const apariciones = (a?.terminos ?? []).reduce((n, g) => n + g.apariciones.length, 0);

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <p className="mono text-[10px] text-[var(--bone-faint)]">
          {a ? `${a.terminos.length} términos · ${apariciones} apariciones · ${a.totales.inconsistentes} inconsistentes` : "Ambigüedades del proyecto"}
        </p>
        <h1>Ambigüedades.</h1>
        <p className="max-w-2xl text-sm text-[var(--bone-dim)]">
          Cada término que se trató como ambiguo, en qué requisitos aparece y cómo se resolvió en cada uno. Si el mismo término quedó validado con significados distintos, se señala como inconsistencia del vocabulario.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <ElegirProyecto proyectoId={proyectoId} proyectos={proyectos} onCambio={elegir} />
          {proyectoId && <Link className="pill ghost" to={`/comparaciones?proyecto=${proyectoId}`}>Contradicciones entre requisitos (exploratorio) →</Link>}
        </div>
      </header>

      {error && <p className="text-sm text-[var(--danger)]">{error.message}</p>}
      {cargando && !a && <p className="text-sm text-[var(--bone-dim)]">Buscando ambigüedades…</p>}

      {a && (
        <>
          <Totales a={a} tipo={tipo} onTipo={(t) => set("tipo", t === tipo ? "" : t)} />

          <section className="space-y-4">
            <div className="flex flex-wrap items-baseline gap-4">
              <h2>Términos</h2>
              <label className="mono flex cursor-pointer items-center gap-2 text-[10px] text-[var(--bone-dim)]">
                <input type="checkbox" checked={soloInconsistentes} onChange={(e) => set("inconsistentes", e.target.checked ? "1" : "")} />
                solo inconsistentes ({a.totales.inconsistentes})
              </label>
              {tipo && <button className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => set("tipo", "")}>quitar filtro «{infoTipo(tipo).etiqueta}» ×</button>}
            </div>
            <ol className="space-y-4">
              {visibles.map((g, i) => <Grupo key={g.clave} g={g} i={i} proyectoId={proyectoId} />)}
              {!visibles.length && (
                <p className="text-sm text-[var(--bone-dim)]">
                  {a.terminos.length ? "Ningún término con este filtro." : `${proyecto?.nombre ?? "Este proyecto"} aún no tiene términos ambiguos analizados.`}
                </p>
              )}
            </ol>
          </section>

          {a.estructuras.length > 0 && (
            <section className="space-y-3">
              <h2>Alcance y anáfora</h2>
              <p className="max-w-2xl text-sm text-[var(--bone-dim)]">Estructuras que detectaron los filtros (spaCy, sin LLM) y que pasaron al Clasificador como términos a interpretar.</p>
              <ul className="border-t border-[var(--line)]">
                {a.estructuras.map((e, i) => (
                  <li key={`${e.req_id}-${e.termino}-${i}`} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-[var(--line)] py-2.5 text-sm">
                    <Link to={`/requisitos/${e.req_id}`} className="mono w-12 text-[10px] text-[var(--bone-faint)] hover:text-[var(--c1)]">{e.req_id}</Link>
                    <span className={`rounded px-1.5 text-[11px] ${infoTipo(e.decision_filtro === "anafora" ? "anaforica" : "alcance").clase}`}>{ETIQUETA_FILTRO[e.decision_filtro] ?? e.decision_filtro}</span>
                    <span className="italic">«{e.termino}»</span>
                    <span className="min-w-0 flex-1 text-[var(--bone-dim)] [overflow-wrap:anywhere]">{e.detalle}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <div className="grid gap-6 md:grid-cols-2">
            <ListaMarcados titulo="Vaguedad" tipo="vaguedad" items={a.vaguedad} nota="Límite impreciso (catálogo de vaguedad). Se marca para la persona; no se debate." />
            <ListaMarcados titulo="Regionalismos" tipo="regional" items={a.regionales} nota="Expresiones del español de trabajo en México (catálogo regional). Pasan al Clasificador." />
          </div>
        </>
      )}
    </div>
  );
}

function Totales({ a, tipo, onTipo }) {
  const totalVias = Object.values(a.totales.por_via).reduce((x, y) => x + y, 0);
  return (
    <section className="grid gap-4 md:grid-cols-2">
      <div className="rounded-2xl border border-[var(--line)] p-4">
        <p className="mono mb-3 text-[9.5px] text-[var(--bone-faint)]">Por tipo de ambigüedad</p>
        <div className="flex flex-wrap gap-2">
          {TIPOS_DEBATIDOS.map((t) => (
            <button
              key={t}
              onClick={() => onTipo(t)}
              title={TIPOS[t].descripcion}
              className={`rounded-lg px-3 py-1.5 text-left ${TIPOS[t].clase} ${tipo === t ? "ring-2 ring-[var(--bone)]" : ""}`}
            >
              <span className="block font-mono text-[20px] leading-none">{a.totales.por_tipo[t] ?? 0}</span>
              <span className="text-[11px]">{TIPOS[t].etiqueta}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="rounded-2xl border border-[var(--line)] p-4">
        <p className="mono mb-3 text-[9.5px] text-[var(--bone-faint)]">Cómo se resolvieron</p>
        {totalVias > 0 && (
          <div className="mb-3 flex h-2 overflow-hidden rounded-full bg-white/[0.04]">
            {Object.entries(a.totales.por_via).filter(([, n]) => n).map(([v, n]) => (
              <span key={v} style={{ width: `${(100 * n) / totalVias}%`, background: INFO_VIA[v]?.tono ?? "rgba(239,233,222,.25)" }} />
            ))}
          </div>
        )}
        <p className="mono flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-[var(--bone-dim)]">
          {Object.entries(a.totales.por_via).map(([v, n]) => (
            <span key={v} className="flex items-center gap-1.5">
              <span className="punto" style={{ background: INFO_VIA[v]?.tono ?? "rgba(239,233,222,.25)" }} />
              {INFO_VIA[v]?.etiqueta ?? "sin resolver"} {n}
            </span>
          ))}
        </p>
      </div>
    </section>
  );
}

function Grupo({ g, i, proyectoId }) {
  return (
    <li className="sube rounded-2xl border border-[var(--line)] bg-white/[0.02] p-5" style={{ "--i": Math.min(i, 12) }}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="serif text-[30px] italic leading-none">«{g.termino}»</span>
        {g.tipos.map((t) => <span key={t} className={`rounded px-1.5 text-[11px] ${infoTipo(t).clase}`}>{infoTipo(t).etiqueta}</span>)}
        <span className="mono text-[9.5px] text-[var(--bone-faint)]">detectado por {g.origenes.join(", ")}</span>
        <span className="mono ml-auto text-[9.5px] text-[var(--bone-dim)]">{g.apariciones.length} {g.apariciones.length === 1 ? "requisito" : "requisitos"}</span>
      </div>

      {g.inconsistente && g.detalle_inconsistencia && <Inconsistencia d={g.detalle_inconsistencia} />}

      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[560px] table-fixed text-left text-sm">
          <thead className="mono text-[9px] text-[var(--bone-faint)]">
            <tr>
              <th className="w-20 py-1.5 font-normal">Requisito</th>
              <th className="w-24 py-1.5 font-normal">Tipo</th>
              <th className="w-40 py-1.5 font-normal">Se resolvió</th>
              <th className="py-1.5 font-normal">Significado</th>
            </tr>
          </thead>
          <tbody>
            {g.apariciones.map((ap) => {
              const via = ap.via ? INFO_VIA[ap.via] : null;
              // el término ya tenía noción validada en el LEL: no llegó al Clasificador
              if (ap.decision_filtro === "resuelto_por_lel") {
                return (
                  <tr key={`${ap.req_id}-lel`} className="border-t border-[var(--line)] align-top">
                    <td className="py-2">
                      <Link to={`/requisitos/${ap.req_id}`} className="mono text-[10px] hover:text-[var(--c1)]">{ap.req_id}</Link>
                      <p className="mono text-[9px] text-[var(--bone-faint)]">C{ap.ciclo}</p>
                    </td>
                    <td className="py-2 text-[12px] text-emerald-400">resuelto por el LEL</td>
                    <td className="mono py-2 text-[9.5px] text-[var(--bone-dim)]">memoria del LEL · no se debatió</td>
                    <td className="py-2 pr-2">
                      <Link className="text-[var(--bone-dim)] underline underline-offset-4 hover:text-[var(--bone)]" to={`/lel?proyecto=${proyectoId}&q=${encodeURIComponent(g.termino)}`}>
                        la noción vigente en el LEL →
                      </Link>
                    </td>
                  </tr>
                );
              }
              return (
                <tr key={`${ap.req_id}-${ap.tipo_ambiguedad}`} className="border-t border-[var(--line)] align-top">
                  <td className="py-2">
                    <Link to={`/requisitos/${ap.req_id}`} className="mono text-[10px] hover:text-[var(--c1)]">{ap.req_id}</Link>
                    <p className="mono text-[9px] text-[var(--bone-faint)]">C{ap.ciclo}</p>
                  </td>
                  <td className="py-2 text-[12px] text-[var(--bone-dim)]">{ap.tipo_ambiguedad ? infoTipo(ap.tipo_ambiguedad).etiqueta : "—"}</td>
                  <td className="mono py-2 text-[9.5px] text-[var(--bone-dim)]">
                    {via ? <span className="flex items-center gap-1.5"><span className="punto" style={{ background: via.tono }} />{via.etiqueta}</span> : <span>{infoEstado(ap.estado).etiqueta.toLowerCase()}</span>}
                    {ap.similitud_inicial != null && <span className="block text-[var(--bone-faint)]">sim. {ap.similitud_inicial.toFixed(2)}{ap.rondas ? ` · ${ap.rondas}R` : ""}</span>}
                  </td>
                  <td className="py-2 pr-2">
                    {ap.interpretacion_final ? (
                      <span><span className="text-emerald-500">✓ </span>{ap.interpretacion_final}</span>
                    ) : ap.propuesta ? (
                      <span className="text-[var(--bone-dim)]">{ap.propuesta} <span className="mono text-[9px] text-[var(--bone-faint)]">propuesta · {infoEstado(ap.estado).etiqueta.toLowerCase()}</span></span>
                    ) : (
                      <span className="text-[var(--bone-faint)]">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </li>
  );
}

function Inconsistencia({ d }) {
  return (
    <div className="mt-3 space-y-2 rounded-lg bg-[#ff5265]/10 px-3 py-2.5 text-sm text-[#ffb3bc]">
      <p>{d.texto}</p>
      {d.significados.length > 0 && (
        <ul className="space-y-1">
          {d.significados.map((s) => (
            <li key={s.significado}>
              «{s.significado}» <span className="mono text-[9.5px] opacity-80">en {s.req_ids.map((r, i) => <span key={r}>{i ? ", " : ""}<Link className="underline" to={`/requisitos/${r}`}>{r}</Link></span>)}</span>
            </li>
          ))}
        </ul>
      )}
      {d.lel.length > 0 && (
        <ul className="space-y-1">
          {d.lel.map((e) => (
            <li key={`${e.req_id}-${e.simbolo}`}>
              LEL «{e.simbolo}»: {e.nocion.join("; ")} <span className="mono text-[9.5px] opacity-80">(<Link className="underline" to={`/requisitos/${e.req_id}`}>{e.req_id}</Link>)</span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-[12px] opacity-80">Revisa si el dominio usa de verdad dos sentidos o si conviene unificar la entrada del LEL.</p>
    </div>
  );
}

function ListaMarcados({ titulo, tipo, items, nota }) {
  return (
    <section className="space-y-2">
      <h2>{titulo}</h2>
      <p className="text-sm text-[var(--bone-dim)]">{nota}</p>
      {items.length ? (
        <ul className="flex flex-wrap gap-2">
          {items.map((x) => (
            <li key={x.termino} className={`rounded-lg px-2.5 py-1 text-sm ${infoTipo(tipo).clase}`}>
              «{x.termino}»{" "}
              <span className="mono text-[9.5px] opacity-80">{x.req_ids.map((r, i) => <span key={r}>{i ? ", " : ""}<Link className="hover:underline" to={`/requisitos/${r}`}>{r}</Link></span>)}</span>
            </li>
          ))}
        </ul>
      ) : <p className="mono text-[10px] text-[var(--bone-faint)]">ninguno</p>}
    </section>
  );
}
