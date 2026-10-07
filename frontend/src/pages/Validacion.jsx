import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { useRequisitoVivo } from "../hooks/useRequisitoVivo";
import { reprocesarRequisito, requisitosDeProyecto, validarRequisito } from "../services/backend";
import { ESTADOS as E, INFO_VIA, estaEnProceso } from "../constants/estados";
import { REGLAS, colorInterpretacion, tipo } from "../constants/agentes";
import { useOrb } from "../components/orb/useOrb";
import TextoMarcado from "../components/TextoMarcado";
import { Aviso, Cargando, EstadoChip, Plegable, Volver } from "../components/ui";

/*
 * Revisión humana (fase 4 de KMoS-SSA). Solo llega aquí lo que hace falta: los
 * requisitos en los que los agentes no llegaron a un acuerdo (o todos, con
 * VALIDACION_HUMANA=siempre; ADR 0017). Por término, la persona confirma el
 * significado que propuso el Crítico, elige otro o escribe el suyo. Al
 * confirmar, el Modelador reescribe el requisito; descartar no formaliza nada.
 */
export default function Validacion() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const orb = useOrb();
  const volver = params.get("volver");
  const { vista: v, error, recargar } = useRequisitoVivo(id);
  const [elecciones, setElecciones] = useState({}); // termino -> { id, editar, significado, parafrasis }
  const [comentario, setComentario] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [aviso, setAviso] = useState(null);
  const [siguiente, setSiguiente] = useState(null);

  const solicitud = v?.solicitud;
  const terminos = useMemo(() => solicitud?.terminos ?? [], [solicitud]);

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

  useEffect(() => {
    if (!v?.proyecto_id) return;
    requisitosDeProyecto(v.proyecto_id)
      .then((l) => setSiguiente(l.find((r) => r.estado === E.PENDIENTE_VALIDACION && r.req_id !== id) ?? null))
      .catch(() => setSiguiente(null));
  }, [v?.proyecto_id, v?.estado, id]);

  if (error) return <div className="space-y-4"><Volver a="/proyectos">Proyectos</Volver><Aviso>No pude cargar {id}: {error.message}</Aviso></div>;
  if (!v) return <Cargando>Cargando {id}…</Cargando>;

  const pendiente = v.estado === E.PENDIENTE_VALIDACION;
  const atras = volver ?? `/proyectos/${v.proyecto_id}`;

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
          if (e.editar) editadas[t.termino] = { id: e.id, significado: e.significado.trim(), parafrasis_del_requisito: e.parafrasis.trim() };
          else if (base && e.id !== t.propuesta?.id) editadas[t.termino] = base;
        }
      }
      await validarRequisito(id, { decision, interpretacionesEditadas: editadas, comentario });
      orb.setMood(decision === "aprobar" ? "success" : "sistema", { revertAfter: 1400 });
      setAviso(decision === "aprobar" ? "Listo. El Modelador está reescribiendo el requisito…" : "Descartado.");
      recargar({ seguir: true });
    } catch (e) {
      setAviso(`Error: ${e.message}`);
    } finally {
      setEnviando(false);
    }
  };

  const reprocesar = async () => {
    try {
      const r = await reprocesarRequisito(v);
      navigate(`/analisis?proyecto=${r.proyecto_id}&ids=${r.req_ids.join(",")}`);
    } catch (e) {
      setAviso(`Error: ${e.message}`);
    }
  };

  return (
    <div className="space-y-7 pb-28">
      <header className="space-y-4">
        <Volver a={atras}>{volver ? "Volver al análisis" : "Proyecto"}</Volver>
        <div className="flex flex-wrap items-center gap-3">
          <span className="mono text-[11px] text-[var(--bone-faint)]">{v.req_id}</span>
          <EstadoChip estado={v.estado} />
        </div>
        <h1>{pendiente ? "Elige el significado" : "Revisión"}</h1>
        {pendiente && terminos.length > 0 && (
          <p className="max-w-2xl text-[15px] text-[var(--bone-dim)]">
            Los agentes no llegaron a un acuerdo{terminos.length > 1 ? ` en ${terminos.length} términos` : ""}. Confirma la propuesta, elige otra o escribe la tuya.
          </p>
        )}
        <p className="serif text-[clamp(20px,2.2vw,28px)] leading-snug">«<TextoMarcado texto={v.texto} marcados={v.marcados.filter((m) => m.tipo)} />»</p>
      </header>

      {estaEnProceso(v.estado) && <div className="tarjeta flex items-center gap-3 px-5 py-4 text-[14.5px]"><span className="gira" /> Los agentes siguen trabajando; la revisión aparece aquí en cuanto terminen.</div>}

      {pendiente && (
        <>
          {!terminos.length && (
            <p className="tarjeta px-5 py-4 text-[14.5px] text-[var(--bone-dim)]">No hay términos dudosos. Confirma para que el Modelador reescriba el requisito.</p>
          )}
          {terminos.map((t) => (
            <TerminoAElegir key={t.termino} t={t} eleccion={elecciones[t.termino]}
              onCambio={(e) => setElecciones((x) => ({ ...x, [t.termino]: { ...x[t.termino], ...e } }))} />
          ))}
          <Plegable titulo="Comentario" nota="opcional: queda en la traza">
            <textarea value={comentario} onChange={(e) => setComentario(e.target.value)} rows={2} className="campo text-[14px]"
              placeholder="Por qué eliges esto" />
          </Plegable>
          <div className="sticky bottom-4 z-10 tarjeta flex flex-wrap items-center gap-3 px-4 py-3 shadow-2xl">
            <button disabled={enviando} onClick={() => enviar("aprobar")} className="pill">Confirmar</button>
            <button disabled={enviando} onClick={() => enviar("rechazar")} className="pill ghost">Descartar requisito</button>
            {aviso && <span className="text-[14px] text-[var(--bone-dim)]">{aviso}</span>}
          </div>
        </>
      )}

      {!pendiente && !estaEnProceso(v.estado) && (
        <div className="tarjeta space-y-2 px-5 py-4 text-[14.5px]">
          <p>{v.estado === E.FORMALIZADO ? "Listo: el requisito ya está en la especificación." : v.estado === E.RECHAZADO ? "Lo descartaste." : "Este requisito no espera revisión."}</p>
          {aviso && <p className="text-[var(--bone-dim)]">{aviso}</p>}
        </div>
      )}
      {v.estado === E.VALIDADO && <p className="flex items-center gap-2 text-[14px] text-[var(--bone-dim)]"><span className="gira" /> El Modelador está reescribiendo el requisito…</p>}

      <footer className="flex flex-wrap gap-2">
        {siguiente && (
          <button className="pill sm" onClick={() => navigate(`/requisitos/${siguiente.req_id}/validacion${volver ? `?volver=${encodeURIComponent(volver)}` : ""}`)}>
            Revisar el siguiente ({siguiente.req_id})
          </button>
        )}
        {[E.ERROR, E.RECHAZADO].includes(v.estado) && <button onClick={reprocesar} className="pill ghost sm">Volver a analizar</button>}
        <Link to={`/requisitos/${id}`} className="pill ghost sm">Ver el requisito</Link>
      </footer>
    </div>
  );
}

function TerminoAElegir({ t, eleccion, onCambio }) {
  const info = tipo(t.tipo_ambiguedad);
  const retiradas = new Map((t.retiradas ?? []).map((r) => [r.interpretacion_id, r]));
  const todas = Object.values(t.todas ?? {}).sort((a, b) => a.id.localeCompare(b.id, "es", { numeric: true }));
  const via = INFO_VIA[t.via];
  if (!eleccion) return null;
  const elegir = (i) => onCambio({ id: i.id, significado: i.significado, parafrasis: i.parafrasis_del_requisito, editar: false });

  return (
    <section className="tarjeta space-y-4 p-5">
      <header className="flex flex-wrap items-baseline gap-3">
        <h2 className="!text-[22px] !normal-case !tracking-normal" style={{ fontFamily: "var(--serif)" }}>«{t.termino}»</h2>
        <span className="etiqueta" title={info.descripcion}>{info.simple}</span>
        {via && <span className="ml-auto text-[12px] text-[var(--bone-faint)]">{via.simple}{t.rondas > 0 ? ` tras ${t.rondas} ronda${t.rondas > 1 ? "s" : ""}` : ""}</span>}
      </header>

      <fieldset className="space-y-2">
        <legend className="sr-only">Significado de «{t.termino}»</legend>
        {todas.map((i) => {
          const c = colorInterpretacion(i.id);
          const ret = retiradas.get(i.id);
          const marcada = eleccion.id === i.id && !eleccion.editar;
          return (
            <label key={i.id} className={`flex cursor-pointer gap-3 rounded-xl border p-3.5 transition-colors ${marcada ? "border-[var(--bone)] bg-white/[0.05]" : "border-[var(--line)] hover:bg-white/[0.03]"}`}>
              <input type="radio" name={`t-${t.termino}`} checked={marcada} onChange={() => elegir(i)} className="mt-1.5 accent-[var(--bone)]" />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2 text-[15.5px]">
                  <span className="h-2 w-2 rounded-full" style={{ background: c.trazo }} />
                  {i.significado}
                  {t.propuesta?.id === i.id && <span className="etiqueta !text-[var(--c1)]">propuesta del Crítico</span>}
                  {ret && <span className="etiqueta" title={ret.motivo}>descartada en el debate</span>}
                </span>
                <span className="mt-1 block text-[14px] text-[var(--bone-dim)]">{i.parafrasis_del_requisito}</span>
              </span>
            </label>
          );
        })}
        <label className={`flex cursor-pointer gap-3 rounded-xl border border-dashed p-3.5 ${eleccion.editar ? "border-[var(--bone)]" : "border-[var(--line)]"}`}>
          <input type="radio" name={`t-${t.termino}`} checked={eleccion.editar} onChange={() => onCambio({ editar: true })} className="mt-1.5 accent-[var(--bone)]" />
          <span className="min-w-0 flex-1 text-[15px]">
            Otro significado
            {eleccion.editar && (
              <span className="mt-3 block space-y-2">
                <input value={eleccion.significado} onChange={(e) => onCambio({ significado: e.target.value })}
                  placeholder="Qué significa aquí" className="campo text-[14.5px]" />
                <textarea value={eleccion.parafrasis} onChange={(e) => onCambio({ parafrasis: e.target.value })} rows={2}
                  placeholder="El requisito escrito con ese significado" className="campo text-[14.5px]" />
              </span>
            )}
          </span>
        </label>
      </fieldset>

      {t.justificacion?.length > 0 && (
        <Plegable titulo="Por qué lo propuso el Crítico">
          <ul className="space-y-1 text-[13.5px] text-[var(--bone-dim)]">
            {t.justificacion.map((j) => <li key={j.regla}><b className="font-medium text-[var(--bone)]">{REGLAS[j.regla]?.nombre ?? j.regla}:</b> {j.argumento}</li>)}
          </ul>
        </Plegable>
      )}
    </section>
  );
}
