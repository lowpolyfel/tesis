import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { useRequisitoVivo } from "../hooks/useRequisitoVivo";
import { requisitosDeProyecto, validarRequisito } from "../services/backend";
import { ESTADOS as E, INFO_VIA, estaEnProceso } from "../constants/estados";
import { REGLAS, colorInterpretacion, tipo } from "../constants/agentes";
import EstadoBadge from "../components/EstadoBadge";

/*
 * Validación humana (fase 4 de KMoS-SSA), por término.
 *
 * Para cada término con interpretaciones la persona ve cómo se llegó a la
 * propuesta (vía, similitud, rondas, arbitraje) y puede: aprobarla, elegir
 * otra interpretación (incluso una retirada en el debate) o reescribirla.
 * Al aprobar, el Modelador formaliza: entradas del LEL para los términos
 * léxicos, el requisito reescrito y sus metas. Rechazar no formaliza nada.
 */
export default function Validacion() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const volver = params.get("volver");
  const { vista: v, error } = useRequisitoVivo(id);
  const [elecciones, setElecciones] = useState({}); // termino -> { id, editar, significado, parafrasis }
  const [comentario, setComentario] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [aviso, setAviso] = useState(null);
  const [siguiente, setSiguiente] = useState(null);

  const solicitud = v?.solicitud;
  const terminos = useMemo(() => solicitud?.terminos ?? [], [solicitud]);

  // Propuesta preseleccionada en cada término
  useEffect(() => {
    if (!terminos.length) return;
    setElecciones((prev) => {
      const nuevo = { ...prev };
      for (const t of terminos) {
        if (!nuevo[t.termino]) {
          const p = t.propuesta ?? Object.values(t.todas ?? {})[0];
          nuevo[t.termino] = { id: p?.id, editar: false, significado: p?.significado ?? "", parafrasis: p?.parafrasis_del_requisito ?? "" };
        }
      }
      return nuevo;
    });
  }, [terminos]);

  // El siguiente requisito por validar del mismo proyecto
  useEffect(() => {
    if (!v?.proyecto_id) return;
    requisitosDeProyecto(v.proyecto_id)
      .then((l) => setSiguiente(l.find((r) => r.estado === E.PENDIENTE_VALIDACION && r.req_id !== id) ?? null))
      .catch(() => setSiguiente(null));
  }, [v?.proyecto_id, v?.estado, id]);

  if (error) return <p className="text-sm text-rose-600">No pude cargar {id}: {error.message}</p>;
  if (!v) return <p className="text-sm text-slate-500">Cargando {id}…</p>;

  const pendiente = v.estado === E.PENDIENTE_VALIDACION;

  const enviar = async (decision) => {
    setEnviando(true);
    setAviso(null);
    try {
      const editadas = {};
      if (decision === "aprobar") {
        for (const t of terminos) {
          const e = elecciones[t.termino];
          if (!e) continue;
          const base = t.todas?.[e.id];
          if (e.editar) {
            editadas[t.termino] = { id: e.id, significado: e.significado.trim(), parafrasis_del_requisito: e.parafrasis.trim() };
          } else if (base && e.id !== t.propuesta?.id) {
            editadas[t.termino] = base;
          }
        }
      }
      await validarRequisito(id, { decision, interpretacionesEditadas: editadas, comentario });
      setAviso(decision === "aprobar" ? "Aprobado. El Modelador está formalizando…" : "Rechazado.");
    } catch (e) {
      setAviso(`Error: ${e.message}`);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="space-y-6 pb-24">
      <header className="space-y-2">
        <nav className="text-sm text-slate-500">
          {volver ? <Link to={volver} className="hover:underline">Volver al análisis</Link> : <Link to="/historial" className="hover:underline">Historial</Link>}
          {" / "}<Link to={`/requisitos/${id}`} className="hover:underline">{id}</Link> / validación
        </nav>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">Validación</h1>
          <EstadoBadge estado={v.estado} className="text-sm" />
          <span className="text-xs text-slate-500">{v.proyecto_id} · ciclo {v.ciclo}{v.origen?.marca ? ` · ${v.origen.marca}` : ""}{v.origen?.pagina ? ` · p. ${v.origen.pagina}` : ""}</span>
        </div>
        <p className="font-serif text-xl leading-snug">«{v.texto}»</p>
      </header>

      {estaEnProceso(v.estado) && (
        <p className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-700">
          Los agentes siguen trabajando en este requisito ({v.estado.replaceAll("_", " ")}). La validación aparece aquí en cuanto terminen.
        </p>
      )}

      {pendiente && (
        <>
          {!terminos.length && (
            <p className="rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
              No se encontraron términos ambiguos. Al aprobar, el requisito se formaliza sin entradas nuevas en el LEL
              (los unívocos no entran: ADR 0007).
            </p>
          )}
          {terminos.map((t) => (
            <TerminoAValidar key={t.termino} t={t} eleccion={elecciones[t.termino]}
              onCambio={(e) => setElecciones((x) => ({ ...x, [t.termino]: { ...x[t.termino], ...e } }))} />
          ))}
          <Contexto solicitud={solicitud} />
          <section className="sticky bottom-3 z-10 space-y-3 rounded-xl border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur">
            <textarea value={comentario} onChange={(e) => setComentario(e.target.value)} rows={2}
              placeholder="Comentario (opcional): por qué apruebas, eliges o rechazas"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            <div className="flex flex-wrap items-center gap-3">
              <button disabled={enviando} onClick={() => enviar("aprobar")}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50">
                Aprobar y formalizar
              </button>
              <button disabled={enviando} onClick={() => enviar("rechazar")}
                className="rounded-md border border-rose-300 px-4 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50">
                Rechazar
              </button>
              {aviso && <span className="text-sm text-slate-600">{aviso}</span>}
            </div>
          </section>
        </>
      )}

      {!pendiente && !estaEnProceso(v.estado) && <Resultado v={v} />}

      <footer className="flex flex-wrap gap-3 text-sm">
        {siguiente && (
          <button className="rounded-md bg-violet-600 px-3 py-1.5 text-white hover:bg-violet-500"
            onClick={() => navigate(`/requisitos/${siguiente.req_id}/validacion${volver ? `?volver=${encodeURIComponent(volver)}` : ""}`)}>
            Validar el siguiente ({siguiente.req_id})
          </button>
        )}
        <Link to={`/requisitos/${id}`} className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50">Ver la traza completa</Link>
        <Link to={`/proyectos/${v.proyecto_id}`} className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50">Ir al proyecto</Link>
      </footer>
    </div>
  );
}

function TerminoAValidar({ t, eleccion, onCambio }) {
  const info = tipo(t.tipo_ambiguedad);
  const retiradas = new Map((t.retiradas ?? []).map((r) => [r.interpretacion_id, r]));
  const todas = Object.values(t.todas ?? {}).sort((a, b) => a.id.localeCompare(b.id, "es", { numeric: true }));
  const via = INFO_VIA[t.via];
  if (!eleccion) return null;
  const elegir = (interp) => onCambio({ id: interp.id, significado: interp.significado, parafrasis: interp.parafrasis_del_requisito });

  return (
    <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">«{t.termino}»</h2>
        <span className={`rounded px-2 py-0.5 text-xs ${info.clase}`} title={info.descripcion}>{info.etiqueta}</span>
        {t.origen && t.origen !== "extractor" && <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">detectado por: {t.origen}</span>}
        <span className="ml-auto flex items-center gap-2 text-xs text-slate-600">
          {via && <span className="punto" style={{ background: via.tono }} />}
          {via?.etiqueta ?? t.decision}
          {t.similitud != null && <> · similitud {t.similitud.toFixed(2)} (umbral {t.umbral})</>}
          {t.rondas > 0 && <> · {t.rondas} ronda{t.rondas > 1 ? "s" : ""}</>}
        </span>
      </header>
      {t.detalle && <p className="text-xs text-slate-500">{t.detalle}</p>}

      {t.justificacion?.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">El Crítico arbitró por {t.propuesta?.id}:</p>
          <ul className="mt-1 space-y-0.5">
            {t.justificacion.map((j) => <li key={j.regla}><b>{j.regla}</b> {REGLAS[j.regla]?.nombre}: {j.argumento}</li>)}
          </ul>
        </div>
      )}

      <fieldset className="space-y-2">
        {todas.map((i) => {
          const c = colorInterpretacion(i.id);
          const ret = retiradas.get(i.id);
          const marcada = eleccion.id === i.id && !eleccion.editar;
          return (
            <label key={i.id} className={`flex cursor-pointer gap-3 rounded-lg border-l-4 p-3 ${c.clase} ${marcada ? "ring-2 ring-slate-900" : "opacity-90"}`}>
              <input type="radio" name={`t-${t.termino}`} checked={marcada} onChange={() => { elegir(i); onCambio({ editar: false }); }} className="mt-1" />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2 text-sm">
                  <b>{i.id}</b> {i.significado}
                  {t.propuesta?.id === i.id && <span className="rounded bg-slate-900 px-1.5 py-0.5 text-[10px] text-white">propuesta</span>}
                  {ret && <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] text-rose-800" title={ret.motivo}>retirada en la ronda {ret.ronda}</span>}
                </span>
                <span className="mt-1 block text-sm text-slate-700">{i.parafrasis_del_requisito}</span>
              </span>
            </label>
          );
        })}
        <label className={`flex cursor-pointer gap-3 rounded-lg border border-dashed border-slate-300 p-3 ${eleccion.editar ? "ring-2 ring-slate-900" : ""}`}>
          <input type="radio" name={`t-${t.termino}`} checked={eleccion.editar} onChange={() => onCambio({ editar: true })} className="mt-1" />
          <span className="min-w-0 flex-1 text-sm">
            Reescribir la interpretación elegida ({eleccion.id})
            {eleccion.editar && (
              <span className="mt-2 block space-y-2">
                <input value={eleccion.significado} onChange={(e) => onCambio({ significado: e.target.value })}
                  placeholder="significado" className="w-full rounded-md border border-slate-300 px-2 py-1" />
                <textarea value={eleccion.parafrasis} onChange={(e) => onCambio({ parafrasis: e.target.value })} rows={2}
                  placeholder="el requisito reescrito con ese significado" className="w-full rounded-md border border-slate-300 px-2 py-1" />
              </span>
            )}
          </span>
        </label>
      </fieldset>
    </section>
  );
}

function Contexto({ solicitud }) {
  if (!solicitud) return null;
  const bloques = [
    solicitud.vaguedad?.length && { titulo: "Vaguedad (no se debate)", texto: `${solicitud.vaguedad.join(", ")}: límite impreciso. Considera pedir una métrica; el Modelador la tratará como meta blanda.`, clase: "bg-violet-50 text-violet-900" },
    solicitud.estructuras?.length && { titulo: "Estructuras detectadas", texto: solicitud.estructuras.map((e) => `«${e.termino}» (${e.decision_filtro}${e.detalle ? `: ${e.detalle}` : ""})`).join(" · "), clase: "bg-indigo-50 text-indigo-900" },
    solicitud.univocos?.length && { titulo: "Unívocos", texto: `${solicitud.univocos.join(", ")}: una sola interpretación razonable; quedan en la traza y no entran al LEL.`, clase: "bg-slate-50 text-slate-700" },
    solicitud.resueltos_por_lel?.length && { titulo: "Resueltos por el LEL", texto: `${solicitud.resueltos_por_lel.join(", ")}: ya tienen noción validada en el proyecto.`, clase: "bg-emerald-50 text-emerald-900" },
  ].filter(Boolean);
  if (!bloques.length) return null;
  return (
    <section className="grid gap-3 md:grid-cols-2">
      {bloques.map((b) => (
        <div key={b.titulo} className={`rounded-lg p-3 text-sm ${b.clase}`}>
          <p className="font-medium">{b.titulo}</p>
          <p className="mt-1">{b.texto}</p>
        </div>
      ))}
    </section>
  );
}

function Resultado({ v }) {
  const f = v.formalizacion;
  const val = v.validacion;
  return (
    <section className="space-y-4">
      {val && (
        <p className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-700">
          {val.decision === "aprobar" ? "Aprobado" : "Rechazado"}
          {val.terminos?.some((t) => t.cambio !== "ninguno") && ` con cambios: ${val.terminos.filter((t) => t.cambio !== "ninguno").map((t) => `«${t.termino}» (${t.cambio})`).join(", ")}`}
          {val.comentario && <> · «{val.comentario}»</>}
        </p>
      )}
      {v.estado === E.VALIDADO && <p className="text-sm text-slate-600">El Modelador está formalizando…</p>}
      {f && (
        <div className="space-y-3 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-emerald-800">Formalizado</p>
          <p className="font-serif text-lg">«{f.requisito_reescrito}»</p>
          {f.entradas_lel?.length > 0 && <p className="text-sm">Entradas nuevas del LEL: {f.entradas_lel.join(", ")}</p>}
          {f.metas?.length > 0 && (
            <ul className="space-y-1 text-sm">
              {f.metas.map((m) => (
                <li key={m.id}><b>{m.id}</b> <span className="text-slate-500">{m.tipo.replace("_", " ")}</span> · {m.enunciado}{m.actor ? ` · ${m.actor}` : ""}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
