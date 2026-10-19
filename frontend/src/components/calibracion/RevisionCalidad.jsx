import { useCallback, useEffect, useMemo, useState } from "react";
import { empezarRevisionCalidad, marcarCalidad, rehacerRevisionCalidad, revisionCalidad } from "../../services/backend";
import { Aviso, Cargando, Confirmar, Plegable } from "../ui";
import RevisionFuera from "./RevisionFuera";
import Rubrica from "./Rubrica";

/*
 * Revisión de la calidad de las salidas del Clasificador (ADR 0029), pensada para el teclado:
 *   1, 2, 3   alternan fidelidad, delimitación e intención
 *   4, 5, 6   marcan qué lecturas esperadas cubrió la salida (solo en los ítems ambiguos)
 *   Enter     guarda y pasa a la siguiente · Backspace regresa · ? abre la rúbrica
 * Es a ciegas por omisión: no se muestra proveedor ni modelo, y el orden (ítems y, dentro de cada
 * ítem, modelos) viene barajado del servidor con una semilla guardada. Cada salida se guarda al
 * avanzar, así que se puede dejar a medias y retomar donde quedó.
 * La detección (si marcó «ambiguo») no se revisa aquí: se mide sola contra el banco.
 * Abajo, «Revisar fuera del sistema» exporta lo mismo a un archivo que contesta una persona o una
 * IA, y lo importa (ADR 0030).
 */
const CLAVE_ANOTADOR = "dudamel.anotador";
const leer = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const CRITERIOS = [
  { clave: "fidelidad", nombre: "Fidelidad", tecla: "1" },
  { clave: "delimitacion", nombre: "Delimitación", tecla: "2" },
  { clave: "intencion", nombre: "Intención", tecla: "3" },
];
const vacia = () => ({ fidelidad: false, delimitacion: false, intencion: false, cobertura: [] });

export default function RevisionCalidad({ prueba, banco, onCambio }) {
  const [doc, setDoc] = useState(undefined); // undefined: cargando; null: sin empezar
  const [error, setError] = useState(null);
  const recargar = useCallback(() => revisionCalidad(prueba.prueba_id).then(setDoc).catch(setError), [prueba.prueba_id]);
  useEffect(() => { recargar(); }, [recargar]);

  if (error) return <Aviso error={error} />;
  if (doc === undefined) return <Cargando>Cargando la revisión…</Cargando>;
  if (prueba.estado === "en_proceso") return <p className="text-[13.5px] text-[var(--bone-dim)]">La prueba sigue corriendo: la revisión se abre cuando termine.</p>;
  return (
    <div className="space-y-6">
      {doc
        ? <Revisar prueba={prueba} banco={banco} doc={doc} setDoc={setDoc} onCambio={onCambio} onRehecha={() => { setDoc(null); onCambio(); }} />
        : <Empezar prueba={prueba} onEmpezada={(d) => { setDoc(d); onCambio(); }} />}
      <Plegable titulo="Revisar fuera del sistema" nota="exportar a una IA o a una persona e importar lo que conteste"
        className="border-t border-[var(--line)] pt-2" alAbrir>
        <RevisionFuera prueba={prueba} doc={doc} onImportado={() => { recargar(); onCambio(); }} />
      </Plegable>
    </div>
  );
}

function Empezar({ prueba, onEmpezada }) {
  const [revisor, setRevisor] = useState(() => leer(CLAVE_ANOTADOR, ""));
  const [conNombres, setConNombres] = useState(false);
  const [error, setError] = useState(null);
  const empezar = async () => {
    try {
      try { localStorage.setItem(CLAVE_ANOTADOR, revisor.trim()); } catch { /* sin almacenamiento */ }
      onEmpezada(await empezarRevisionCalidad(prueba.prueba_id, { revisor: revisor.trim(), a_ciegas: !conNombres }));
    } catch (e) { setError(e); }
  };
  return (
    <div className="tarjeta max-w-2xl space-y-4 p-5">
      <p className="text-[14px] text-[var(--bone-dim)]">
        Vas a revisar la factura de cada salida con tres criterios (fidelidad, delimitación e intención) y, en los términos
        ambiguos, qué lecturas esperadas cubrió. Sin ver qué modelo la produjo y en un orden barajado. Se guarda al avanzar:
        puedes dejarla a medias y retomarla.
      </p>
      <label className="block">
        <span className="etiqueta mb-1 block">Revisor</span>
        <input value={revisor} onChange={(e) => setRevisor(e.target.value)} maxLength={120} placeholder="Tu nombre" className="campo w-64 text-[14px]" />
      </label>
      <label className="flex cursor-pointer items-center gap-2 text-[13px] text-[var(--bone-dim)]">
        <input type="checkbox" checked={conNombres} onChange={(e) => setConNombres(e.target.checked)} />
        Revisar con los nombres de los modelos a la vista (no ciega: el resumen lo dirá)
      </label>
      <Aviso error={error} />
      <button className="pill sm" disabled={!revisor.trim()} onClick={empezar}>Empezar la revisión</button>
    </div>
  );
}

function Revisar({ prueba, banco, doc, setDoc, onCambio, onRehecha }) {
  const terminos = useMemo(() => Object.fromEntries(banco.terminos.map((t) => [t.id, t])), [banco]);
  const nombres = useMemo(() => Object.fromEntries(prueba.modelos.map((m) => [m.id, `${m.proveedor} · ${m.modelo}`])), [prueba]);
  const orden = doc.orden;
  const marcada = (o) => doc.marcas?.[o.modelo]?.[o.item];
  const [i, setI] = useState(() => Math.max(0, orden.findIndex((o) => !marcada(o))) );
  const [borrador, setBorrador] = useState(vacia);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [ayuda, setAyuda] = useState(false);
  const [rehacer, setRehacer] = useState(false);
  const revisadas = orden.filter(marcada).length;
  const actual = orden[i];
  const t = actual ? terminos[actual.item] : null;
  const r = actual ? prueba.resultados[actual.modelo]?.[actual.item] : null;
  const ambiguo = t ? (t.ambiguo ?? t.clase !== "inequivoco") : false;

  // al llegar a una salida, el borrador es lo ya guardado (o vacío)
  useEffect(() => {
    const m = actual && marcada(actual);
    setBorrador(m ? { fidelidad: m.fidelidad, delimitacion: m.delimitacion, intencion: m.intencion, cobertura: m.cobertura ?? [] } : vacia());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i, doc]);

  const guardarYSeguir = useCallback(async () => {
    if (!actual || guardando) return;
    setGuardando(true);
    setError(null);
    try {
      const { marca } = await marcarCalidad(prueba.prueba_id, { modelo: actual.modelo, item: actual.item, ...borrador, nota: null });
      setDoc((d) => ({ ...d, marcas: { ...d.marcas, [actual.modelo]: { ...(d.marcas?.[actual.modelo] ?? {}), [actual.item]: marca } } }));
      onCambio();
      setI((k) => Math.min(orden.length, k + 1));
    } catch (e) { setError(e); } finally { setGuardando(false); }
  }, [actual, borrador, guardando, orden.length, prueba.prueba_id, setDoc, onCambio]);

  useEffect(() => {
    const tecla = (e) => {
      if (e.target.closest?.("input, textarea, select") || e.metaKey || e.ctrlKey || e.altKey) return;
      const c = CRITERIOS.find((x) => x.tecla === e.key);
      if (c && actual) { e.preventDefault(); setBorrador((b) => ({ ...b, [c.clave]: !b[c.clave] })); return; }
      const lectura = { 4: 0, 5: 1, 6: 2 }[e.key];
      if (lectura != null && ambiguo && t && lectura < t.lecturas.length) {
        e.preventDefault();
        setBorrador((b) => ({ ...b, cobertura: b.cobertura.includes(lectura) ? b.cobertura.filter((x) => x !== lectura) : [...b.cobertura, lectura].sort() }));
        return;
      }
      if (e.key === "Enter") { e.preventDefault(); guardarYSeguir(); }
      else if (e.key === "Backspace" || e.key === "ArrowLeft") { e.preventDefault(); setI((k) => Math.max(0, k - 1)); }
      else if (e.key === "ArrowRight") { e.preventDefault(); setI((k) => Math.min(orden.length, k + 1)); }
      else if (e.key === "?") { e.preventDefault(); setAyuda((a) => !a); }
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [actual, ambiguo, t, guardarYSeguir, orden.length]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="mono text-[11px] text-[var(--bone)]">{revisadas} / {orden.length} revisadas</span>
        <div className="h-1.5 min-w-[10rem] flex-1 overflow-hidden rounded-full bg-[color-mix(in_oklab,var(--bone)_10%,transparent)]">
          <div className="h-full rounded-full bg-[var(--c1)]" style={{ width: `${(revisadas / Math.max(1, orden.length)) * 100}%` }} />
        </div>
        <span className="mono text-[10px] text-[var(--bone-faint)]">
          {doc.revisor} · {doc.a_ciegas ? "a ciegas" : "con nombres visibles"} · semilla {doc.semilla}
        </span>
        <button className="pill ghost sm" onClick={() => setAyuda((a) => !a)} aria-expanded={ayuda}>Rúbrica (?)</button>
        <button className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--danger)]" onClick={() => setRehacer(true)}>rehacer</button>
      </div>

      <div className={`grid gap-5 ${ayuda ? "lg:grid-cols-[minmax(0,1fr)_22rem]" : ""}`}>
        {actual ? (
          <article className="tarjeta space-y-4 p-5" aria-live="polite">
            <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="mono text-[10px] text-[var(--bone-faint)]">salida {i + 1} de {orden.length} · {actual.item}</span>
              <h3 className="text-[19px] text-[var(--bone)]">{t.termino}</h3>
              <span className="text-[12.5px] text-[var(--bone-faint)]">{t.dominio}</span>
              {!doc.a_ciegas && <span className="mono ml-auto text-[10px] text-[var(--bone-dim)]">{nombres[actual.modelo]}</span>}
              {marcada(actual) && (
                <span className="mono text-[10px] text-[var(--bone-faint)]">
                  ya revisada{marcada(actual).origen ? ` · importada (${marcada(actual).origen.tipo === "ia" ? "IA" : "persona"}: ${marcada(actual).origen.quien})` : ""}
                </span>
              )}
            </header>
            <p className="text-[13.5px] text-[var(--bone-dim)]">«{t.cita}»</p>

            <section className="space-y-2 border-t border-[var(--line)] pt-3">
              <p className="etiqueta">Lo que escribió el modelo · {r.intenciones.length === 1 ? "una intención" : `${r.intenciones.length} intenciones`}</p>
              <ol className="space-y-2.5">
                {r.intenciones.map((x) => (
                  <li key={x.id} className="space-y-0.5 text-[13.5px]">
                    <p><span className="mono mr-2 text-[10px] text-[var(--bone-faint)]">{x.id}</span><span className="text-[var(--bone)]">{x.significado}</span></p>
                    <p className="pl-7 text-[12.5px] text-[var(--bone-dim)]"><span className="etiqueta mr-1.5">intención</span>{x.intencion}</p>
                    <p className="pl-7 text-[12.5px] text-[var(--bone-dim)]"><span className="etiqueta mr-1.5">paráfrasis</span>«{x.parafrasis}»</p>
                  </li>
                ))}
              </ol>
            </section>

            <section className="grid gap-4 border-t border-[var(--line)] pt-3 md:grid-cols-2">
              <div className="space-y-2">
                <p className="etiqueta">Criterios (cumple si lo cumplen todas las intenciones)</p>
                {CRITERIOS.map((c) => (
                  <Casilla key={c.clave} tecla={c.tecla} activa={borrador[c.clave]} onClick={() => setBorrador((b) => ({ ...b, [c.clave]: !b[c.clave] }))}>
                    {c.nombre}
                  </Casilla>
                ))}
              </div>
              {ambiguo && (
                <div className="space-y-2">
                  <p className="etiqueta">Lecturas esperadas que aparecen</p>
                  {t.lecturas.map((l, k) => (
                    <Casilla key={l} tecla={String(4 + k)} activa={borrador.cobertura.includes(k)}
                      onClick={() => setBorrador((b) => ({ ...b, cobertura: b.cobertura.includes(k) ? b.cobertura.filter((x) => x !== k) : [...b.cobertura, k].sort() }))}>
                      {l}
                    </Casilla>
                  ))}
                </div>
              )}
            </section>

            <Aviso error={error} />
            <footer className="flex flex-wrap items-center gap-2 border-t border-[var(--line)] pt-3">
              <button className="pill ghost sm" disabled={i === 0} onClick={() => setI((k) => Math.max(0, k - 1))}>← Anterior <span className="opacity-60">⌫</span></button>
              <button className="pill sm" disabled={guardando} onClick={guardarYSeguir}>{guardando ? "Guardando…" : "Guardar y seguir"} <span className="opacity-60">↵</span></button>
              <span className="mono ml-auto text-[10px] text-[var(--bone-faint)]">1 2 3 criterios · {ambiguo ? "4 5 6 lecturas · " : ""}? rúbrica</span>
            </footer>
          </article>
        ) : (
          <div className="tarjeta space-y-3 p-5">
            <p className="text-[15px] text-[var(--bone)]">{revisadas === orden.length ? "Revisión completa." : "Llegaste al final del orden."}</p>
            <p className="text-[13px] text-[var(--bone-dim)]">{revisadas} de {orden.length} salidas revisadas. Puedes regresar con ⌫ para corregir cualquiera.</p>
            {revisadas < orden.length && (
              <button className="pill ghost sm" onClick={() => setI(Math.max(0, orden.findIndex((o) => !marcada(o))))}>Ir a la primera sin revisar</button>
            )}
          </div>
        )}
        {ayuda && <Rubrica onCerrar={() => setAyuda(false)} />}
      </div>

      {rehacer && (
        <Confirmar pregunta="¿Borrar esta revisión de calidad y empezar de nuevo?" accion="Borrar la revisión"
          detalle="Se borran las marcas de calidad y de cobertura; las respuestas de los modelos no se tocan. Una revisión con el criterio viejo (✓/✗ de la v2.3), si existe, tampoco."
          onCancelar={() => setRehacer(false)}
          onConfirmar={async () => { await rehacerRevisionCalidad(prueba.prueba_id); setRehacer(false); onRehecha(); }} />
      )}
    </div>
  );
}

function Casilla({ tecla, activa, onClick, children }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={activa}
      className={`flex w-full items-start gap-3 rounded-xl border px-3 py-2 text-left text-[13.5px] transition-colors ${activa
        ? "border-[color-mix(in_oklab,var(--c1)_60%,var(--line))] bg-[color-mix(in_oklab,var(--c1)_14%,transparent)] text-[var(--bone)]"
        : "border-[var(--line)] text-[var(--bone-dim)] hover:text-[var(--bone)]"}`}>
      <kbd className="mono mt-0.5 min-w-[1.4rem] rounded-md border border-[var(--line)] px-1.5 text-center text-[10.5px]">{tecla}</kbd>
      <span className="flex-1">{children}</span>
      <span className="mono text-[11px]" aria-hidden="true">{activa ? "sí" : "no"}</span>
    </button>
  );
}
