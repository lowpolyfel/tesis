import { useRef, useState } from "react";
import { NIVELES_META, nivelMeta } from "../../constants/fases";
import { seccion } from "../../components/orb/secciones";
import { useOrb } from "../../components/orb/useOrb";
import { volarALaEsfera } from "../../components/fases/vuelo";
import GeneracionFase from "../../components/fases/GeneracionFase";
import { Avisos, Desactualizado, Hecho, Historial, Regenerar, SinGenerar, useFase } from "../../components/fases/Fase";
import Citas, { useCitas } from "../../components/fases/RefCita";
import { Aviso, Cargando, Chip } from "../../components/ui";

/*
 * Fase 4 (ADR 0024): las metas en tres niveles, como un árbol.
 *   de la organización (MO) → estratégicas (ME) → específicas (MS, con su indicador)
 * Las propone el Modelador con el LEL y el mapa validados y lo que se dijo en la entrevista;
 * la persona valida, corrige, agrega o quita cada una. Cada cambio se guarda al momento.
 */
export default function Metas({ proyectoId, onCambio, onSeguir }) {
  const orb = useOrb();
  const { vista, setVista, error, guardar, conservar, recargar } = useFase(proyectoId, "metas", onCambio);
  const turnos = useCitas(proyectoId);
  const [generando, setGenerando] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState(null);
  const sec = seccion("metas");

  if (error) return <Aviso error={error} />;
  if (!vista) return <Cargando>Cargando las metas…</Cargando>;
  const doc = vista.documento;
  const generacion = generando && (
    <GeneracionFase proyectoId={proyectoId} fase="metas" seccionId="metas" moodGenerando="metas_generando" moodSeccion={sec.mood}
      onListo={(d) => { setGenerando(false); setVista((v) => ({ ...v, documento: d, al_dia: true })); onCambio?.(); }}
      onCancelar={() => { setGenerando(false); recargar(); }} />
  );
  if (!doc) {
    return (
      <>
        <SinGenerar disponible={vista.disponible} motivo={vista.motivo} generando={vista.generando} titulo="Las metas del proyecto"
          texto="Los agentes leen la entrevista, el léxico y el mapa validados y proponen las metas en tres niveles: lo que la organización quiere lograr, las metas estratégicas con las que el sistema contribuye y las metas específicas, concretas y verificables, que después realizarán los requisitos."
          onGenerar={() => setGenerando(true)} />
        {generacion}
      </>
    );
  }

  const metas = doc.contenido.metas;
  const guardarMetas = async (nuevas) => {
    setErrorGuardar(null);
    try { await guardar({ metas: nuevas }); } catch (e) { setErrorGuardar(e); throw e; }
  };
  const cambiarMeta = (id, cambios) => guardarMetas(metas.map((m) => (m.id === id ? { ...m, ...cambios } : m)));
  const quitarMeta = (id) => guardarMetas(metas.filter((m) => m.id !== id));
  const agregarMeta = (nivel, contribuye_a) => {
    const prefijo = nivelMeta(nivel).prefijo;
    const n = Math.max(0, ...metas.filter((m) => m.id.startsWith(prefijo)).map((m) => Number(m.id.slice(2)) || 0)) + 1;
    return guardarMetas([...metas, { id: `${prefijo}${n}`, nivel, enunciado: "Nueva meta", contribuye_a: contribuye_a ?? null,
      indicador: nivel === "especifica" ? "" : null, simbolos: [], evidencia: [], validada: false, origen: "persona" }]);
  };
  const pendientes = metas.filter((m) => !m.validada).length;
  const hijas = (id) => metas.filter((m) => m.contribuye_a === id);
  const raiz = metas.filter((m) => m.nivel === "organizacional");

  return (
    <div className="space-y-5">
      {!vista.al_dia && <Desactualizado que="las metas" onRegenerar={() => setGenerando(true)} onConservar={conservar} />}
      {vista.hecho && <Hecho texto="Las metas están validadas. Con ellas, los agentes escriben los requisitos." accion="Seguir a los requisitos" onAccion={onSeguir} />}

      <div className="flex flex-wrap items-center gap-3">
        <p className="text-[14px] text-[var(--bone-dim)]">
          {NIVELES_META.map((n) => `${metas.filter((m) => m.nivel === n.id).length} ${n.corto.toLowerCase()}${metas.filter((m) => m.nivel === n.id).length === 1 ? "" : "s"}`).join(" · ")}
          {pendientes > 0 && <> · <b className="font-normal text-[#ffc457]">{pendientes}</b> por validar</>}
        </p>
        {pendientes > 0 && (
          <button className="pill sm ml-auto" onClick={async () => {
            await guardarMetas(metas.map((m) => ({ ...m, validada: true })));
            orb.setMood("success"); orb.poke(1); setTimeout(() => orb.setMood(sec.mood), 1200);
          }}>Validar todas</button>
        )}
      </div>
      <Aviso error={errorGuardar} />

      <ol className="space-y-6">
        {raiz.map((mo) => (
          <li key={mo.id} className="space-y-3">
            <TarjetaMeta m={mo} turnos={turnos} hijas={hijas(mo.id)} onCambiar={cambiarMeta} onQuitar={quitarMeta}
              onAgregarHija={() => agregarMeta("estrategica", mo.id)} moodSeccion={sec.mood} />
            <ol className="arbol-metas space-y-3">
              {hijas(mo.id).map((me) => (
                <li key={me.id} className="space-y-3">
                  <TarjetaMeta m={me} turnos={turnos} hijas={hijas(me.id)} onCambiar={cambiarMeta} onQuitar={quitarMeta}
                    onAgregarHija={() => agregarMeta("especifica", me.id)} moodSeccion={sec.mood} />
                  <ol className="arbol-metas space-y-3">
                    {hijas(me.id).map((ms) => (
                      <li key={ms.id}><TarjetaMeta m={ms} turnos={turnos} hijas={[]} onCambiar={cambiarMeta} onQuitar={quitarMeta} moodSeccion={sec.mood} /></li>
                    ))}
                  </ol>
                </li>
              ))}
            </ol>
          </li>
        ))}
      </ol>
      <button className="pill ghost sm" onClick={() => agregarMeta("organizacional", null)}>+ Meta de la organización</button>

      <Avisos avisos={doc.avisos} />
      <Historial doc={doc} />
      <div className="flex justify-end"><Regenerar que="las metas" onConfirmar={() => setGenerando(true)} /></div>
      {generacion}
    </div>
  );
}

function TarjetaMeta({ m, turnos, hijas, onCambiar, onQuitar, onAgregarHija, moodSeccion }) {
  const orb = useOrb();
  const ref = useRef(null);
  const nivel = nivelMeta(m.nivel);
  const [editando, setEditando] = useState(m.origen === "persona" && m.enunciado === "Nueva meta");
  const [enunciado, setEnunciado] = useState(m.enunciado);
  const [indicador, setIndicador] = useState(m.indicador ?? "");
  const [error, setError] = useState(null);
  const hacer = async (fn, vuelo) => {
    setError(null);
    try {
      await fn();
      if (vuelo) volarALaEsfera(orb, ref.current, { moodSeccion, ...vuelo });
      return true;
    } catch (e) {
      setError(e);
      return false;
    }
  };
  return (
    <div ref={ref} className="tarjeta meta space-y-3 p-4" style={{ "--tono": nivel.tono }}>
      <div className="flex flex-wrap items-center gap-2">
        <Chip tono={nivel.tono}>{m.id} · {nivel.corto}</Chip>
        {m.origen === "persona" && <span className="etiqueta">la agregaste</span>}
        <span className="ml-auto">{m.validada ? <Chip tono="#57f7a7">validada</Chip> : <Chip tono="#ffc457">por validar</Chip>}</span>
      </div>
      {editando ? (
        <form className="space-y-2" onSubmit={(e) => {
          e.preventDefault();
          hacer(() => onCambiar(m.id, { enunciado: enunciado.trim() || m.enunciado, indicador: m.nivel === "especifica" ? indicador.trim() || null : null, validada: true }),
            { mood: "success" }).then((ok) => ok && setEditando(false));
        }}>
          <textarea autoFocus value={enunciado} maxLength={320} rows={2} onChange={(e) => setEnunciado(e.target.value)} className="campo text-[15px]" />
          {m.nivel === "especifica" && (
            <input value={indicador} maxLength={240} onChange={(e) => setIndicador(e.target.value)} placeholder="Indicador: cómo se sabe que se cumple" className="campo text-[13.5px]" />
          )}
          <div className="flex gap-2">
            <button className="pill sm">Guardar</button>
            <button type="button" className="pill ghost sm" onClick={() => setEditando(false)}>Cancelar</button>
          </div>
        </form>
      ) : (
        <>
          <p className={m.nivel === "organizacional" ? "serif text-[22px] leading-tight" : "text-[15.5px] leading-snug"}>{m.enunciado}</p>
          {m.indicador && <p className="text-[13px] text-[var(--bone-dim)]"><span className="etiqueta mr-2">Indicador</span>{m.indicador}</p>}
        </>
      )}
      {m.simbolos?.length > 0 && <p className="flex flex-wrap gap-1.5">{m.simbolos.map((s) => <span key={s} className="mono rounded-full bg-[color-mix(in_oklab,var(--bone)_6%,transparent)] px-2 py-0.5 text-[9.5px]">{s}</span>)}</p>}
      <Citas refs={m.evidencia} turnos={turnos} />
      <Aviso error={error} />
      {!editando && (
        <div className="flex flex-wrap items-center gap-2">
          {!m.validada && <button className="pill sm" onClick={() => hacer(() => onCambiar(m.id, { validada: true }), { mood: "success", etiqueta: "✓" })}>✓ Validar</button>}
          <button className="pill ghost sm" onClick={() => { setEnunciado(m.enunciado); setIndicador(m.indicador ?? ""); setEditando(true); }}>✎ Corregir</button>
          {onAgregarHija && <button className="pill ghost sm" onClick={() => hacer(onAgregarHija)}>+ {m.nivel === "organizacional" ? "Estratégica" : "Específica"}</button>}
          {!hijas.length && <button className="mono ml-auto px-1 text-[10px] text-[var(--bone-faint)] hover:text-[var(--danger)]" onClick={() => hacer(() => onQuitar(m.id))}>quitar</button>}
        </div>
      )}
    </div>
  );
}
