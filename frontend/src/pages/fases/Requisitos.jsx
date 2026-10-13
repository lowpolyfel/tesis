import { useRef, useState } from "react";
import { useApi } from "../../hooks/useApi";
import { especificacionMarkdown, obtenerFase } from "../../services/backend";
import { CATEGORIAS_NF, TIPO_REQUISITO } from "../../constants/agentes";
import { PRIORIDADES } from "../../constants/fases";
import { seccion } from "../../components/orb/secciones";
import { useOrb } from "../../components/orb/useOrb";
import { volarALaEsfera } from "../../components/fases/vuelo";
import { descargar } from "../../components/artefactos/exportar";
import GeneracionFase from "../../components/fases/GeneracionFase";
import { Avisos, Desactualizado, Hecho, Historial, Regenerar, SinGenerar, useFase } from "../../components/fases/Fase";
import Citas, { useCitas } from "../../components/fases/RefCita";
import { Aviso, Cargando, Chip, Plegable } from "../../components/ui";

/*
 * Fase 5 (ADR 0024): los requisitos, el producto final. Los escribe el Modelador por meta
 * estratégica con la entrevista, el LEL, el contexto, el mapa y las metas validados. Cada
 * uno dice qué metas realiza, qué términos del LEL usa y qué parte de la entrevista lo
 * respalda; el código avisa lo que conviene mirar (expresiones vagas, sin criterios…).
 * La persona valida, corrige, agrega o quita; la especificación completa se descarga en
 * Markdown, con su trazabilidad.
 */
const GRUPOS = [["funcional", "Requisitos funcionales"], ["no_funcional", "Requisitos no funcionales"]];
const lineas = (t) => t.split("\n").map((x) => x.trim()).filter(Boolean);

export default function Requisitos({ proyecto, onCambio }) {
  const orb = useOrb();
  const pid = proyecto.proyecto_id;
  const { vista, setVista, error, guardar, conservar } = useFase(pid, "requisitos", onCambio);
  const { datos: metasVista } = useApi(() => obtenerFase(pid, "metas"), [pid]);
  const turnos = useCitas(pid);
  const [generando, setGenerando] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState(null);
  const [aviso, setAviso] = useState(null);
  const sec = seccion("fase_requisitos");

  if (error) return <Aviso error={error} />;
  if (!vista) return <Cargando>Cargando los requisitos…</Cargando>;
  const doc = vista.documento;
  const generacion = generando && (
    <GeneracionFase proyectoId={pid} fase="requisitos" seccionId="fase_requisitos" moodGenerando="requisitos_generando" moodSeccion={sec.mood}
      onListo={(d) => { setGenerando(false); setVista((v) => ({ ...v, documento: d, al_dia: true })); onCambio?.(); }}
      onCancelar={() => setGenerando(false)} />
  );
  if (!doc) {
    return (
      <>
        <SinGenerar disponible={vista.disponible} motivo={vista.motivo} generando={vista.generando} titulo="Los requisitos"
          texto="Con todo validado —la entrevista, el léxico con sus intenciones, el mapa y las metas—, los agentes escriben los requisitos funcionales y no funcionales que realizan cada meta específica. Cada requisito usa los términos del LEL en el sentido acordado y se rastrea a sus metas y a lo que se dijo en la entrevista."
          onGenerar={() => setGenerando(true)} />
        {generacion}
      </>
    );
  }

  const reqs = doc.contenido.requisitos;
  const metas = Object.fromEntries((metasVista?.documento?.contenido.metas ?? []).map((m) => [m.id, m]));
  const guardarReqs = async (nuevos) => {
    setErrorGuardar(null);
    try { await guardar({ requisitos: nuevos }); return true; } catch (e) { setErrorGuardar(e); return false; }
  };
  const cambiar = (id, cambios) => guardarReqs(reqs.map((r) => (r.id === id ? { ...r, ...cambios } : r)));
  const quitar = (id) => guardarReqs(reqs.filter((r) => r.id !== id));
  const agregar = (tipo) => {
    const pref = tipo === "funcional" ? "RF" : "RNF";
    const n = Math.max(0, ...reqs.filter((r) => new RegExp(`^${pref}\\d+$`).test(r.id)).map((r) => Number(r.id.slice(pref.length)))) + 1;
    return guardarReqs([...reqs, { id: `${pref}${String(n).padStart(2, "0")}`, texto: "El sistema debe…", tipo,
      categoria: tipo === "funcional" ? null : "usabilidad", prioridad: "media", metas: [], simbolos: [], evidencia: [],
      criterios: [], supuestos: [], avisos: [], validado: false, origen: "persona" }]);
  };
  const pendientes = reqs.filter((r) => !r.validado).length;
  const conAviso = reqs.filter((r) => r.avisos?.length).length;

  const bajar = async () => {
    try {
      const md = await especificacionMarkdown(pid);
      descargar(`especificacion-${proyecto.nombre.toLowerCase().replace(/[^a-z0-9áéíóúñ]+/gi, "-")}.md`, md, "text/markdown");
    } catch (e) { setAviso(e.message); }
  };
  const copiar = async () => {
    try { await navigator.clipboard.writeText(await especificacionMarkdown(pid)); setAviso("Copiada al portapapeles."); } catch { setAviso("No se pudo copiar."); }
    setTimeout(() => setAviso(null), 2000);
  };

  return (
    <div className="space-y-6">
      {!vista.al_dia && <Desactualizado que="los requisitos" onRegenerar={() => setGenerando(true)} onConservar={conservar} />}
      {vista.hecho && <Hecho texto="Los requisitos están validados: la especificación está lista, de la entrevista a cada requisito." />}

      <div className="flex flex-wrap items-center gap-3">
        <p className="text-[14px] text-[var(--bone-dim)]">
          {reqs.filter((r) => r.tipo === "funcional").length} funcionales · {reqs.filter((r) => r.tipo !== "funcional").length} no funcionales
          {pendientes > 0 && <> · <b className="font-normal text-[#ffc457]">{pendientes}</b> por validar</>}
          {conAviso > 0 && <> · {conAviso} con algo que revisar</>}
        </p>
        <span className="ml-auto flex flex-wrap gap-2">
          {pendientes > 0 && (
            <button className="pill sm" onClick={async () => {
              if (await guardarReqs(reqs.map((r) => ({ ...r, validado: true })))) { orb.setMood("success"); orb.poke(1.2); setTimeout(() => orb.setMood(sec.mood), 1200); }
            }}>Validar todos</button>
          )}
          <button className="pill ghost sm" onClick={bajar}>Descargar especificación</button>
          <button className="pill ghost sm" onClick={copiar}>Copiar en Markdown</button>
        </span>
      </div>
      {aviso && <p className="text-[13px] text-[var(--bone-dim)]">{aviso}</p>}
      <Aviso error={errorGuardar} />

      {GRUPOS.map(([tipo, titulo]) => {
        const del = reqs.filter((r) => (tipo === "funcional" ? r.tipo === "funcional" : r.tipo !== "funcional"));
        return (
          <section key={tipo} className="space-y-3">
            <div className="flex items-center gap-3">
              <h2>{titulo}</h2>
              <button className="mono ml-auto text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => agregar(tipo)}>+ agregar</button>
            </div>
            <ol className="space-y-3">
              {del.map((r) => <Requisito key={r.id} r={r} metas={metas} turnos={turnos} moodSeccion={sec.mood} onCambiar={cambiar} onQuitar={quitar} />)}
            </ol>
            {!del.length && <p className="text-[13.5px] text-[var(--bone-faint)]">Ninguno.</p>}
          </section>
        );
      })}

      <Plegable titulo="Matriz de trazabilidad" nota="requisito → metas, términos y entrevista">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12.5px]">
            <thead className="etiqueta"><tr><th className="py-1 pr-3">Requisito</th><th className="pr-3">Metas</th><th className="pr-3">Términos del LEL</th><th>Entrevista</th></tr></thead>
            <tbody>
              {reqs.map((r) => (
                <tr key={r.id} className="border-t border-[var(--line)] align-top text-[var(--bone-dim)]">
                  <td className="mono py-1.5 pr-3 text-[10px] text-[var(--bone)]">{r.id}</td>
                  <td className="pr-3">{r.metas.join(", ") || "—"}</td>
                  <td className="pr-3">{r.simbolos.join(", ") || "—"}</td>
                  <td>{r.evidencia.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Plegable>
      <Avisos avisos={doc.avisos} />
      <Historial doc={doc} />
      <div className="flex justify-end"><Regenerar que="los requisitos" onConfirmar={() => setGenerando(true)} /></div>
      {generacion}
    </div>
  );
}

function Requisito({ r, metas, turnos, moodSeccion, onCambiar, onQuitar }) {
  const orb = useOrb();
  const ref = useRef(null);
  const [editando, setEditando] = useState(r.origen === "persona" && r.texto === "El sistema debe…");
  const t = TIPO_REQUISITO[r.tipo] ?? TIPO_REQUISITO.funcional;
  const validar = async () => {
    if (await onCambiar(r.id, { validado: true })) volarALaEsfera(orb, ref.current, { mood: "success", etiqueta: "✓", moodSeccion });
  };
  if (editando) {
    return (
      <li ref={ref}>
        <EditorRequisito r={r} metas={metas} onCancelar={() => setEditando(false)}
          onGuardar={async (cambios) => {
            if (await onCambiar(r.id, { ...cambios, validado: true })) {
              setEditando(false);
              volarALaEsfera(orb, ref.current, { mood: "success", etiqueta: "✎", moodSeccion });
            }
          }} />
      </li>
    );
  }
  return (
    <li ref={ref} className="tarjeta space-y-3 p-5" onPointerEnter={() => orb.poke(0.15)}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="mono text-[11px]" style={{ color: `color-mix(in oklab, ${t.tono} var(--mezcla-tono), var(--bone))` }}>{r.id}</span>
        <span className="etiqueta">{r.categoria ? `${CATEGORIAS_NF[r.categoria] ?? r.categoria} · ` : ""}prioridad {r.prioridad}</span>
        {r.origen === "persona" && <span className="etiqueta">lo agregaste</span>}
        <span className="ml-auto">{r.validado ? <Chip tono="#57f7a7">validado</Chip> : <Chip tono="#ffc457">por validar</Chip>}</span>
      </div>
      <p className="text-[16.5px] leading-snug">{r.texto}</p>
      {r.criterios?.length > 0 && (
        <div>
          <p className="etiqueta">Criterios de aceptación</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13.5px] text-[var(--bone-dim)]">{r.criterios.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </div>
      )}
      {r.supuestos?.length > 0 && (
        <div>
          <p className="etiqueta">Supuestos (confírmalos)</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13.5px] text-[var(--bone-dim)]">{r.supuestos.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
        {r.metas.map((m) => <span key={m} title={metas[m]?.enunciado ?? ""} className="mono rounded-full border border-[#ff7a8a]/40 px-2 py-0.5 text-[9.5px]">{m}</span>)}
        {r.simbolos.map((s) => <span key={s} className="mono rounded-full bg-[color-mix(in_oklab,var(--bone)_6%,transparent)] px-2 py-0.5 text-[9.5px]">{s}</span>)}
      </div>
      <Citas refs={r.evidencia} turnos={turnos} />
      {r.avisos?.length > 0 && <p className="text-[12.5px] text-[var(--aviso)]">Revisa: {r.avisos.join(" · ")}</p>}
      <div className="flex flex-wrap items-center gap-2">
        {!r.validado && <button className="pill sm" onClick={validar}>✓ Validar</button>}
        <button className="pill ghost sm" onClick={() => setEditando(true)}>✎ Corregir</button>
        <button className="mono ml-auto px-1 text-[10px] text-[var(--bone-faint)] hover:text-[var(--danger)]" onClick={() => onQuitar(r.id)}>quitar</button>
      </div>
    </li>
  );
}

function EditorRequisito({ r, metas, onGuardar, onCancelar }) {
  const [texto, setTexto] = useState(r.texto);
  const [tipo, setTipo] = useState(r.tipo);
  const [categoria, setCategoria] = useState(r.categoria ?? "usabilidad");
  const [prioridad, setPrioridad] = useState(r.prioridad);
  const [criterios, setCriterios] = useState(r.criterios.join("\n"));
  const [supuestos, setSupuestos] = useState(r.supuestos.join("\n"));
  const [elegidas, setElegidas] = useState(new Set(r.metas));
  const especificas = Object.values(metas).filter((m) => m.nivel === "especifica");
  return (
    <form className="tarjeta space-y-4 p-5" style={{ borderColor: "color-mix(in oklab,#57f7a7 40%,var(--line))" }}
      onSubmit={(e) => {
        e.preventDefault();
        onGuardar({ texto: texto.trim(), tipo, categoria: tipo === "funcional" ? null : categoria, prioridad,
          criterios: lineas(criterios), supuestos: lineas(supuestos), metas: [...elegidas] });
      }}>
      <p className="etiqueta">Corregir {r.id}</p>
      <textarea autoFocus value={texto} maxLength={700} rows={3} onChange={(e) => setTexto(e.target.value)} className="campo text-[15px]" required />
      <div className="flex flex-wrap gap-3">
        <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="campo w-auto text-[13.5px]">
          <option value="funcional">Funcional</option><option value="no_funcional">No funcional</option>
        </select>
        {tipo !== "funcional" && (
          <select value={categoria} onChange={(e) => setCategoria(e.target.value)} className="campo w-auto text-[13.5px]">
            {Object.entries(CATEGORIAS_NF).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        )}
        <select value={prioridad} onChange={(e) => setPrioridad(e.target.value)} className="campo w-auto text-[13.5px]">
          {PRIORIDADES.map((p) => <option key={p} value={p}>prioridad {p}</option>)}
        </select>
      </div>
      <label className="block space-y-1.5">
        <span className="etiqueta">Criterios de aceptación <span className="normal-case tracking-normal">(uno por renglón)</span></span>
        <textarea value={criterios} rows={2} onChange={(e) => setCriterios(e.target.value)} className="campo text-[14px]" />
      </label>
      <label className="block space-y-1.5">
        <span className="etiqueta">Supuestos <span className="normal-case tracking-normal">(uno por renglón)</span></span>
        <textarea value={supuestos} rows={2} onChange={(e) => setSupuestos(e.target.value)} className="campo text-[14px]" />
      </label>
      {especificas.length > 0 && (
        <fieldset className="space-y-1.5">
          <legend className="etiqueta">Metas específicas que realiza</legend>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            {especificas.map((m) => (
              <label key={m.id} className="flex items-center gap-2 text-[13px]" title={m.enunciado}>
                <input type="checkbox" className="casilla" checked={elegidas.has(m.id)} onChange={() => setElegidas((s) => {
                  const n = new Set(s);
                  if (n.has(m.id)) n.delete(m.id); else n.add(m.id);
                  return n;
                })} />
                {m.id}
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <div className="flex gap-2">
        <button className="pill sm" disabled={!texto.trim()}>Guardar</button>
        <button type="button" className="pill ghost sm" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  );
}
