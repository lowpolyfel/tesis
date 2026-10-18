import { useCallback, useEffect, useState } from "react";
import { useApi } from "../../hooks/useApi";
import { anotacion, anotacionesEntrevista, empezarAnotacion, responderAnotacion } from "../../services/backend";
import { Aviso, Cargando } from "../ui";
import Rubrica from "./Rubrica";

/*
 * Etiquetado de los términos de una entrevista (ADR 0029): el ground truth de la calibración.
 *   S sí es ambiguo · N no · X no sé · Backspace regresa · ? abre la rúbrica
 * A ciegas siempre: aquí nunca se muestran la similitud ni la decisión del sistema, solo el término,
 * sus citas y el contexto del proyecto. Cada persona tiene su propio etiquetado, en un orden
 * barajado que se guardó con su semilla; cada respuesta se guarda al darla, así que se puede dejar
 * a medias. Con dos o más personas, la calibración usa los términos en que coinciden y calcula la
 * kappa de Cohen entre cada par.
 */
const CLAVE_ANOTADOR = "dudamel.anotador";
const leer = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const RESPUESTAS = [
  { clave: "si", texto: "Sí, es ambiguo", tecla: "S" },
  { clave: "no", texto: "No", tecla: "N" },
  { clave: "no_se", texto: "No sé", tecla: "X" },
];
const TEXTO = { si: "sí", no: "no", no_se: "no sé" };
const fmt = (x) => (x == null ? "—" : x.toFixed(2));

export default function EtiquetarEntrevista({ entrevistaId, onCambio, onCerrar }) {
  const resumen_ = useApi(() => anotacionesEntrevista(entrevistaId), [entrevistaId]);
  const [aid, setAid] = useState(null);
  const [anotador, setAnotador] = useState(() => leer(CLAVE_ANOTADOR, ""));
  const [error, setError] = useState(null);

  const empezar = async (nombre) => {
    setError(null);
    try {
      try { localStorage.setItem(CLAVE_ANOTADOR, nombre.trim()); } catch { /* sin almacenamiento */ }
      const a = await empezarAnotacion(entrevistaId, { anotador: nombre.trim() });
      setAid(a.anotacion_id);
    } catch (e) { setError(e); }
  };

  if (aid) return <Sesion anotacionId={aid} onCambio={() => { onCambio(); resumen_.recargar(); }} onSalir={() => { setAid(null); resumen_.recargar(); }} />;
  const r = resumen_.datos;
  return (
    <div className="space-y-4 border-t border-[var(--line)] pt-4">
      <Aviso error={error || resumen_.error} />
      {!r && !resumen_.error && <Cargando>Cargando quién etiquetó…</Cargando>}
      {r && (
        <>
          <p className="text-[13px] text-[var(--bone-dim)]">
            {r.n_terminos} términos llegaron al mecanismo de divergencia. Se etiquetan a ciegas: sin ver la similitud ni la decisión del sistema.
          </p>
          {(r.anotaciones.length > 0 || r.legado) && (
            <table className="tabla-viz max-w-2xl">
              <thead><tr><th>Persona</th><th>Avance</th><th>Sí / No / No sé</th><th /></tr></thead>
              <tbody>
                {r.anotaciones.map((a) => (
                  <tr key={a.anotacion_id}>
                    <td className="text-[var(--bone)]">{a.anotador}</td><td>{a.hechas}/{a.total}</td>
                    <td>{a.por_respuesta.si} / {a.por_respuesta.no} / {a.por_respuesta.no_se}</td>
                    <td className="text-right"><button className="pill ghost sm" onClick={() => setAid(a.anotacion_id)}>Retomar</button></td>
                  </tr>
                ))}
                {r.legado && <tr><td className="text-[var(--bone-dim)]">{r.legado.anotador} (v2.2)</td><td>{r.legado.n_etiquetas}</td><td>—</td><td /></tr>}
              </tbody>
            </table>
          )}
          {r.acuerdo.length > 0 && (
            <p className="text-[12.5px] text-[var(--bone-dim)]">
              Acuerdo: {r.acuerdo.map((k) => `${k.a} / ${k.b}: κ = ${fmt(k.kappa)} (${k.n} términos, ${fmt(k.acuerdo_observado)} de acuerdo)`).join(" · ")}
            </p>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <label className="block">
              <span className="etiqueta mb-1 block">Quién etiqueta</span>
              <input value={anotador} onChange={(e) => setAnotador(e.target.value)} maxLength={120} placeholder="Tu nombre" className="campo w-56 text-[14px]" />
            </label>
            <button className="pill sm" disabled={!anotador.trim() || !r.n_terminos} onClick={() => empezar(anotador)}>Etiquetar</button>
            <button className="pill ghost sm" onClick={onCerrar}>Cerrar</button>
          </div>
        </>
      )}
    </div>
  );
}

function Sesion({ anotacionId, onCambio, onSalir }) {
  const [a, setA] = useState(null);
  const [error, setError] = useState(null);
  const [i, setI] = useState(0);
  const [ayuda, setAyuda] = useState(false);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    anotacion(anotacionId).then((d) => {
      setA(d);
      const primera = d.terminos.findIndex((t) => !d.respuestas[t.clave]);
      setI(primera < 0 ? d.terminos.length : primera);
    }).catch(setError);
  }, [anotacionId]);

  const responder = useCallback(async (respuesta) => {
    const t = a?.terminos[i];
    if (!t || guardando) return;
    setGuardando(true);
    setError(null);
    try {
      const r = await responderAnotacion(anotacionId, t.termino, respuesta);
      setA((x) => ({ ...x, respuestas: r.respuestas }));
      onCambio();
      setI((k) => k + 1);
    } catch (e) { setError(e); } finally { setGuardando(false); }
  }, [a, i, guardando, anotacionId, onCambio]);

  useEffect(() => {
    const tecla = (e) => {
      if (e.target.closest?.("input, textarea, select") || e.metaKey || e.ctrlKey || e.altKey) return;
      const r = RESPUESTAS.find((x) => x.tecla.toLowerCase() === e.key.toLowerCase());
      if (r) { e.preventDefault(); responder(r.clave); }
      else if (e.key === "Backspace" || e.key === "ArrowLeft") { e.preventDefault(); setI((k) => Math.max(0, k - 1)); }
      else if (e.key === "ArrowRight") { e.preventDefault(); setI((k) => Math.min(a?.terminos.length ?? 0, k + 1)); }
      else if (e.key === "?") { e.preventDefault(); setAyuda((x) => !x); }
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [responder, a]);

  if (error && !a) return <Aviso error={error} />;
  if (!a) return <Cargando>Cargando los términos…</Cargando>;
  const total = a.terminos.length;
  const hechas = a.terminos.filter((t) => a.respuestas[t.clave]).length;
  const t = a.terminos[i];
  const dada = t ? a.respuestas[t.clave]?.respuesta : null;

  return (
    <div className="space-y-4 border-t border-[var(--line)] pt-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="mono text-[11px] text-[var(--bone)]">{hechas} / {total} etiquetados</span>
        <div className="h-1.5 min-w-[10rem] flex-1 overflow-hidden rounded-full bg-[color-mix(in_oklab,var(--bone)_10%,transparent)]">
          <div className="h-full rounded-full bg-[var(--c1)]" style={{ width: `${(hechas / Math.max(1, total)) * 100}%` }} />
        </div>
        <span className="mono text-[10px] text-[var(--bone-faint)]">{a.anotador} · a ciegas · semilla {a.semilla}</span>
        <button className="pill ghost sm" onClick={() => setAyuda((x) => !x)} aria-expanded={ayuda}>Rúbrica (?)</button>
        <button className="pill ghost sm" onClick={onSalir}>Volver a la lista</button>
      </div>
      <div className={`grid gap-5 ${ayuda ? "lg:grid-cols-[minmax(0,1fr)_20rem]" : ""}`}>
        {t ? (
          <article className="tarjeta space-y-4 p-5" aria-live="polite">
            <header className="flex flex-wrap items-baseline gap-x-3">
              <span className="mono text-[10px] text-[var(--bone-faint)]">término {i + 1} de {total}</span>
              <h3 className="text-[19px] text-[var(--bone)]">{t.termino}</h3>
              {dada && <span className="mono text-[10px] text-[var(--bone-faint)]">ya respondido: {TEXTO[dada]}</span>}
            </header>
            {a.contexto && <p className="text-[12.5px] text-[var(--bone-faint)]"><span className="etiqueta mr-1.5">contexto</span>{a.contexto}</p>}
            <ul className="space-y-2">
              {t.citas.map((c) => (
                <li key={c.turno} className="text-[13.5px] text-[var(--bone-dim)]">
                  <span className="mono mr-2 text-[10px] text-[var(--bone-faint)]">T{c.turno}{c.hablante ? ` · ${c.hablante}` : ""}</span>«{c.fragmento}»
                </li>
              ))}
              {!t.citas.length && <li className="text-[12.5px] text-[var(--bone-faint)]">(sin citas registradas)</li>}
            </ul>
            <p className="text-[13px] text-[var(--bone)]">¿Admite más de una lectura razonable en este dominio?</p>
            <Aviso error={error} />
            <div className="flex flex-wrap gap-2">
              {RESPUESTAS.map((r) => (
                <button key={r.clave} type="button" disabled={guardando} onClick={() => responder(r.clave)} aria-pressed={dada === r.clave}
                  className={`pill sm ${dada === r.clave ? "" : "ghost"}`}>
                  <kbd className="mono mr-1.5 opacity-70">{r.tecla}</kbd>{r.texto}
                </button>
              ))}
              <button className="pill ghost sm ml-auto" disabled={i === 0} onClick={() => setI((k) => Math.max(0, k - 1))}>← Anterior <span className="opacity-60">⌫</span></button>
            </div>
          </article>
        ) : (
          <div className="tarjeta space-y-2 p-5">
            <p className="text-[15px] text-[var(--bone)]">{hechas === total ? "Etiquetado completo." : "Llegaste al final."}</p>
            <p className="text-[13px] text-[var(--bone-dim)]">{hechas} de {total} términos. Puedes regresar con ⌫ para corregir.</p>
          </div>
        )}
        {ayuda && <Rubrica tipo="entrevista" onCerrar={() => setAyuda(false)} />}
      </div>
    </div>
  );
}
