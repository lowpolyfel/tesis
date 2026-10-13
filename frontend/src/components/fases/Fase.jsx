import { useCallback, useEffect, useState } from "react";
import { conservarFase, guardarFase, obtenerFase } from "../../services/backend";
import { Aviso, Confirmar, Plegable } from "../ui";

/*
 * Lo común de las fases que genera el Modelador (mapa, metas y requisitos; ADR 0024):
 * cargar el documento (y seguir preguntando mientras se genera en segundo plano), guardar
 * lo que la persona edita, el aviso de que lo de atrás cambió, la confirmación antes de
 * volver a generar y el historial de cambios.
 */
const SONDEO_MS = 2000;

export function useFase(proyectoId, fase, onCambio) {
  const [vista, setVista] = useState(null);
  const [error, setError] = useState(null);
  const recargar = useCallback(() => obtenerFase(proyectoId, fase).then((v) => { setVista(v); setError(null); return v; })
    .catch((e) => { setError(e); return null; }), [proyectoId, fase]);
  useEffect(() => { setVista(null); recargar(); }, [recargar]);
  useEffect(() => {
    if (!vista?.generando) return undefined;
    const t = setInterval(() => recargar().then((v) => { if (v && !v.generando) onCambio?.(); }), SONDEO_MS);
    return () => clearInterval(t);
  }, [vista?.generando, recargar, onCambio]);
  const guardar = useCallback(async (contenido) => {
    const v = await guardarFase(proyectoId, fase, contenido);
    setVista(v);
    onCambio?.();
    return v;
  }, [proyectoId, fase, onCambio]);
  const conservar = useCallback(async () => { setVista(await conservarFase(proyectoId, fase)); onCambio?.(); }, [proyectoId, fase, onCambio]);
  return { vista, setVista, error, recargar, guardar, conservar };
}

export function Desactualizado({ que, onRegenerar, onConservar }) {
  const [error, setError] = useState(null);
  return (
    <div className="tarjeta space-y-3 !border-[#ffc457]/40 px-5 py-4">
      <p className="text-[14.5px]">
        <b className="font-normal text-[#ffc457]">Lo de antes cambió</b> después de generar {que}: alguien corrigió el léxico o una fase anterior.
        Puedes volver a generarlo con lo nuevo o conservarlo tal como está.
      </p>
      <Aviso error={error} />
      <div className="flex flex-wrap gap-2">
        <button className="pill sm" onClick={onRegenerar}>Volver a generar</button>
        <button className="pill ghost sm" onClick={async () => { try { await onConservar(); } catch (e) { setError(e); } }}>Conservar así</button>
      </div>
    </div>
  );
}

export function Regenerar({ que, onConfirmar }) {
  const [preguntando, setPreguntando] = useState(false);
  if (!preguntando) {
    return <button className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setPreguntando(true)}>volver a generar</button>;
  }
  return (
    <Confirmar pregunta={`¿Volver a generar ${que}?`}
      detalle="Los agentes lo arman de nuevo con lo validado hasta ahora. Lo que editaste aquí se reemplaza (queda en el historial)."
      accion="Volver a generar" enviando="…" onCancelar={() => setPreguntando(false)}
      onConfirmar={async () => { setPreguntando(false); onConfirmar(); }} />
  );
}

export function SinGenerar({ disponible, motivo, titulo, texto, generando, onGenerar }) {
  return (
    <div className="tarjeta space-y-4 px-6 py-6">
      <p className="serif text-[26px] leading-tight">{titulo}</p>
      <p className="max-w-2xl text-[14.5px] leading-relaxed text-[var(--bone-dim)]">{texto}</p>
      {generando ? <p className="mono flex items-center gap-2 text-[10.5px] text-[var(--bone-dim)]"><span className="gira" /> El Modelador está trabajando…</p>
        : disponible ? <button className="pill" onClick={onGenerar}>Generar con los agentes</button>
          : <p className="text-[13.5px] text-[#ffc457]">{motivo}</p>}
    </div>
  );
}

export function Hecho({ texto, accion, onAccion }) {
  return (
    <div className="tarjeta flex flex-wrap items-center gap-4 !border-[#57f7a7]/40 px-5 py-4">
      <span className="punto" style={{ background: "#57f7a7", boxShadow: "0 0 12px #57f7a7" }} />
      <p className="min-w-0 flex-1 text-[14.5px]">{texto}</p>
      {accion && <button className="pill sm" onClick={onAccion}>{accion}</button>}
    </div>
  );
}

const ACCION = { generar: "Los agentes lo generaron", editar: "Lo editaste", conservar: "Lo conservaste aunque cambió lo de antes" };

export function Historial({ doc }) {
  if (!doc?.historial?.length) return null;
  return (
    <Plegable titulo="Historial" nota={`${doc.historial.length} · ${doc.modelo ?? ""}`}>
      <ol className="space-y-1.5 text-[12.5px] text-[var(--bone-dim)]">
        {[...doc.historial].reverse().map((h, i) => (
          <li key={i}>
            <span className="mono text-[9.5px] text-[var(--bone-faint)]">{h.fecha?.slice(0, 16).replace("T", " ")}</span>{" "}
            {ACCION[h.accion] ?? h.accion}{h.detalle ? ` · ${h.detalle}` : ""}{h.cambios?.length ? `: ${h.cambios.join("; ")}` : ""}
          </li>
        ))}
      </ol>
    </Plegable>
  );
}

export function Avisos({ avisos }) {
  if (!avisos?.length) return null;
  return (
    <Plegable titulo="Lo que revisó el código" nota={`${avisos.length} aviso${avisos.length === 1 ? "" : "s"}`}>
      <ul className="space-y-1 text-[13px] text-[var(--aviso)]">{avisos.map((a, i) => <li key={i}>{a}</li>)}</ul>
    </Plegable>
  );
}
