import { Fragment, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useApi } from "../hooks/useApi";
import { evaluar, listarCorpus, listarEvaluaciones, obtenerCorpus, obtenerEvaluacion } from "../services/backend";
import { INFO_VIA } from "../constants/estados";
import { tipo as infoTipo } from "../constants/agentes";

/*
 * Evaluación contra el corpus (ADR 0014): el sistema multiagente frente a una
 * línea base de un solo agente, ambos contra el ground truth. Cada corrida crea
 * su propio proyecto de evaluación (LEL aparte) y deja etiquetas para la
 * calibración. Se mide lo que el sistema propone ANTES de la validación humana.
 */
const SONDEO_MS = 2500;
const pct = (x) => (x == null ? "—" : `${Math.round(x * 100)}%`);
const DEBATE_GT = {
  justificado: { texto: "debate justificado", tono: "text-emerald-600" },
  de_mas: { texto: "debate de más", tono: "text-amber-600" },
  faltante: { texto: "faltó debate", tono: "text-red-600" },
  sin_debate_correcto: { texto: "sin debate, correcto", tono: "text-[var(--bone-dim)]" },
};

export default function Evaluacion() {
  const [params, setParams] = useSearchParams();
  const elegida = params.get("e");
  const { datos: corpus, error: errorCorpus } = useApi(listarCorpus);
  const [lista, setLista] = useState(null);
  const [informe, setInforme] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [lanzando, setLanzando] = useState(null);
  const [verCorpus, setVerCorpus] = useState(null);

  const ver = (id) => setParams(id ? { e: id } : {}, { replace: true });

  useEffect(() => {
    listarEvaluaciones().then(setLista).catch((e) => setAviso(e.message));
  }, []);

  const id = elegida ?? lista?.[0]?.evaluacion_id ?? null;

  useEffect(() => {
    if (!id) { setInforme(null); return undefined; }
    let activo = true;
    let t = null;
    const leer = async () => {
      try {
        const r = await obtenerEvaluacion(id);
        if (!activo) return;
        setInforme(r);
        if (r.estado !== "terminada") t = setTimeout(leer, SONDEO_MS);
        else listarEvaluaciones().then((l) => activo && setLista(l)).catch(() => {});
      } catch (e) {
        if (activo) setAviso(e.message);
      }
    };
    leer();
    return () => { activo = false; clearTimeout(t); };
  }, [id]);

  const lanzar = async (nombreCorpus) => {
    setAviso(null);
    setLanzando(nombreCorpus);
    try {
      const { evaluacion_id: nueva } = await evaluar(nombreCorpus);
      setLista(await listarEvaluaciones());
      ver(nueva);
    } catch (e) {
      setAviso(e.message);
    } finally {
      setLanzando(null);
    }
  };

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <p className="mono text-[10px] text-[var(--bone-faint)]">Sistema multiagente frente a un solo agente</p>
        <h1>Evaluación.</h1>
        <p className="max-w-2xl text-sm text-[var(--bone-dim)]">
          Cada corrida procesa el corpus con el sistema completo y con una línea base de un solo agente, y compara ambos con el ground truth. Crea su propio proyecto (con su LEL) y deja etiquetas para la calibración del umbral.
        </p>
        {aviso && <p className="text-sm text-[var(--danger)]">{aviso}</p>}
      </header>

      <section className="space-y-3">
        <h2>Corpus</h2>
        {errorCorpus && <p className="text-sm text-[var(--danger)]">{errorCorpus.message}</p>}
        {corpus && corpus.length === 0 && <p className="text-sm text-[var(--bone-dim)]">No hay corpus en data/corpus/.</p>}
        <ol className="grid gap-3 md:grid-cols-2">
          {(corpus ?? []).map((c) => (
            <li key={c.nombre} className="rounded-2xl border border-[var(--line)] bg-white/[0.02] p-4 text-sm">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="serif text-[24px] leading-tight">{c.nombre}</span>
                {c.ejemplo && <span className="rounded bg-amber-100 px-1.5 text-[11px] text-amber-900">ejemplo, no se reporta</span>}
                {!c.valido && <span className="rounded bg-red-100 px-1.5 text-[11px] text-red-900">inválido</span>}
              </div>
              {c.descripcion && <p className="mt-1 text-[var(--bone-dim)]">{c.descripcion}</p>}
              {c.conteo && (
                <p className="mono mt-2 text-[9.5px] text-[var(--bone-faint)]">
                  {c.conteo.n_requisitos} requisitos · {c.conteo.n_ambiguos} ambiguos · {c.conteo.n_terminos} términos ({Object.entries(c.conteo.por_tipo).filter(([, n]) => n).map(([t, n]) => `${infoTipo(t).etiqueta.toLowerCase()} ${n}`).join(", ")}) · {c.conteo.n_vaguedad} vaguedad · {c.conteo.n_regionales} regionales
                </p>
              )}
              <p className="mono mt-1 text-[9px] text-[var(--bone-faint)]">
                autoría: {c.autoria ?? "—"} · validado por: {c.validado_por ?? "nadie todavía"}
              </p>
              {c.errores.length > 0 && <ul className="mt-2 list-disc pl-5 text-[12px] text-[var(--danger)]">{c.errores.map((e) => <li key={e}>{e}</li>)}</ul>}
              {c.avisos.length > 0 && <ul className="mt-2 list-disc pl-5 text-[12px] text-amber-600">{c.avisos.map((e) => <li key={e}>{e}</li>)}</ul>}
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="pill" disabled={!c.valido || lanzando} onClick={() => lanzar(c.nombre)}>{lanzando === c.nombre ? "Encolando…" : "Evaluar"}</button>
                {c.valido && <button className="pill ghost" onClick={() => setVerCorpus((x) => (x === c.nombre ? null : c.nombre))}>{verCorpus === c.nombre ? "Ocultar" : "Ver ground truth"}</button>}
              </div>
            </li>
          ))}
        </ol>
        {verCorpus && <DetalleCorpus nombre={verCorpus} />}
      </section>

      {lista && lista.length > 0 && (
        <section className="space-y-4">
          <h2>Corridas</h2>
          <div className="flex flex-wrap gap-2">
            {lista.map((e) => (
              <button
                key={e.evaluacion_id}
                onClick={() => ver(e.evaluacion_id)}
                className={`rounded-xl border px-3 py-2 text-left text-sm ${e.evaluacion_id === id ? "border-[var(--c1)] bg-white/[0.04]" : "border-[var(--line)] hover:bg-white/[0.03]"}`}
              >
                <span className="mono flex items-center gap-2 text-[9.5px] text-[var(--bone-faint)]">
                  {e.evaluacion_id} · {e.corpus}{e.ejemplo ? " (ejemplo)" : ""}
                  {e.estado !== "terminada" && <span className="gira" />}
                </span>
                <span className="block">{e.nombre}</span>
                <span className="mono text-[9px] text-[var(--bone-faint)]">
                  {e.estado === "terminada" ? new Date(e.terminado ?? e.creado).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" }) : `sistema ${e.progreso.listos_sistema}/${e.progreso.total} · línea base ${e.progreso.listos_linea_base}/${e.progreso.total}`}
                </span>
              </button>
            ))}
          </div>
          {informe && <Informe r={informe} />}
        </section>
      )}
    </div>
  );
}

function DetalleCorpus({ nombre }) {
  const { datos: d, error } = useApi(() => obtenerCorpus(nombre), [nombre]);
  if (error) return <p className="text-sm text-[var(--danger)]">{error.message}</p>;
  if (!d) return <p className="text-sm text-[var(--bone-dim)]">Cargando el corpus…</p>;
  return (
    <ol className="border-t border-[var(--line)]">
      {d.items.map((it) => (
        <li key={it.id} className="border-b border-[var(--line)] py-3 text-sm">
          <p className="flex flex-wrap items-baseline gap-3">
            <span className="mono w-12 text-[10px] text-[var(--bone-faint)]">{it.id}</span>
            <span className="min-w-0 flex-1 text-[15px]">{it.texto}</span>
            <span className={`mono text-[9.5px] ${it.ground_truth.ambiguo ? "text-amber-600" : "text-[var(--bone-faint)]"}`}>{it.ground_truth.ambiguo ? "ambiguo" : "sin ambigüedad"}</span>
          </p>
          <GroundTruth gt={it.ground_truth} />
        </li>
      ))}
    </ol>
  );
}

function GroundTruth({ gt }) {
  if (!gt.terminos.length && !gt.vaguedad.length && !gt.regionales.length && !gt.notas) return null;
  return (
    <div className="mt-2 space-y-1 pl-[3.75rem] text-[12.5px] text-[var(--bone-dim)]">
      {gt.terminos.map((t) => (
        <p key={t.termino}>
          <span className={`rounded px-1.5 text-[11px] ${infoTipo(t.tipo_ambiguedad).clase}`}>{infoTipo(t.tipo_ambiguedad).etiqueta}</span>{" "}
          <span className="italic">«{t.termino}»</span>: {t.interpretaciones_validas.join(" · ")}
          {t.interpretacion_esperada && <span className="text-[var(--bone-faint)]"> (esperada: {t.interpretacion_esperada})</span>}
        </p>
      ))}
      {gt.vaguedad.length > 0 && <p>vaguedad: {gt.vaguedad.join(", ")}</p>}
      {gt.regionales.length > 0 && <p>regionales: {gt.regionales.join(", ")}</p>}
      {gt.notas && <p className="text-[var(--bone-faint)]">{gt.notas}</p>}
    </div>
  );
}

function Informe({ r }) {
  const s = r.resumen.sistema;
  const b = r.resumen.linea_base;
  const filas = [
    ["Ambigüedad: precisión", s.deteccion_ambiguedad.precision, b.deteccion_ambiguedad.precision, true],
    ["Ambigüedad: exhaustividad", s.deteccion_ambiguedad.exhaustividad, b.deteccion_ambiguedad.exhaustividad, true],
    ["Ambigüedad: F1", s.deteccion_ambiguedad.f1, b.deteccion_ambiguedad.f1, true],
    ["Todo lo marcado: precisión", s.deteccion.precision, b.deteccion.precision],
    ["Todo lo marcado: exhaustividad", s.deteccion.exhaustividad, b.deteccion.exhaustividad],
    ["Todo lo marcado: F1", s.deteccion.f1, b.deteccion.f1],
    ["Requisito ambiguo sí/no: exactitud", s.requisito.exactitud, b.requisito.exactitud],
    ["Tipo de ambigüedad: exactitud", s.tipo.exactitud, b.tipo.exactitud],
  ];
  return (
    <div className="space-y-7">
      {r.avisos.length > 0 && (
        <ul className="space-y-1 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">{r.avisos.map((a) => <li key={a}>{a}</li>)}</ul>
      )}
      <p className="max-w-3xl text-sm text-[var(--bone-dim)]">{r.nota}</p>
      <p className="mono flex flex-wrap gap-x-4 text-[9.5px] text-[var(--bone-faint)]">
        <Link className="hover:text-[var(--bone)]" to={`/proyectos/${r.proyecto_id}`}>proyecto {r.proyecto_id} →</Link>
        <Link className="hover:text-[var(--bone)]" to={`/calibracion?proyecto=${r.proyecto_id}`}>calibración con estas etiquetas →</Link>
        <span>umbral {r.config.similarity_threshold} · {r.config.max_debate_rounds} rondas</span>
        {r.estado !== "terminada" && <span className="flex items-center gap-1"><span className="gira" /> sistema {r.progreso.listos_sistema}/{r.progreso.total} · línea base {r.progreso.listos_linea_base}/{r.progreso.total}</span>}
      </p>

      <section className="space-y-2">
        <h3 className="mono text-[10px] text-[var(--bone-faint)]">Métricas</h3>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="mono text-[9px] text-[var(--bone-faint)]">
              <tr><th className="py-1.5 font-normal" /><th className="w-24 py-1.5 font-normal">Sistema</th><th className="w-24 py-1.5 font-normal">Un agente</th><th className="w-2/5 py-1.5 font-normal" /></tr>
            </thead>
            <tbody>
              {filas.map(([k, a, z, nucleo]) => (
                <tr key={k} className="border-t border-[var(--line)]">
                  <td className={`py-1.5 pr-3 ${nucleo ? "font-medium" : "text-[var(--bone-dim)]"}`}>{k}</td>
                  <td className="py-1.5 font-mono">{pct(a)}</td>
                  <td className="py-1.5 font-mono text-[var(--bone-dim)]">{pct(z)}</td>
                  <td className="py-1.5">
                    <div className="space-y-0.5">
                      <div className="h-1.5 rounded-full bg-[var(--c1)]" style={{ width: `${(a ?? 0) * 100}%` }} />
                      <div className="h-1.5 rounded-full bg-[rgba(239,233,222,.35)]" style={{ width: `${(z ?? 0) * 100}%` }} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mono flex flex-wrap gap-x-4 text-[9.5px] text-[var(--bone-faint)]">
          <span>sistema: VP {s.deteccion_ambiguedad.vp} · FP {s.deteccion_ambiguedad.fp} · FN {s.deteccion_ambiguedad.fn}{s.errores ? ` · ${s.errores} con error` : ""}</span>
          <span>un agente: VP {b.deteccion_ambiguedad.vp} · FP {b.deteccion_ambiguedad.fp} · FN {b.deteccion_ambiguedad.fn}{b.errores ? ` · ${b.errores} con error` : ""}</span>
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-[var(--line)] p-4">
          <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Debates del sistema contra el ground truth</p>
          <dl className="grid grid-cols-2 gap-y-1 text-sm">
            <dt>Activados</dt><dd className="font-mono">{s.debates.activados}</dd>
            <dt>Necesarios</dt><dd className="font-mono">{s.debates.necesarios}</dd>
            <dt className="text-emerald-600">Justificados</dt><dd className="font-mono">{s.debates.justificados}</dd>
            <dt className="text-amber-600">De más</dt><dd className="font-mono">{s.debates.de_mas}</dd>
            <dt className="text-red-600">Faltantes</dt><dd className="font-mono">{s.debates.faltantes}</dd>
          </dl>
        </div>
        <div className="rounded-2xl border border-[var(--line)] p-4">
          <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Cómo se resolvieron los términos (sistema)</p>
          <dl className="grid grid-cols-2 gap-y-1 text-sm">
            {Object.entries(s.vias).map(([v, n]) => (
              <Fragment key={v}>
                <dt className="flex items-center gap-1.5">{INFO_VIA[v] && <span className="punto" style={{ background: INFO_VIA[v].tono }} />}{INFO_VIA[v]?.etiqueta ?? "sin vía"}</dt>
                <dd className="font-mono">{n}</dd>
              </Fragment>
            ))}
          </dl>
        </div>
      </section>

      <section className="space-y-2">
        <h3 className="mono text-[10px] text-[var(--bone-faint)]">Por requisito</h3>
        <ol className="border-t border-[var(--line)]">{r.requisitos.map((f) => <FilaInforme key={f.id_corpus} f={f} />)}</ol>
      </section>
    </div>
  );
}

function FilaInforme({ f }) {
  const [abierto, setAbierto] = useState(false);
  const gt = f.ground_truth;
  const lado = (l, nombre) => (
    <div className="min-w-0">
      <p className="mono text-[9px] text-[var(--bone-faint)]">{nombre}</p>
      {!l.listo ? <p className="text-[12px] text-[var(--bone-faint)]">pendiente…</p> : l.error ? <p className="text-[12px] text-[var(--danger)]">{l.error}</p> : (
        <>
          <p className="text-[12.5px]">
            {l.ambiguo ? "ambiguo" : "sin ambigüedad"}{" "}
            <span className={l.correcto ? "text-emerald-600" : "text-red-600"}>{l.correcto ? "✓" : "✗"}</span>
            {l.debate_gt && <span className={`mono ml-2 text-[9.5px] ${DEBATE_GT[l.debate_gt].tono}`}>{DEBATE_GT[l.debate_gt].texto}</span>}
          </p>
          <p className="text-[12px] text-[var(--bone-dim)]">
            {l.terminos.filter((t) => t.detectado).map((t, i) => (
              <span key={t.termino}>{i ? ", " : ""}<span className={t.clase_gt ? "" : "text-amber-600"} title={t.clase_gt ? `coincide con «${t.emparejado_con}» (${t.criterio})` : "no está en el ground truth"}>{t.termino}</span></span>
            ))}
            {l.faltantes.length > 0 && <span className="text-red-600"> · faltó: {l.faltantes.join(", ")}</span>}
          </p>
        </>
      )}
    </div>
  );
  return (
    <li className="border-b border-[var(--line)] py-3 text-sm">
      <button className="grid w-full gap-x-4 gap-y-2 text-left md:grid-cols-[3rem_1fr_1fr_1fr]" onClick={() => setAbierto((x) => !x)}>
        <span className="mono text-[10px] text-[var(--bone-faint)]">{f.id_corpus}</span>
        <span className="min-w-0">
          <span className="block">{f.texto}</span>
          <span className={`mono text-[9.5px] ${gt.ambiguo ? "text-amber-600" : "text-[var(--bone-faint)]"}`}>
            ground truth: {gt.ambiguo ? gt.terminos.map((t) => t.termino).join(", ") : "sin ambigüedad"}
          </span>
        </span>
        {lado(f.sistema, "Sistema")}
        {lado(f.linea_base, `Un agente${f.linea_base.modelo ? ` · ${f.linea_base.modelo}` : ""}`)}
      </button>
      {abierto && (
        <div className="mt-3 space-y-3 md:pl-16">
          <GroundTruth gt={gt} />
          <TablaTerminos titulo={<>Sistema · <Link className="underline" to={`/requisitos/${f.req_id}`}>{f.req_id}</Link></>} terminos={f.sistema.terminos} />
          <TablaTerminos titulo="Un agente" terminos={f.linea_base.terminos} />
        </div>
      )}
    </li>
  );
}

function TablaTerminos({ titulo, terminos }) {
  if (!terminos.length) return <p className="mono text-[9.5px] text-[var(--bone-faint)]">{titulo}: sin términos</p>;
  return (
    <div className="overflow-x-auto">
      <p className="mono mb-1 text-[9.5px] text-[var(--bone-faint)]">{titulo}</p>
      <table className="w-full min-w-[600px] text-left text-[12.5px]">
        <thead className="mono text-[9px] text-[var(--bone-faint)]">
          <tr>{["Término", "Origen", "Detectado", "Tipo", "Interpretación", "Similitud", "Ground truth"].map((h) => <th key={h} className="py-1 font-normal">{h}</th>)}</tr>
        </thead>
        <tbody>
          {terminos.map((t) => (
            <tr key={t.termino} className="border-t border-[var(--line)] align-top">
              <td className="py-1 pr-2 italic">«{t.termino}»</td>
              <td className="py-1 pr-2 text-[var(--bone-dim)]">{t.origen}</td>
              <td className="py-1 pr-2">{t.detectado ? t.motivo_deteccion : <span className="text-[var(--bone-faint)]">no</span>}</td>
              <td className="py-1 pr-2">{t.tipo_ambiguedad ? infoTipo(t.tipo_ambiguedad).etiqueta : "—"}{t.tipo_correcto === false && <span className="text-red-600"> ✗</span>}</td>
              <td className="py-1 pr-2 text-[var(--bone-dim)]">{t.interpretacion ?? "—"}{t.via && <span className="text-[var(--bone-faint)]"> · {INFO_VIA[t.via]?.etiqueta ?? t.via}</span>}</td>
              <td className="py-1 pr-2 font-mono">{t.similitud?.toFixed(2) ?? "—"}</td>
              <td className="py-1">{t.clase_gt ? `${t.clase_gt}${t.tipo_gt ? ` (${infoTipo(t.tipo_gt).etiqueta.toLowerCase()})` : ""} · ${t.criterio}` : <span className="text-[var(--bone-faint)]">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
