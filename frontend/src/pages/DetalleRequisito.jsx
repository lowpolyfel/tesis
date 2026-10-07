import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { useOrb } from "../components/orb/useOrb";
import { useRequisitoVivo } from "../hooks/useRequisitoVivo";
import { reprocesarRequisito } from "../services/backend";
import { ESTADOS as E, INFO_VIA, MOOD_SIMPLE, estadoSimple } from "../constants/estados";
import { CATEGORIAS_NF, HALLAZGO, TIPOS, TIPO_REQUISITO, tipo as infoTipo } from "../constants/agentes";
import { recordarProyecto } from "../components/proyectoRecordado";
import EstadoBadge from "../components/EstadoBadge";
import TextoMarcado, { tonoMarcado } from "../components/TextoMarcado";
import RutaEstados from "../components/traza/RutaEstados";
import TerminoTraza from "../components/traza/TerminoTraza";
import Bitacora from "../components/traza/Bitacora";
import { Aviso, Cargando, Chip, EstadoChip, Plegable, Volver } from "../components/ui";
import { Editor } from "./proyecto/Especificacion";

/*
 * Un requisito. Arriba, el resultado: el texto original con lo que los agentes
 * notaron, la versión completa que escribió el Modelador (corregible) y qué
 * significado quedó para cada término dudoso. Plegada, la traza completa por
 * fases de KMoS-SSA (la figura de la tesis, CONTEXTO §11). Todo sale de la vista
 * por término del backend (GET /requisitos/{id}) y se actualiza sola mientras
 * los agentes trabajan. Con ?figura=1 se muestra solo la traza, clara y a ancho
 * fijo, para capturas.
 */
const CATEGORIAS = [["sujeto", "Sujetos"], ["verbo", "Verbos"], ["objeto", "Objetos"], ["estado", "Estados"]];
const DECISION = HALLAZGO; // lo que hicieron los filtros, dicho para una persona
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
  const { vista: v, error, recargar } = useRequisitoVivo(id);
  const [aviso, setAviso] = useState(null);

  // La esfera toma el tono del estado del requisito (piensa mientras los agentes trabajan)
  useEffect(() => {
    if (!v) return;
    orb.setMood(MOOD_SIMPLE[estadoSimple(v.estado).id]);
    orb.update("core", { active: v.en_proceso });
    recordarProyecto(v.proyecto_id);
  }, [orb, v]);
  useEffect(() => () => orb.update("core", { active: false }), [orb]);

  if (error) return <div className="space-y-4"><Volver a="/proyectos">Proyectos</Volver><Aviso>No pude cargar {id}: {error.message}</Aviso></div>;
  if (!v) return <Cargando>Cargando {id}…</Cargando>;

  // con el caso terminado, un término que el Clasificador no vio ya no lo verá (p. ej. falló)
  const sinClasificar = (t) => t.univoco == null && v.terminal;
  const ambiguos = v.terminos.filter((t) => !t.univoco && !sinClasificar(t));
  const univocos = v.terminos.filter((t) => t.univoco || sinClasificar(t));
  const enError = v.estado === E.ERROR;
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

  const tecnico = (
    <Tecnico v={v} id={id} figura={figura} ambiguos={ambiguos} univocos={univocos} enError={enError}
      tiposPresentes={tiposPresentes} via={via} aviso={aviso} reprocesar={reprocesar} />
  );
  if (figura) return tecnico;

  return (
    <div className="space-y-8">
      <Resultado v={v} id={id} ambiguos={ambiguos} reprocesar={reprocesar} aviso={aviso} onCorregido={() => recargar()} />
      <Plegable titulo="Detalles técnicos" nota="la traza completa: fases, debate y mensajes">
        <div className="tarjeta p-5">{tecnico}</div>
      </Plegable>
    </div>
  );
}

/* ------------------------------------------------------------------ resultado */

const CAMBIO_SIMPLE = { eleccion: "elegido por ti", edicion: "escrito por ti" };

function Resultado({ v, id, ambiguos, reprocesar, aviso, onCorregido }) {
  const [corrigiendo, setCorrigiendo] = useState(false);
  const f = v.formalizacion;
  const tipoReq = f?.tipo_requisito ? TIPO_REQUISITO[f.tipo_requisito] : null;
  const hallazgos = [
    ...v.resumen.vaguedad.map((t) => [t, "vaguedad"]),
    ...v.resumen.regionales.filter((t) => !ambiguos.some((a) => a.termino === t)).map((t) => [t, "regional"]),
    ...v.resumen.resueltos_por_lel.map((t) => [t, "lel"]),
  ];
  const tiposMarcas = [...new Set(v.marcados.map((m) => m.tipo).filter(Boolean))];

  return (
    <div className="space-y-7">
      <header className="space-y-4">
        <Volver a={`/proyectos/${v.proyecto_id}`}>Proyecto {v.proyecto_id}</Volver>
        <div className="flex flex-wrap items-center gap-3">
          <span className="mono text-[11px] text-[var(--bone-faint)]">{v.req_id}{v.origen?.marca ? ` · ${v.origen.marca}` : ""}</span>
          <EstadoChip estado={v.estado} />
          {tipoReq && <Chip tono={tipoReq.tono}>{tipoReq.etiqueta}{f.categoria ? ` · ${CATEGORIAS_NF[f.categoria] ?? f.categoria}` : ""}</Chip>}
          <span className="ml-auto flex flex-wrap gap-2">
            {v.estado === E.PENDIENTE_VALIDACION && <Link to={`/requisitos/${id}/validacion`} className="pill sm">Revisar</Link>}
            {v.terminal && <button onClick={reprocesar} className="pill ghost sm">Volver a analizar</button>}
            <Link to={`/analisis?proyecto=${v.proyecto_id}&ids=${id}&escena=1`} className="pill ghost sm">Ver en la escena</Link>
          </span>
        </div>
        <Aviso>{aviso}</Aviso>
      </header>

      <section className="space-y-2">
        <p className="etiqueta">{f ? "Original" : "Requisito"}</p>
        <p className="serif text-[clamp(22px,2.4vw,30px)] leading-snug">«<TextoMarcado texto={v.texto} marcados={v.marcados.filter((m) => m.tipo)} />»</p>
        {tiposMarcas.length > 0 && (
          <p className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-[var(--bone-faint)]">
            {tiposMarcas.map((k) => (
              <span key={k} className="flex items-center gap-1.5" title={TIPOS[k]?.descripcion}>
                <span className="h-2 w-2 rounded-full" style={{ background: tonoMarcado(k) }} />{TIPOS[k]?.simple ?? k}
              </span>
            ))}
          </p>
        )}
      </section>

      {v.en_proceso && <div className="tarjeta flex items-center gap-3 px-5 py-4 text-[14.5px]"><span className="gira" /> Los agentes siguen trabajando en este requisito.</div>}
      {v.estado === E.ERROR && (
        <div className="tarjeta space-y-1 !border-[#ff7b88]/40 px-5 py-4 text-[14.5px]">
          <p>Un agente no pudo terminar. Puedes volver a analizarlo; este queda en la historia.</p>
          {v.errores[0] && <p className="text-[13px] text-[var(--bone-faint)]">{v.errores[0].nodo ?? "sistema"}: {v.errores[0].mensaje}</p>}
        </div>
      )}
      {v.estado === E.RECHAZADO && <div className="tarjeta px-5 py-4 text-[14.5px] text-[var(--bone-dim)]">Lo descartaste en la revisión. Puedes volver a analizarlo.</div>}

      {f && (
        corrigiendo ? (
          <ul>
            <Editor x={{ req_id: v.req_id, clave: "Versión completa", reescrito: f.requisito_reescrito, tipo_requisito: f.tipo_requisito,
              categoria: f.categoria, supuestos: f.supuestos ?? [] }}
              onListo={(cambio) => { setCorrigiendo(false); if (cambio) onCorregido(); }} />
          </ul>
        ) : (
          <section className="tarjeta space-y-3 p-5">
            <div className="flex items-baseline gap-3">
              <p className="etiqueta">Versión completa</p>
              {f.corregido && <span className="text-[12px] text-[var(--bone-faint)]">corregida por ti</span>}
              <button className="mono ml-auto text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setCorrigiendo(true)}>corregir</button>
            </div>
            <p className="text-[18px] leading-relaxed">{f.requisito_reescrito}</p>
            {f.supuestos?.length > 0 && (
              <ul className="space-y-1 text-[13.5px] text-[#f2c879]">
                {f.supuestos.map((x, i) => <li key={i}>Supuesto: {x}</li>)}
              </ul>
            )}
          </section>
        )
      )}

      {(ambiguos.length > 0 || hallazgos.length > 0) && (
        <section className="space-y-3">
          <p className="etiqueta">Lo que se aclaró</p>
          <ul className="space-y-2">
            {ambiguos.map((t) => <TerminoAclarado key={t.termino} t={t} />)}
            {hallazgos.map(([t, k]) => (
              <li key={`${k}-${t}`} className="flex flex-wrap items-baseline gap-x-3 text-[14.5px]">
                <span className="italic">«{t}»</span>
                <span className="text-[var(--bone-faint)]">{infoTipo(k).descripcion}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {!v.en_proceso && v.extraccion && !ambiguos.length && !hallazgos.length && (
        <p className="text-[14.5px] text-[var(--bone-dim)]">No había palabras con doble sentido.</p>
      )}

      {ambiguos.some((t) => t.entrada_lel) && (
        <p className="text-[14px] text-[var(--bone-dim)]">
          Entró al léxico: {ambiguos.filter((t) => t.entrada_lel).map((t) => t.entrada_lel.simbolo).join(", ")} ·{" "}
          <Link className="enlace" to={`/proyectos/${v.proyecto_id}?vista=lexico`}>ver el léxico</Link>
        </p>
      )}
    </div>
  );
}

/* Un término dudoso: con qué significado quedó y cómo se llegó ahí */
function TerminoAclarado({ t }) {
  const res = t.resolucion;
  const final = t.validacion?.final ?? res?.propuesta;
  const via = res ? INFO_VIA[res.via] : null;
  const info = infoTipo(t.tipo_ambiguedad);
  return (
    <li className="tarjeta flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 py-3">
      <span className="text-[15.5px] italic">«{t.termino}»</span>
      <span className="etiqueta" title={info.descripcion}>{info.simple}</span>
      <span className="min-w-0 flex-1 text-[15px]">{final ? <>→ {final.significado}</> : <span className="text-[var(--bone-faint)]">en debate…</span>}</span>
      <span className="text-[12px] text-[var(--bone-faint)]">
        {CAMBIO_SIMPLE[t.validacion?.cambio] ?? via?.simple ?? ""}
      </span>
    </li>
  );
}

/* ------------------------------------------------------------------ traza técnica */

function Tecnico({ v, id, figura, ambiguos, univocos, enError, tiposPresentes, via, aviso, reprocesar }) {
  return (
    <div className="space-y-8 pb-4">
      {/* ---------------------------------------------------------------- encabezado */}
      <header className="space-y-3">
        {figura && <p className="text-sm text-slate-500">{v.proyecto_id} / ciclo {v.ciclo} / {v.req_id}</p>}
        <div className="flex flex-wrap items-center gap-3">
          {figura ? <h1 className="text-2xl font-semibold">{v.req_id}</h1> : <p className="font-mono text-sm">{v.req_id}</p>}
          <EstadoBadge estado={v.estado} className="text-sm" />
          <span className="text-xs text-slate-500">
            {v.origen?.archivo && <>{v.origen.archivo}{v.origen.pagina ? `, p. ${v.origen.pagina}` : ""}{v.origen.marca ? ` · ${v.origen.marca}` : ""} · </>}
            creado {hora(v.creado)}
            {v.origen?.reproceso_de && <> · reprocesa <Link className="underline" to={`/requisitos/${v.origen.reproceso_de}`}>{v.origen.reproceso_de}</Link></>}
          </span>
          {!figura && (
            <span className="ml-auto flex flex-wrap gap-2 text-sm">
              <Link to={`/requisitos/${id}?figura=1`} className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50">Vista para figura</Link>
            </span>
          )}
        </div>
        {figura && <p className="font-serif text-2xl leading-snug">«<TextoMarcado texto={v.texto} marcados={v.marcados} claro={figura} />»</p>}
        {figura && tiposPresentes.length > 0 && (
          <p className="flex flex-wrap gap-3 text-xs text-slate-600">
            {tiposPresentes.map((k) => (
              <span key={k} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ background: tonoMarcado(k, figura) }} />{TIPOS[k]?.etiqueta ?? k}
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
        <p className="text-xs text-slate-500">
          Validación humana: {v.config.validacion_humana ? v.config.validacion_humana.replaceAll("_", " ") : "siempre (anterior a ADR 0017)"}
          {" · "}contexto del proyecto: {v.config.contexto_proyecto ? <span title={v.config.contexto_proyecto}>«{v.config.contexto_proyecto.length > 80 ? `${v.config.contexto_proyecto.slice(0, 79)}…` : v.config.contexto_proyecto}»</span> : "ninguno"}
        </p>
        {figura && aviso && <p className="text-sm text-rose-600">{aviso}</p>}
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
          {ambiguos.map((t) => <TerminoTraza key={t.termino} t={t} umbral={v.config.umbral} terminal={v.terminal} />)}
          {univocos.length > 0 && (
            <ul className="space-y-1 rounded-xl border border-slate-200 p-3">
              {univocos.map((t) => <TerminoTraza key={t.termino} t={t} umbral={v.config.umbral} terminal={v.terminal} enError={enError} />)}
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
      <Fase n="4" titulo="Validación del modelo" quien={v.validacion?.automatica ? "Sistema (no hacía falta una persona)" : "Humano"}
        vacia={!v.validacion && (v.estado === E.PENDIENTE_VALIDACION ? "Esperando la revisión de una persona."
          : enError ? "No llegó a validación: el caso terminó en error." : "Aún no llega a validación.")}>
        {v.validacion && (
          <div className="space-y-1 text-sm">
            <p>
              <b>{v.validacion.automatica ? "Aprobado por el sistema" : v.validacion.decision === "aprobar" ? "Aprobado" : "Rechazado"}</b>
              {v.validacion.automatica && <span className="text-slate-500"> ({v.validacion.motivo === "sin_ambiguedad" ? "sin términos ambiguos" : v.validacion.motivo === "validacion_desactivada" ? "validación humana desactivada" : "sin arbitraje: no hacía falta una persona"})</span>}
              {" · "}{hora(v.validacion.timestamp)}{v.validacion.comentario && <> · «{v.validacion.comentario}»</>}
            </p>
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
        vacia={!v.formalizacion && (v.estado === E.VALIDADO ? "El Modelador está formalizando…"
          : enError ? "No se formalizó: el caso terminó en error." : v.estado === E.RECHAZADO ? "No se formaliza: la persona rechazó el requisito."
            : "Se formaliza al aprobar.")}>
        {v.formalizacion && (
          <div className="space-y-3 text-sm">
            <p className="font-serif text-lg">«{v.formalizacion.requisito_reescrito}»</p>
            {v.formalizacion.tipo_requisito && (
              <p><span className="text-slate-500">Tipo: </span>{TIPO_REQUISITO[v.formalizacion.tipo_requisito]?.etiqueta}{v.formalizacion.categoria ? ` (${CATEGORIAS_NF[v.formalizacion.categoria] ?? v.formalizacion.categoria})` : ""}</p>
            )}
            {v.formalizacion.supuestos?.length > 0 && <p><span className="text-slate-500">Supuestos tomados del contexto: </span>{v.formalizacion.supuestos.join(" · ")}</p>}
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
          <Bitacora reqId={id} total={v.n_mensajes} ultima={v.ultima_secuencia} />
        </Fase>
      )}
    </div>
  );
}
