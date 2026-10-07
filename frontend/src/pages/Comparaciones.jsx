import { Fragment, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { compararRequisitos, comparacionesDeProyecto, obtenerComparacion } from "../services/backend";
import ElegirProyecto, { useProyectoElegido } from "../components/ElegirProyecto";

/*
 * Comparación entre requisitos de un proyecto. MÓDULO EXPLORATORIO (ADR 0012):
 * amplía el alcance de CONTEXTO §6 y está pendiente de revisar con la asesora.
 * No toca el grafo, las trazas ni el LEL; se corre a pedido y pasa por la cola.
 *   - contradicción y redundancia: juicio de un LLM por par candidato, con citas
 *     que el código verifica contra el texto;
 *   - casi duplicado: coseno de embeddings sobre el umbral (determinista);
 *   - inconsistencia de vocabulario: mismo término validado o mismo símbolo del
 *     LEL con significados distintos (determinista).
 */
const SONDEO_MS = 2000;
const EN_CURSO = ["en_cola", "en_proceso"];

const HALLAZGO = {
  contradiccion: { etiqueta: "Contradicción", clase: "border-red-300 bg-red-50", texto: "text-red-700", tono: "#f87171" },
  casi_duplicado: { etiqueta: "Casi duplicado", clase: "border-amber-300 bg-amber-50", texto: "text-amber-700", tono: "#fbbf24" },
  redundancia: { etiqueta: "Redundancia", clase: "border-sky-300 bg-sky-50", texto: "text-sky-700", tono: "#38bdf8" },
  inconsistencia_vocabulario: { etiqueta: "Inconsistencia de vocabulario", clase: "border-fuchsia-300 bg-fuchsia-50", texto: "text-fuchsia-700", tono: "#e879f9" },
};
const ORDEN_HALLAZGOS = ["contradiccion", "inconsistencia_vocabulario", "casi_duplicado", "redundancia"];
const FUENTE = { llm: "juicio del LLM", embeddings: "coseno de embeddings", lel: "LEL del proyecto", validacion: "significados validados" };
const RELACION = { contradiccion: "contradicción", redundancia: "redundancia", complementaria: "complementaria", independiente: "independiente" };
const MOTIVO = { similitud: "similitud ≥ umbral", simbolo_lel: "comparten símbolo del LEL", lema: "comparten lema" };
const ESTADO = { en_cola: "en cola", en_proceso: "comparando", terminada: "terminada", error: "error" };

export default function Comparaciones() {
  const { proyectoId, proyecto, proyectos, elegir } = useProyectoElegido();
  const [params, setParams] = useSearchParams();
  const elegida = params.get("c");
  const [lista, setLista] = useState(null);
  const [actual, setActual] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [pidiendo, setPidiendo] = useState(false);

  const verComparacion = (id) => setParams((prev) => {
    const p = new URLSearchParams(prev);
    if (id) p.set("c", id); else p.delete("c");
    return p;
  }, { replace: true });

  // Listado del proyecto
  useEffect(() => {
    if (!proyectoId) return undefined;
    let activo = true;
    setLista(null);
    comparacionesDeProyecto(proyectoId)
      .then((l) => { if (activo) setLista(l); })
      .catch((e) => activo && setAviso(e.message));
    return () => { activo = false; };
  }, [proyectoId]);

  // Sin elegida: la más reciente
  const id = elegida ?? lista?.[0]?.comparacion_id ?? null;

  // Detalle, sondeado mientras está en curso
  useEffect(() => {
    if (!id) { setActual(null); return undefined; }
    let activo = true;
    let t = null;
    const leer = async () => {
      try {
        const c = await obtenerComparacion(id);
        if (!activo) return;
        setActual(c);
        if (EN_CURSO.includes(c.estado)) t = setTimeout(leer, SONDEO_MS);
        else if (proyectoId) comparacionesDeProyecto(proyectoId).then((l) => activo && setLista(l)).catch(() => {});
      } catch (e) {
        if (activo) setAviso(e.message);
      }
    };
    leer();
    return () => { activo = false; clearTimeout(t); };
  }, [id, proyectoId]);

  const comparar = async () => {
    setAviso(null);
    setPidiendo(true);
    try {
      const { comparacion_id: nueva } = await compararRequisitos(proyectoId);
      setLista(await comparacionesDeProyecto(proyectoId));
      verComparacion(nueva);
    } catch (e) {
      setAviso(e.message);
    } finally {
      setPidiendo(false);
    }
  };

  const enCurso = lista?.some((c) => EN_CURSO.includes(c.estado));

  return (
    <div className="space-y-7">
      <header className="space-y-3">
        <p className="mono text-[10px] text-[var(--bone-faint)]">Entre requisitos de un mismo proyecto</p>
        <h1>Comparaciones.</h1>
        <p className="max-w-2xl rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Módulo exploratorio (ADR 0012). Amplía el alcance de la tesis, que deja fuera la contradicción entre requisitos (CONTEXTO §6), y está pendiente de revisión con la asesora, la Dra. Karla Olmos Sánchez. No modifica el debate, las trazas ni el LEL.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <ElegirProyecto proyectoId={proyectoId} proyectos={proyectos} onCambio={(p) => { verComparacion(null); elegir(p); }} />
          <button className="pill" disabled={!proyectoId || pidiendo || enCurso} onClick={comparar}>
            {enCurso ? "Comparando…" : pidiendo ? "Encolando…" : "Comparar los requisitos"}
          </button>
          {proyectoId && <Link className="pill ghost" to={`/ambiguedades?proyecto=${proyectoId}`}>Ambigüedades</Link>}
        </div>
        {aviso && <p className="text-sm text-[var(--danger)]">{aviso}</p>}
      </header>

      {lista && lista.length === 0 && (
        <p className="text-sm text-[var(--bone-dim)]">
          {proyecto?.nombre ?? "Este proyecto"} aún no tiene comparaciones. Hacen falta al menos dos requisitos que no estén en error ni rechazados.
        </p>
      )}

      {lista && lista.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
          <ol className="space-y-2">
            {lista.map((c) => (
              <li key={c.comparacion_id}>
                <button
                  onClick={() => verComparacion(c.comparacion_id)}
                  className={`w-full rounded-xl border p-3 text-left text-sm ${c.comparacion_id === id ? "border-[var(--c1)] bg-white/[0.04]" : "border-[var(--line)] hover:bg-white/[0.03]"}`}
                >
                  <span className="mono flex items-center gap-2 text-[9.5px] text-[var(--bone-faint)]">
                    {c.comparacion_id} · {new Date(c.creado).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" })}
                    {EN_CURSO.includes(c.estado) && <span className="gira" />}
                  </span>
                  <span className="mt-1 block">{c.n_requisitos} requisitos · {c.pares_evaluados} pares evaluados</span>
                  <span className="mono mt-1 flex flex-wrap gap-x-3 text-[9.5px] text-[var(--bone-dim)]">
                    {c.estado !== "terminada" && <span>{ESTADO[c.estado]}</span>}
                    {ORDEN_HALLAZGOS.filter((t) => c.hallazgos_por_tipo[t]).map((t) => (
                      <span key={t} className="flex items-center gap-1"><span className="punto" style={{ background: HALLAZGO[t].tono }} />{c.hallazgos_por_tipo[t]} {HALLAZGO[t].etiqueta.toLowerCase()}</span>
                    ))}
                    {c.estado === "terminada" && !Object.values(c.hallazgos_por_tipo).some(Boolean) && <span>sin hallazgos</span>}
                  </span>
                </button>
              </li>
            ))}
          </ol>
          {actual ? <Detalle c={actual} /> : <p className="text-sm text-[var(--bone-dim)]">Cargando la comparación…</p>}
        </div>
      )}
    </div>
  );
}

function Detalle({ c }) {
  const textos = useMemo(() => Object.fromEntries(c.requisitos.map((r) => [r.req_id, r])), [c]);
  const [par, setPar] = useState(null);

  if (EN_CURSO.includes(c.estado)) {
    const pct = c.avance.total ? Math.round((100 * c.avance.hechos) / c.avance.total) : 0;
    return (
      <section className="space-y-3 rounded-2xl border border-[var(--line)] p-5">
        <p className="flex items-center gap-2"><span className="gira" /> {c.estado === "en_cola" ? "Esperando turno en la cola…" : `El comparador revisa los pares: ${c.avance.hechos} de ${c.avance.total}`}</p>
        <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]"><div className="h-full bg-[var(--c1)] transition-all" style={{ width: `${pct}%` }} /></div>
      </section>
    );
  }
  if (c.estado === "error") {
    return <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">La comparación falló: {c.error?.excepcion} — {c.error?.mensaje}</p>;
  }

  const porTipo = ORDEN_HALLAZGOS.map((t) => [t, c.hallazgos.filter((h) => h.tipo === t)]).filter(([, l]) => l.length);
  const parElegido = par ? c.relaciones_por_par.find((r) => r.par === par) : null;

  return (
    <div className="min-w-0 space-y-7">
      <section className="space-y-2">
        <p className="mono flex flex-wrap gap-x-4 gap-y-1 text-[9.5px] text-[var(--bone-faint)]">
          <span>{c.requisitos.length} requisitos</span>
          <span>{c.pares_totales} pares posibles</span>
          <span>{c.pares_candidatos} candidatos</span>
          <span>{c.pares_evaluados} evaluados por el LLM</span>
          {c.pares_fuera_por_limite > 0 && <span className="text-amber-600">{c.pares_fuera_por_limite} fuera por el límite</span>}
          {c.pares_con_error > 0 && <span className="text-[var(--danger)]">{c.pares_con_error} con error</span>}
        </p>
        <p className="mono flex flex-wrap gap-x-4 gap-y-1 text-[9px] text-[var(--bone-faint)]">
          <span>relación ≥ {c.config.umbral_relacion}</span>
          <span>duplicado ≥ {c.config.umbral_duplicado}</span>
          <span>máx. {c.config.max_pares} pares</span>
          <span>{c.config.modelo ?? "sin modelo"} · {c.config.prompt_version}</span>
          <span>embeddings {c.config.modelo_embeddings ?? "—"}</span>
        </p>
      </section>

      <section className="space-y-4">
        <h2>Hallazgos</h2>
        {porTipo.length === 0 && <p className="text-sm text-[var(--bone-dim)]">Ningún hallazgo entre los pares revisados.</p>}
        {porTipo.map(([t, l]) => (
          <div key={t} className="space-y-3">
            <p className={`mono text-[10px] ${HALLAZGO[t].texto}`}>{HALLAZGO[t].etiqueta} · {l.length}</p>
            <ol className="space-y-3">{l.map((h) => <Hallazgo key={h.id} h={h} textos={textos} />)}</ol>
          </div>
        ))}
      </section>

      <section className="space-y-3">
        <h2>Similitud entre requisitos</h2>
        <p className="max-w-2xl text-sm text-[var(--bone-dim)]">
          Coseno entre los embeddings del texto base de cada requisito (reescrito si ya se formalizó). El borde marca los pares que revisó el LLM. Toca una celda para ver ese par.
        </p>
        <Matriz c={c} onPar={setPar} elegido={par} />
        {parElegido && <ParElegido r={parElegido} textos={textos} />}
      </section>

      <RelacionesPorPar c={c} />

      {(c.excluidos.length > 0 || c.fuera_por_limite.length > 0) && (
        <section className="grid gap-6 md:grid-cols-2">
          {c.excluidos.length > 0 && (
            <div>
              <h3 className="mono mb-2 text-[10px] text-[var(--bone-faint)]">Requisitos excluidos</h3>
              <ul className="space-y-1 text-sm text-[var(--bone-dim)]">
                {c.excluidos.map((x) => (
                  <li key={x.req_id}><Link className="mono text-[10px] hover:text-[var(--c1)]" to={`/requisitos/${x.req_id}`}>{x.req_id}</Link> {x.motivo}{x.detalle ? ` (${x.detalle})` : ""}</li>
                ))}
              </ul>
            </div>
          )}
          {c.fuera_por_limite.length > 0 && (
            <div>
              <h3 className="mono mb-2 text-[10px] text-[var(--bone-faint)]">Pares candidatos que no revisó el LLM (límite)</h3>
              <ul className="mono space-y-1 text-[10px] text-[var(--bone-dim)]">
                {c.fuera_por_limite.map((x) => <li key={x.par}>{x.par} · {x.similitud.toFixed(2)} · {x.motivos.map((m) => MOTIVO[m] ?? m).join(", ")}</li>)}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function Hallazgo({ h, textos }) {
  const info = HALLAZGO[h.tipo];
  return (
    <li className={`rounded-2xl border p-4 ${info.clase}`}>
      <div className="mono flex flex-wrap items-center gap-x-3 gap-y-1 text-[9.5px] text-[var(--bone-dim)]">
        <span>{h.id}</span>
        <span>{FUENTE[h.fuente] ?? h.fuente}{h.modelo ? ` · ${h.modelo}` : ""}</span>
        {h.similitud != null && <span>coseno {h.similitud.toFixed(2)}</span>}
        {h.terminos.length > 0 && <span>términos: {h.terminos.join(", ")}</span>}
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {h.requisitos.map((rid) => {
          const ev = h.evidencia.find((e) => e.req_id === rid);
          return (
            <div key={rid} className="rounded-xl bg-white/[0.03] p-3 text-sm">
              <p className="mono text-[9.5px] text-[var(--bone-faint)]">
                <Link className="hover:text-[var(--c1)]" to={`/requisitos/${rid}`}>{rid}</Link>
                {textos[rid] && ` · texto ${textos[rid].base}`}
              </p>
              <p className="mt-1 leading-relaxed"><Resaltar texto={textos[rid]?.texto ?? ""} cita={ev?.verificada ? ev.cita : null} /></p>
              {ev && !ev.verificada && (
                <p className="mt-2 text-[12px] text-[var(--danger)]">La cita del LLM no aparece literal en el requisito: «{ev.cita}»</p>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-sm">{h.explicacion}</p>
    </li>
  );
}

/* Subraya la cita (si se verificó) dentro del texto, sin mayúsculas ni acentos */
function Resaltar({ texto, cita }) {
  if (!cita) return texto;
  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const i = norm(texto).indexOf(norm(cita));
  if (i < 0) return texto;
  return <>{texto.slice(0, i)}<mark className="rounded bg-[var(--c1)]/25 px-0.5 text-inherit">{texto.slice(i, i + cita.length)}</mark>{texto.slice(i + cita.length)}</>;
}

function Matriz({ c, onPar, elegido }) {
  const ids = c.requisitos.map((r) => r.req_id);
  const evaluados = new Set(c.relaciones_por_par.map((r) => r.par));
  // el hallazgo más grave de cada par, en las dos orientaciones de la clave
  const conHallazgo = new Map();
  for (const t of [...ORDEN_HALLAZGOS].reverse()) {
    for (const h of c.hallazgos.filter((x) => x.tipo === t)) {
      const [a, b] = h.requisitos;
      conHallazgo.set(`${a}-${b}`, t).set(`${b}-${a}`, t);
    }
  }
  const valor = (a, b) => c.matriz_similitud[`${a}-${b}`] ?? c.matriz_similitud[`${b}-${a}`];
  const clave = (a, b) => (c.matriz_similitud[`${a}-${b}`] !== undefined ? `${a}-${b}` : `${b}-${a}`);
  if (ids.length < 2) return null;
  const celda = ids.length > 14 ? 22 : 34;
  return (
    <div className="overflow-x-auto">
      <div className="inline-grid gap-px text-center" style={{ gridTemplateColumns: `48px repeat(${ids.length}, ${celda}px)` }}>
        <span />
        {ids.map((b) => <span key={b} className="mono pb-1 text-[8.5px] text-[var(--bone-faint)]">{b.replace(/^R0?/, "")}</span>)}
        {ids.map((a, i) => (
          <Fragment key={a}>
            <span className="mono pr-2 text-right text-[9px] text-[var(--bone-faint)]" style={{ lineHeight: `${celda}px` }}>{a}</span>
            {ids.map((b, j) => {
              if (i === j) return <span key={b} className="bg-white/[0.02]" style={{ height: celda }} />;
              const x = valor(a, b);
              const k = clave(a, b);
              const tipo = conHallazgo.get(k);
              return (
                <button
                  key={b}
                  title={`${a} · ${b}: ${x?.toFixed(3) ?? "—"}${tipo ? ` · ${HALLAZGO[tipo].etiqueta}` : ""}`}
                  onClick={() => onPar(evaluados.has(k) ? k : null)}
                  className="relative"
                  style={{
                    height: celda,
                    background: x == null ? "transparent" : `rgba(116,130,255,${Math.max(0.04, Math.min(1, (x - 0.2) / 0.8))})`,
                    outline: k === elegido ? "2px solid var(--bone)" : evaluados.has(k) ? "1px solid rgba(239,233,222,.55)" : "none",
                    outlineOffset: -1,
                  }}
                >
                  {tipo && <span className="absolute inset-0 m-auto h-2 w-2 rounded-full" style={{ background: HALLAZGO[tipo].tono }} />}
                </button>
              );
            })}
          </Fragment>
        ))}
      </div>
      <p className="mono mt-2 flex flex-wrap gap-x-4 text-[9px] text-[var(--bone-faint)]">
        {ORDEN_HALLAZGOS.map((t) => <span key={t} className="flex items-center gap-1"><span className="punto" style={{ background: HALLAZGO[t].tono }} />{HALLAZGO[t].etiqueta.toLowerCase()}</span>)}
      </p>
    </div>
  );
}

function ParElegido({ r, textos }) {
  return (
    <div className="rounded-2xl border border-[var(--line)] p-4 text-sm">
      <p className="mono text-[9.5px] text-[var(--bone-faint)]">{r.par} · coseno {r.similitud.toFixed(3)} · {r.motivos.map((m) => MOTIVO[m] ?? m).join(", ")}{r.compartidos.length ? ` · comparten: ${r.compartidos.join(", ")}` : ""}</p>
      <div className="mt-2 grid gap-3 md:grid-cols-2">
        {r.requisitos.map((rid) => <p key={rid}><span className="mono text-[9.5px] text-[var(--bone-faint)]">{rid} </span>{textos[rid]?.texto}</p>)}
      </div>
      {r.relacion
        ? <p className="mt-2"><span className="font-medium">{RELACION[r.relacion]}</span>{r.explicacion ? ` — ${r.explicacion}` : ""}</p>
        : <p className="mt-2 text-[var(--danger)]">El comparador falló: {r.error?.excepcion} — {r.error?.mensaje}</p>}
    </div>
  );
}

function RelacionesPorPar({ c }) {
  const [abierto, setAbierto] = useState(false);
  if (!c.relaciones_por_par.length) return null;
  const conteo = c.relaciones_por_par.reduce((m, r) => ({ ...m, [r.relacion ?? "error"]: (m[r.relacion ?? "error"] ?? 0) + 1 }), {});
  return (
    <section className="space-y-2">
      <button className="flex flex-wrap items-baseline gap-3 text-left" onClick={() => setAbierto((x) => !x)}>
        <h2>Juicio por par</h2>
        <span className="mono text-[9.5px] text-[var(--bone-faint)]">
          {Object.entries(conteo).map(([k, n]) => `${RELACION[k] ?? k} ${n}`).join(" · ")} · {abierto ? "ocultar" : "ver todos"}
        </span>
      </button>
      {abierto && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] text-left text-sm">
            <thead className="mono text-[9px] text-[var(--bone-faint)]">
              <tr><th className="py-1.5 font-normal">Par</th><th className="py-1.5 font-normal">Coseno</th><th className="py-1.5 font-normal">Por qué se revisó</th><th className="py-1.5 font-normal">Relación</th><th className="py-1.5 font-normal">Explicación</th></tr>
            </thead>
            <tbody>
              {c.relaciones_por_par.map((r) => (
                <tr key={r.par} className="border-t border-[var(--line)] align-top">
                  <td className="mono py-2 pr-3 text-[10px]">{r.par}</td>
                  <td className="mono py-2 pr-3 text-[10px]">{r.similitud.toFixed(2)}</td>
                  <td className="py-2 pr-3 text-[12px] text-[var(--bone-dim)]">{r.motivos.map((m) => MOTIVO[m] ?? m).join(", ")}{r.compartidos.length ? `: ${r.compartidos.join(", ")}` : ""}</td>
                  <td className="py-2 pr-3">{r.relacion ? RELACION[r.relacion] : <span className="text-[var(--danger)]">error</span>}</td>
                  <td className="py-2 text-[12px] text-[var(--bone-dim)]">{r.explicacion ?? r.error?.mensaje}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
