import { rubricaRevision } from "../../services/backend";
import { useApi } from "../../hooks/useApi";
import { Aviso, Cargando } from "../ui";

/*
 * La rúbrica de la revisión humana (ADR 0029) en un panel lateral. Sale del mismo origen que el
 * apéndice de la tesis (backend/app/calibracion/rubrica.py → docs/rubrica-revision.md), así que lo
 * que se ve aquí es exactamente lo que se le entrega a un segundo anotador.
 * `tipo`: "calidad" (prueba de modelos) o "entrevista" (etiquetado de términos).
 */
export default function Rubrica({ tipo = "calidad", onCerrar }) {
  const { datos: r, error } = useApi(rubricaRevision, []);
  return (
    <aside className="tarjeta max-h-[78vh] space-y-4 overflow-y-auto p-4 text-[13px] lg:sticky lg:top-24" aria-label="Rúbrica">
      <div className="flex items-baseline gap-3">
        <p className="text-[15px] text-[var(--bone)]">Rúbrica</p>
        {onCerrar && <button className="mono ml-auto text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={onCerrar}>cerrar (?)</button>}
      </div>
      <Aviso error={error} />
      {!r && !error && <Cargando>Cargando la rúbrica…</Cargando>}
      {r && tipo === "calidad" && (
        <>
          <p className="text-[var(--bone-dim)]">{r.regla_agregado}</p>
          {r.criterios.map((c) => (
            <section key={c.clave} className="space-y-1">
              <p className="text-[var(--bone)]"><kbd className="mono mr-2 rounded border border-[var(--line)] px-1.5 text-[10.5px]">{c.tecla}</kbd>{c.nombre}</p>
              <p className="text-[var(--bone-dim)]">{c.oracion}</p>
              <p className="text-[12px] text-[var(--bone-faint)]"><b className="font-medium text-[var(--bone-dim)]">Pasa:</b> {c.pasa}</p>
              <p className="text-[12px] text-[var(--bone-faint)]"><b className="font-medium text-[var(--bone-dim)]">No pasa:</b> {c.no_pasa}</p>
            </section>
          ))}
          <section className="space-y-1">
            <p className="text-[var(--bone)]"><kbd className="mono mr-2 rounded border border-[var(--line)] px-1.5 text-[10.5px]">4–6</kbd>{r.cobertura.nombre}</p>
            <p className="text-[var(--bone-dim)]">{r.cobertura.oracion}</p>
            <p className="text-[12px] text-[var(--bone-faint)]"><b className="font-medium text-[var(--bone-dim)]">Pasa:</b> {r.cobertura.pasa}</p>
            <p className="text-[12px] text-[var(--bone-faint)]"><b className="font-medium text-[var(--bone-dim)]">No pasa:</b> {r.cobertura.no_pasa}</p>
          </section>
        </>
      )}
      {r && tipo === "entrevista" && (
        <section className="space-y-2">
          <p className="text-[var(--bone-dim)]">{r.etiqueta_entrevista.oracion}</p>
          {[["si", "Sí"], ["no", "No"], ["no_se", "No sé"]].map(([k, nombre]) => (
            <p key={k} className="text-[12.5px] text-[var(--bone-faint)]">
              <kbd className="mono mr-2 rounded border border-[var(--line)] px-1.5 text-[10.5px]">{r.etiqueta_entrevista.teclas[k]}</kbd>
              <b className="font-medium text-[var(--bone-dim)]">{nombre}:</b> {r.etiqueta_entrevista[k]}
            </p>
          ))}
        </section>
      )}
    </aside>
  );
}
