import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useApi } from "../hooks/useApi";
import { calibracionDeProyecto, calibracionGeneral, obtenerConfiguracion } from "../services/backend";
import ElegirProyecto, { useProyectoElegido } from "../components/ElegirProyecto";
import { INFO_VIA } from "../constants/estados";
import { tipo as infoTipo } from "../constants/agentes";

/*
 * Calibración del umbral como ANÁLISIS DE SENSIBILIDAD (ADR 0013). Solo lectura:
 * qué habría decidido la regla «similitud ≥ umbral» con otros umbrales sobre las
 * similitudes iniciales ya calculadas. La configuración no se toca desde aquí
 * (se cambia en backend/.env y cada traza guarda la suya). Si la evaluación dejó
 * etiquetas para el proyecto, se contrasta con el ground truth. Si la similitud
 * no separa los casos, es un hallazgo: el umbral no se ajusta para que salgan bien.
 */
const DECISION = { aceptado_directo: "aceptado directo", en_debate: "debate" };
const TONO_DECISION = { aceptado_directo: "#57f7a7", en_debate: "#ffc457" };
const pct = (x) => (x == null ? "—" : `${Math.round(x * 100)}%`);

export default function Calibracion() {
  const { proyectoId, proyecto, proyectos, elegir } = useProyectoElegido();
  const [params, setParams] = useSearchParams();
  const todos = params.get("alcance") === "todos";
  const { datos: cfg } = useApi(obtenerConfiguracion);
  const [rejilla, setRejilla] = useState({});
  const [borrador, setBorrador] = useState(null);
  const [umbral, setUmbral] = useState(null);

  useEffect(() => {
    if (cfg && !borrador) setBorrador({ desde: cfg.calibracion.desde, hasta: cfg.calibracion.hasta, paso: cfg.calibracion.paso });
  }, [cfg, borrador]);

  const { datos: c, error, cargando } = useApi(
    () => (todos ? calibracionGeneral(rejilla) : proyectoId ? calibracionDeProyecto(proyectoId, rejilla) : Promise.resolve(null)),
    [todos, proyectoId, JSON.stringify(rejilla)],
  );

  // El umbral que se inspecciona empieza en el configurado
  useEffect(() => { if (c) setUmbral((u) => (u != null && c.rejilla.some((f) => f.umbral === u) ? u : c.umbral_configurado)); }, [c]);

  const setAlcance = (v) => setParams((prev) => {
    const p = new URLSearchParams(prev);
    if (v) p.set("alcance", v); else p.delete("alcance");
    return p;
  }, { replace: true });

  const fila = c?.rejilla.find((f) => f.umbral === umbral) ?? c?.rejilla.find((f) => f.configurado);

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <p className="mono text-[10px] text-[var(--bone-faint)]">Análisis de sensibilidad del umbral</p>
        <h1>Calibración.</h1>
        {c && <p className="max-w-3xl text-sm text-[var(--bone-dim)]">{c.nota}</p>}
        <div className="flex flex-wrap items-center gap-3">
          {!todos && <ElegirProyecto proyectoId={proyectoId} proyectos={proyectos} onCambio={elegir} />}
          <label className="mono flex cursor-pointer items-center gap-2 text-[10px] text-[var(--bone-dim)]">
            <input type="checkbox" checked={todos} onChange={(e) => setAlcance(e.target.checked ? "todos" : "")} />
            todos los proyectos juntos (sin los de evaluación)
          </label>
        </div>
      </header>

      {cfg && <Configuracion cfg={cfg} />}

      {borrador && (
        <form
          className="mono flex flex-wrap items-end gap-4 text-[10px] text-[var(--bone-faint)]"
          onSubmit={(e) => { e.preventDefault(); setRejilla({ ...borrador }); }}
        >
          {["desde", "hasta", "paso"].map((k) => (
            <label key={k} className="block">
              <span className="mb-1 block">{k}</span>
              <input
                type="number" step="0.01" min={k === "paso" ? 0.001 : 0} max="1"
                value={borrador[k]}
                onChange={(e) => setBorrador((b) => ({ ...b, [k]: e.target.value }))}
                className="linea w-20 py-1 text-[13px] text-[var(--bone)]"
              />
            </label>
          ))}
          <button className="pill ghost">Recalcular rejilla</button>
        </form>
      )}

      {error && <p className="text-sm text-[var(--danger)]">{error.message}</p>}
      {cargando && !c && <p className="text-sm text-[var(--bone-dim)]">Calculando…</p>}

      {c && c.n_valores === 0 && (
        <p className="text-sm text-[var(--bone-dim)]">
          {todos ? "Ningún proyecto" : proyecto?.nombre ?? "Este proyecto"} tiene todavía similitudes iniciales: aparecen cuando el Clasificador propone dos o más interpretaciones de un término.
        </p>
      )}

      {c && c.n_valores > 0 && (
        <>
          {c.avisos.length > 0 && (
            <ul className="space-y-1 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {c.avisos.map((a) => <li key={a}>{a}</li>)}
            </ul>
          )}

          <section className="space-y-3">
            <div className="flex flex-wrap items-baseline gap-3">
              <h2>Distribución de la similitud inicial</h2>
              <p className="mono text-[9.5px] text-[var(--bone-faint)]">
                {c.n_valores} términos · media {c.distribucion.media?.toFixed(2)} · mediana {c.distribucion.mediana?.toFixed(2)} · rango {c.distribucion.min?.toFixed(2)}–{c.distribucion.max?.toFixed(2)} · {c.modelos_embeddings.join(", ")}
              </p>
            </div>
            <Distribucion c={c} umbral={fila?.umbral} />
          </section>

          <section className="space-y-3">
            <h2>¿Qué habría pasado con otro umbral?</h2>
            <Rejilla c={c} umbral={fila?.umbral} onUmbral={setUmbral} />
            {fila && <Cambios fila={fila} />}
          </section>

          {c.con_ground_truth ? <GroundTruth g={c.con_ground_truth} umbral={fila?.umbral} onUmbral={setUmbral} /> : (
            <p className="text-sm text-[var(--bone-dim)]">
              Sin etiquetas de referencia para {todos ? "estos proyectos" : "este proyecto"}. Una <Link className="underline" to="/evaluacion">evaluación contra el corpus</Link> deja etiquetas y aquí aparece la precisión y la exhaustividad por umbral.
            </p>
          )}

          <Valores valores={c.valores} umbral={fila?.umbral} />
        </>
      )}
    </div>
  );
}

function Configuracion({ cfg }) {
  return (
    <section className="rounded-2xl border border-[var(--line)] p-4 text-sm">
      <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Configuración vigente · {cfg.nota}</p>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        {[
          ["Umbral", cfg.umbral], ["Máx. rondas", cfg.max_rondas], ["Embeddings", cfg.modelo_embeddings], ["Temperatura · semilla", `${cfg.temperatura} · ${cfg.semilla}`],
          ["Extractor", cfg.modelos.extractor], ["Clasificador", cfg.modelos.clasificador], ["Crítico", cfg.modelos.critico], ["Modelador", cfg.modelos.modelador],
        ].map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="mono text-[9px] text-[var(--bone-faint)]">{k}</dt>
            <dd className="truncate font-mono text-[12.5px]" title={String(v)}>{v ?? "—"}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/* Histograma de similitudes con la línea del umbral configurado y la del inspeccionado */
function Distribucion({ c, umbral }) {
  const W = 720, H = 180, M = { l: 28, r: 12, t: 10, b: 26 };
  const bins = c.distribucion.bins;
  if (!bins.length) return null;
  const x0 = Math.min(bins[0].desde, c.umbral_configurado, umbral ?? 1);
  const x1 = Math.max(bins.at(-1).hasta, c.umbral_configurado, umbral ?? 0);
  const maxN = Math.max(1, ...bins.map((b) => b.n));
  const x = (v) => M.l + ((v - x0) / (x1 - x0 || 1)) * (W - M.l - M.r);
  const y = (n) => H - M.b - (n / maxN) * (H - M.t - M.b);
  const ticks = Array.from({ length: 11 }, (_, i) => i / 10).filter((t) => t >= x0 - 1e-9 && t <= x1 + 1e-9);
  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full min-w-[480px]" role="img" aria-label="Histograma de la similitud inicial">
        {bins.map((b) => (
          <rect key={b.desde} x={x(b.desde) + 1} y={y(b.n)} width={Math.max(1, x(b.hasta) - x(b.desde) - 2)} height={H - M.b - y(b.n)} fill="var(--c1)" fillOpacity={b.n ? 0.7 : 0}>
            <title>{`${b.desde.toFixed(2)}–${b.hasta.toFixed(2)}: ${b.n}`}</title>
          </rect>
        ))}
        <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke="rgba(239,233,222,.25)" />
        {ticks.map((t) => (
          <text key={t} x={x(t)} y={H - 8} fontSize="10" textAnchor="middle" fill="rgba(239,233,222,.45)" style={{ fontFamily: "var(--mono)" }}>{t.toFixed(1)}</text>
        ))}
        <text x={4} y={M.t + 8} fontSize="10" fill="rgba(239,233,222,.45)" style={{ fontFamily: "var(--mono)" }}>{maxN}</text>
        <line x1={x(c.umbral_configurado)} x2={x(c.umbral_configurado)} y1={M.t} y2={H - M.b} stroke="#efe9de" strokeDasharray="4 4" />
        <text x={x(c.umbral_configurado) + 4} y={M.t + 10} fontSize="10" fill="#efe9de">configurado {c.umbral_configurado}</text>
        {umbral != null && umbral !== c.umbral_configurado && (
          <>
            <line x1={x(umbral)} x2={x(umbral)} y1={M.t} y2={H - M.b} stroke="#ffc457" />
            <text x={x(umbral) + 4} y={M.t + 24} fontSize="10" fill="#ffc457">{umbral}</text>
          </>
        )}
      </svg>
    </div>
  );
}

function Rejilla({ c, umbral, onUmbral }) {
  const total = c.n_valores;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[460px] text-left text-sm">
        <thead className="mono text-[9px] text-[var(--bone-faint)]">
          <tr>
            <th className="py-1.5 font-normal">Umbral</th>
            <th className="py-1.5 font-normal">Aceptados directo</th>
            <th className="py-1.5 font-normal">Van a debate</th>
            <th className="w-2/5 py-1.5 font-normal" />
            <th className="py-1.5 text-right font-normal">Cambian vs. lo real</th>
          </tr>
        </thead>
        <tbody>
          {c.rejilla.map((f) => (
            <tr
              key={f.umbral}
              onClick={() => onUmbral(f.umbral)}
              className={`cursor-pointer border-t border-[var(--line)] ${f.umbral === umbral ? "bg-white/[0.05]" : "hover:bg-white/[0.03]"}`}
            >
              <td className="py-1.5 font-mono">{f.umbral.toFixed(2)}{f.configurado && <span className="mono ml-2 text-[9px] text-[var(--bone-faint)]">configurado</span>}</td>
              <td className="py-1.5 font-mono">{f.directos}</td>
              <td className="py-1.5 font-mono">{f.debates}</td>
              <td className="py-1.5">
                <div className="flex h-1.5 overflow-hidden rounded-full bg-white/[0.04]">
                  <span style={{ width: `${(100 * f.directos) / total}%`, background: TONO_DECISION.aceptado_directo }} />
                  <span style={{ width: `${(100 * f.debates) / total}%`, background: TONO_DECISION.en_debate }} />
                </div>
              </td>
              <td className="py-1.5 text-right font-mono">{f.cambian.length || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Cambios({ fila }) {
  if (!fila.cambian.length) {
    return <p className="mono text-[10px] text-[var(--bone-faint)]">Con {fila.umbral.toFixed(2)} ningún término cambia de camino respecto de lo que pasó.</p>;
  }
  return (
    <div className="rounded-2xl border border-[var(--line)] p-4">
      <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Con umbral {fila.umbral.toFixed(2)} cambiarían {fila.cambian.length} términos (no predice cómo habría terminado el debate)</p>
      <ul className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
        {fila.cambian.map((x) => (
          <li key={`${x.req_id}-${x.termino}`} className="flex flex-wrap items-baseline gap-2">
            <Link className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--c1)]" to={`/requisitos/${x.req_id}`}>{x.req_id}</Link>
            <span className="italic">«{x.termino}»</span>
            <span className="font-mono text-[11px] text-[var(--bone-dim)]">{x.similitud.toFixed(2)}</span>
            <span className="text-[12px]" style={{ color: TONO_DECISION[x.decision_real] }}>{DECISION[x.decision_real]}</span>
            <span className="text-[var(--bone-faint)]">→</span>
            <span className="text-[12px]" style={{ color: TONO_DECISION[x.decision_con_umbral] }}>{DECISION[x.decision_con_umbral]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function GroundTruth({ g, umbral, onUmbral }) {
  const fila = g.por_umbral.find((f) => f.umbral === umbral) ?? g.por_umbral.find((f) => f.configurado);
  const s = g.separacion;
  return (
    <section className="space-y-4">
      <h2>Contra el ground truth</h2>
      <p className="mono text-[9.5px] text-[var(--bone-faint)]">
        {g.n_etiquetas} etiquetas · {g.n_emparejados} con similitud · {g.n_ambiguos} ambiguos · {g.n_no_ambiguos} no ambiguos
        {g.n_invalidas > 0 && ` · ${g.n_invalidas} etiquetas inválidas`} · fuentes: {g.fuentes.map((f) => `${f.proyecto_id}${f.evaluacion_id ? ` (${f.evaluacion_id})` : ""}`).join(", ")}
      </p>
      <p className={`rounded-lg px-3 py-2 text-sm ${s.separa === false ? "border border-amber-300 bg-amber-50 text-amber-800" : "border border-[var(--line)]"}`}>
        {s.separa == null
          ? "Faltan casos de alguna clase para saber si la similitud separa ambiguos de no ambiguos."
          : s.separa
            ? `La similitud separa los casos: el ambiguo más alto (${s.max_ambiguos?.toFixed(2)}) queda por debajo del no ambiguo más bajo (${s.min_no_ambiguos?.toFixed(2)}).`
            : `Hallazgo: la similitud NO separa los casos. Hay ambiguos con similitud de hasta ${s.max_ambiguos?.toFixed(2)} y no ambiguos desde ${s.min_no_ambiguos?.toFixed(2)}; ningún umbral los acierta todos.`}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead className="mono text-[9px] text-[var(--bone-faint)]">
            <tr>{["Umbral", "VP", "FP", "VN", "FN", "Precisión", "Exhaustividad", "F1"].map((h) => <th key={h} className="py-1.5 font-normal">{h}</th>)}</tr>
          </thead>
          <tbody>
            {g.por_umbral.map((f) => (
              <tr key={f.umbral} onClick={() => onUmbral(f.umbral)} className={`cursor-pointer border-t border-[var(--line)] font-mono ${f.umbral === fila?.umbral ? "bg-white/[0.05]" : "hover:bg-white/[0.03]"}`}>
                <td className="py-1.5">{f.umbral.toFixed(2)}{f.configurado && <span className="mono ml-2 text-[9px] text-[var(--bone-faint)]">conf.</span>}</td>
                <td>{f.vp}</td><td>{f.fp}</td><td>{f.vn}</td><td>{f.fn}</td>
                <td>{pct(f.precision)}</td><td>{pct(f.exhaustividad)}</td><td>{f.f1?.toFixed(2) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[12px] text-[var(--bone-faint)]">Positivo = «va a debate» (similitud &lt; umbral); un término etiquetado ambiguo que se aceptaría directo es un falso negativo.</p>
      {fila?.mal_separados.length > 0 && (
        <div>
          <p className="mono mb-1 text-[9.5px] text-[var(--bone-faint)]">Mal separados con {fila.umbral.toFixed(2)}</p>
          <ul className="space-y-1 text-sm">
            {fila.mal_separados.map((m) => (
              <li key={`${m.req_id}-${m.termino}`} className="flex flex-wrap items-baseline gap-2">
                <Link className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--c1)]" to={`/requisitos/${m.req_id}`}>{m.req_id}</Link>
                <span className="italic">«{m.termino}»</span>
                <span className="font-mono text-[11px]">{m.similitud.toFixed(2)}</span>
                <span className="text-[12px] text-[var(--bone-dim)]">{m.ambiguo ? "ambiguo" : "no ambiguo"} → {DECISION[m.decision_con_umbral]}</span>
                <span className="mono text-[9px] text-amber-600">{m.tipo_error === "falso_positivo" ? "falso positivo" : "falso negativo"}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {(g.etiquetas_sin_similitud.length > 0 || g.valores_sin_etiqueta.length > 0) && (
        <p className="text-[12px] text-[var(--bone-faint)]">
          {g.etiquetas_sin_similitud.length} etiquetas sin similitud (el sistema no generó dos interpretaciones para ese término) · {g.valores_sin_etiqueta.length} similitudes sin etiqueta.
        </p>
      )}
    </section>
  );
}

/* Cada término con su similitud: se ve qué lado del umbral inspeccionado le toca */
function Valores({ valores, umbral }) {
  const [abierto, setAbierto] = useState(false);
  const orden = useMemo(() => [...valores].sort((a, b) => a.similitud - b.similitud), [valores]);
  return (
    <section className="space-y-2">
      <button className="flex flex-wrap items-baseline gap-3 text-left" onClick={() => setAbierto((x) => !x)}>
        <h2>Valores</h2>
        <span className="mono text-[9.5px] text-[var(--bone-faint)]">{valores.length} términos · {abierto ? "ocultar" : "ver todos"}</span>
      </button>
      {abierto && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] text-left text-sm">
            <thead className="mono text-[9px] text-[var(--bone-faint)]">
              <tr>{["Requisito", "Término", "Tipo", "Similitud", "Umbral usado", "Decisión real", "Vía final"].map((h) => <th key={h} className="py-1.5 font-normal">{h}</th>)}</tr>
            </thead>
            <tbody>
              {orden.map((v) => (
                <tr key={`${v.req_id}-${v.termino}`} className="border-t border-[var(--line)]">
                  <td className="py-1.5"><Link className="mono text-[10px] hover:text-[var(--c1)]" to={`/requisitos/${v.req_id}`}>{v.req_id}</Link> <span className="mono text-[9px] text-[var(--bone-faint)]">C{v.ciclo}</span></td>
                  <td className="py-1.5 italic">«{v.termino}»</td>
                  <td className="py-1.5 text-[12px]">{infoTipo(v.tipo_ambiguedad).etiqueta}</td>
                  <td className={`py-1.5 font-mono ${umbral != null && v.similitud < umbral ? "text-amber-600" : ""}`}>{v.similitud.toFixed(3)}</td>
                  <td className="py-1.5 font-mono text-[var(--bone-dim)]">{v.umbral_usado ?? "—"}</td>
                  <td className="py-1.5 text-[12px]" style={{ color: TONO_DECISION[v.decision_real] }}>{DECISION[v.decision_real]}</td>
                  <td className="py-1.5 text-[12px] text-[var(--bone-dim)]">{v.via ? INFO_VIA[v.via]?.etiqueta : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
