/*
 * Bloque numerado de la traza. `estado`:
 *   "hecho"     etapa completada
 *   "curso"     los agentes están trabajando en ella
 *   "pendiente" todavía no llega
 *   "omitida"   no aplica en este camino (p. ej., debate en aceptación directa)
 */
const ESTILO = {
  hecho: "border-slate-300 bg-white",
  curso: "border-amber-300 bg-white",
  pendiente: "border-dashed border-slate-300 bg-slate-50 text-slate-400",
  omitida: "border-dashed border-slate-300 bg-slate-50",
};

export default function Etapa({ numero, titulo, agente, meta, estado = "hecho", id, children }) {
  return (
    <section id={id} className={`scroll-mt-4 rounded-lg border ${ESTILO[estado]}`}>
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-inherit px-4 py-2.5">
        <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${estado === "hecho" ? "bg-slate-900 text-sobre" : "bg-slate-200 text-slate-600"}`}>
          {numero}
        </span>
        <h2 className="text-sm font-semibold uppercase tracking-wide">{titulo}</h2>
        {agente && <span className="text-sm text-slate-500">{agente}</span>}
        {meta && <span className="ml-auto font-mono text-xs text-slate-400">{meta}</span>}
      </header>
      <div className="px-4 py-4">
        {estado === "pendiente" && <p className="text-sm">Pendiente: esta etapa aún no se ejecuta.</p>}
        {estado === "curso" && (
          <p className="flex items-center gap-2 text-sm text-amber-700">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            Los agentes están trabajando en esta etapa…
          </p>
        )}
        {(estado === "hecho" || estado === "omitida") && children}
      </div>
    </section>
  );
}
