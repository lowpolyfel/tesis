import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { useOrb } from "../components/orb/useOrb";
import { useRequisitoVivo } from "../hooks/useRequisitoVivo";
import { reprocesarRequisito } from "../services/backend";
import { ESTADOS as E, INFO_VIA } from "../constants/estados";
import { TIPOS } from "../constants/agentes";
import EstadoBadge from "../components/EstadoBadge";
import TextoMarcado, { TONO_AMBIGUEDAD } from "../components/TextoMarcado";
import RutaEstados from "../components/traza/RutaEstados";
import TerminoTraza from "../components/traza/TerminoTraza";
import Bitacora from "../components/traza/Bitacora";

/*
 * Traza completa de un requisito (la figura de la tesis, CONTEXTO §11),
 * organizada por las fases de KMoS-SSA. Todo sale de la vista por término del
 * backend (GET /requisitos/{id}) y se actualiza sola mientras los agentes
 * trabajan. Con ?figura=1 se muestra clara y a ancho fijo para capturas.
 */
const CATEGORIAS = [["sujeto", "Sujetos"], ["verbo", "Verbos"], ["objeto", "Objetos"], ["estado", "Estados"]];
const DECISION = {
  resuelto_por_lel: "resuelto por el LEL", vaguedad: "vaguedad (no se debate)", regional: "regional → Clasificador",
  alcance: "estructura de alcance → Clasificador", anafora: "anáfora → Clasificador", candidato: "candidato → Clasificador",
};
const hora = (iso) => new Date(iso).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "medium" });

function Fase({ n, titulo, quien, children, vacia }) {
  return (
    <section className="space-y-3">
      <header className="flex flex-wrap items-baseline gap-3 border-b border-slate-200 pb-1">
        <span className="font-mono text-xs text-slate-400">{n}</span>
        <h2 className="text-sm font-semibold uppercase tracking-wide">{titulo}</h2>
        <span className="text-xs text-slate-500">{quien}</span>
      </header>
      {vacia ? <p className="text-sm text-slate-500">{vacia}</p> : children}
    </section>
  );
}

export default function DetalleRequisito() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const figura = params.get("figura") === "1";
  const navigate = useNavigate();
  const orb = useOrb();
  const { vista: v, error } = useRequisitoVivo(id);
  const [aviso, setAviso] = useState(null);

  // La esfera toma el tono de cómo se resolvió (o piensa mientras los agentes trabajan)
  useEffect(() => {
    if (!v) return;
    const tono = v.estado === E.ERROR ? "error" : v.en_proceso ? "thinking"
      : v.resumen.via === "arbitraje" ? "critico" : v.resumen.via === "consenso" ? "clasificador" : v.resumen.via ? "modelador" : "idle";
    orb.setMood(tono);
    orb.update("core", { sub: v.req_id, active: v.en_proceso });
  }, [orb, v]);
  useEffect(() => () => { orb.setMood("idle"); orb.update("core", { active: false, sub: null }); }, [orb]);

  if (error) return <p className="text-sm text-rose-600">No pude cargar {id}: {error.message}</p>;
  if (!v) return <p className="text-sm text-slate-500">Cargando {id}…</p>;

  const ambiguos = v.terminos.filter((t) => !t.univoco);
  const univocos = v.terminos.filter((t) => t.univoco);
  const tiposPresentes = [...new Set(v.marcados.map((m) => m.tipo).filter(Boolean))];
  const via = v.resumen.via ? INFO_VIA[v.resumen.via] : null;

  const reprocesar = async () => {
    try {
      const r = await reprocesarRequisito(v);
      navigate(`/analisis?proyecto=${r.proyecto_id}&ids=${r.req_ids.join(",")}`);
    } catch (e) {
      setAviso(e.message);
    }
  };

  return (
    <div className="space-y-8 pb-16">
      {/* ---------------------------------------------------------------- encabezado */}
      <header className="space-y-3">
        {!figura && (
          <nav className="text-sm text-slate-500">
            <Link to={`/proyectos/${v.proyecto_id}`} className="hover:underline">{v.proyecto_id}</Link> / ciclo {v.ciclo} / {v.req_id}
          </nav>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{v.req_id}</h1>
          <EstadoBadge estado={v.estado} className="text-sm" />
          <span className="text-xs text-slate-500">
            {v.origen?.archivo && <>{v.origen.archivo}{v.origen.pagina ? `, p. ${v.origen.pagina}` : ""}{v.origen.marca ? ` · ${v.origen.marca}` : ""} · </>}
            creado {hora(v.creado)}
            {v.origen?.reproceso_de && <> · reprocesa <Link className="underline" to={`/requisitos/${v.origen.reproceso_de}`}>{v.origen.reproceso_de}</Link></>}
          </span>
          {!figura && (
            <span className="ml-auto flex flex-wrap gap-2 text-sm">
              {v.estado === E.PENDIENTE_VALIDACION && (
                <Link to={`/requisitos/${id}/validacion`} className="rounded-md bg-violet-600 px-3 py-1.5 text-sobre hover:bg-violet-500">Validar</Link>
              )}
              <Link to={`/analisis?proyecto=${v.proyecto_id}&ids=${id}&escena=1`} className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50">Ver en la escena</Link>
              {[E.RECHAZADO, E.ERROR].includes(v.estado) && (
                <button onClick={reprocesar} className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50">Reprocesar</button>
              )}
              <Link to={`/requisitos/${id}?figura=1`} className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50">Vista para figura</Link>
            </span>
          )}
        </div>
        <p className="font-serif text-2xl leading-snug">«<TextoMarcado texto={v.texto} marcados={v.marcados} />»</p>
        {tiposPresentes.length > 0 && (
          <p className="flex flex-wrap gap-3 text-xs text-slate-600">
            {tiposPresentes.map((k) => (
              <span key={k} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ background: TONO_AMBIGUEDAD[k] }} />{TIPOS[k]?.etiqueta ?? k}
              </span>
            ))}
          </p>
        )}
        <RutaEstados transiciones={v.transiciones} enProceso={v.en_proceso} />
        <dl className="grid grid-cols-2 gap-3 rounded-xl border border-slate-200 p-3 text-sm md:grid-cols-6">
          <div><dt className="text-xs text-slate-500">ambiguos</dt><dd className="font-semibold">{v.resumen.n_ambiguos} de {v.resumen.n_terminos}</dd></div>
          <div><dt className="text-xs text-slate-500">vía</dt><dd className="flex items-center gap-1.5 font-semibold">{via && <span className="punto" style={{ background: via.tono }} />}{via?.etiqueta ?? "—"}</dd></div>
          <div><dt className="text-xs text-slate-500">similitud mínima</dt><dd className="font-semibold">{v.resumen.similitud_minima?.toFixed(2) ?? "—"} <span className="text-xs font-normal text-slate-500">umbral {v.config.umbral}</span></dd></div>
          <div><dt className="text-xs text-slate-500">rondas</dt><dd className="font-semibold">{v.resumen.rondas_max} de {v.config.max_rondas}</dd></div>
          <div><dt className="text-xs text-slate-500">mensajes</dt><dd className="font-semibold">{v.n_mensajes}{v.n_repetidos ? ` (${v.n_repetidos} repetidos)` : ""}</dd></div>
          <div><dt className="text-xs text-slate-500">modelos</dt><dd className="truncate text-xs" title={JSON.stringify(v.config.modelos)}>{v.config.modelos.clasificador} · crítico {v.config.modelos.critico}</dd></div>
        </dl>
        {aviso && <p className="text-sm text-rose-600">{aviso}</p>}
      </header>

      {v.errores.length > 0 && (
        <section className="rounded-xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-900">
          <p className="font-semibold">El caso terminó en error</p>
          <ul className="mt-1 space-y-1">
            {v.errores.map((e) => <li key={e.secuencia}>#{e.secuencia} · {e.nodo ?? "fuera de los nodos"} · {e.excepcion}: {e.mensaje} {e.prompt_version && <span className="font-mono text-xs">({e.prompt_version})</span>}</li>)}
          </ul>
          <p className="mt-1 text-xs">Las salidas crudas de cada intento están en la bitácora (mensaje error).</p>
        </section>
      )}

      {/* ---------------------------------------------------------------- fase 1 */}
      <Fase n="1" titulo="Enriquecimiento de conocimiento" quien="Extractor + filtros deterministas"
        vacia={!v.extraccion && "El Extractor aún no termina."}>
        {v.extraccion && (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2 text-sm">
              {CATEGORIAS.map(([k, nombre]) => {
                const ts = v.extraccion.terminos.filter((t) => t.categoria_tentativa === k);
                return ts.length ? <p key={k}><span className="text-slate-500">{nombre}: </span>{ts.map((t) => t.termino).join(", ")}</p> : null;
              })}
              {v.extraccion.descartados?.length > 0 && <p className="text-xs text-slate-500">Descartados por no estar en el texto: {v.extraccion.descartados.join(", ")}</p>}
              <p className="text-xs text-slate-500">
                {v.extraccion.modelo} · {v.extraccion.prompt_version}{v.extraccion.intentos > 1 ? ` · ${v.extraccion.intentos} intentos` : ""}
                {v.extraccion.duracion_ms != null && ` · ${(v.extraccion.duracion_ms / 1000).toFixed(1)} s`}
              </p>
            </div>
            <ul className="space-y-1 text-sm">
              {v.marcados.map((m, i) => (
                <li key={i} className="flex flex-wrap gap-2">
                  <b>«{m.texto}»</b>
                  <span className="text-slate-500">{DECISION[m.decision_filtro] ?? m.decision_filtro}</span>
                  {m.detalle && <span className="text-xs text-slate-500">· {m.detalle}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Fase>

      {/* ---------------------------------------------------------------- fases 2 y 3 */}
      <Fase n="2–3" titulo="Generación y discusión del modelo" quien="Clasificador · Divergencia · Crítico"
        vacia={!v.terminos.length && (v.en_proceso ? "Esperando al Clasificador…" : "Sin términos candidatos.")}>
        <div className="space-y-4">
          {ambiguos.map((t) => <TerminoTraza key={t.termino} t={t} umbral={v.config.umbral} />)}
          {univocos.length > 0 && (
            <ul className="space-y-1 rounded-xl border border-slate-200 p-3">
              {univocos.map((t) => <TerminoTraza key={t.termino} t={t} umbral={v.config.umbral} />)}
            </ul>
          )}
          {v.resumen.vaguedad.length > 0 && (
            <p className="rounded-lg bg-violet-50 p-3 text-sm text-violet-900">
              Vaguedad (catálogo, sin debate): {v.resumen.vaguedad.join(", ")}. No produce interpretaciones discretas: se marca y llega al humano.
            </p>
          )}
        </div>
      </Fase>

      {/* ---------------------------------------------------------------- fase 4 */}
      <Fase n="4" titulo="Validación del modelo" quien="Humano"
        vacia={!v.validacion && (v.estado === E.PENDIENTE_VALIDACION ? "Esperando la validación de una persona." : "Aún no llega a validación.")}>
        {v.validacion && (
          <div className="space-y-1 text-sm">
            <p><b>{v.validacion.decision === "aprobar" ? "Aprobado" : "Rechazado"}</b> · {hora(v.validacion.timestamp)}{v.validacion.comentario && <> · «{v.validacion.comentario}»</>}</p>
            <ul>
              {v.validacion.terminos.map((t) => (
                <li key={t.termino}>«{t.termino}»: {t.propuesta} → {t.final?.id ?? "—"} <span className="text-slate-500">({t.cambio})</span></li>
              ))}
            </ul>
          </div>
        )}
      </Fase>

      {/* ---------------------------------------------------------------- fase 5 */}
      <Fase n="5" titulo="Enriquecimiento (cierre)" quien="Modelador"
        vacia={!v.formalizacion && (v.estado === E.VALIDADO ? "El Modelador está formalizando…" : "Se formaliza al aprobar.")}>
        {v.formalizacion && (
          <div className="space-y-3 text-sm">
            <p className="font-serif text-lg">«{v.formalizacion.requisito_reescrito}»</p>
            <p><span className="text-slate-500">Entradas nuevas del LEL: </span>{v.formalizacion.entradas_lel?.length ? v.formalizacion.entradas_lel.join(", ") : "ninguna"}</p>
            {v.formalizacion.metas?.length > 0 && (
              <ul className="space-y-0.5">
                {v.formalizacion.metas.map((m) => (
                  <li key={m.id}><b>{m.id}</b> <span className="text-slate-500">{m.tipo.replace("_", " ")}</span> · {m.enunciado}{m.actor ? ` · ${m.actor}` : ""}{m.contribuye_a ? ` → ${m.contribuye_a}` : ""}</li>
                ))}
              </ul>
            )}
            {v.formalizacion.univocos?.length > 0 && <p className="text-xs text-slate-500">Unívocos (no entran al LEL, ADR 0007): {v.formalizacion.univocos.join(", ")}</p>}
          </div>
        )}
      </Fase>

      {!figura && (
        <Fase n="·" titulo="Bitácora del protocolo" quien={`${v.n_mensajes} mensajes`}>
          <Bitacora reqId={id} total={v.n_mensajes} />
        </Fase>
      )}
    </div>
  );
}
