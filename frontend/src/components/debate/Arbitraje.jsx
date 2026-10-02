import { LECTURAS } from "../../constants/agentes";

/* Decisión del Crítico cuando se agotan las rondas sin consenso */
export default function Arbitraje({ arbitraje, rondas, maxRondas, umbral }) {
  const ultima = rondas.at(-1);
  const conteo = arbitraje.criterios.reduce((a, c) => ({ ...a, [c.favorece]: (a[c.favorece] ?? 0) + 1 }), {});
  const elegida = LECTURAS[arbitraje.eleccion];

  return (
    <article className="rounded-md border-2 border-orange-300 bg-orange-50/40">
      <header className="border-b border-orange-200 px-3 py-2">
        <h4 className="text-sm font-semibold text-orange-900">Arbitraje del Crítico</h4>
        <p className="text-sm text-orange-900">
          Se agotaron las {maxRondas} rondas y la similitud quedó en{" "}
          <strong className="font-mono">{ultima.similitudCierre.toFixed(2)}</strong>, por debajo del umbral{" "}
          <strong className="font-mono">{umbral.toFixed(2)}</strong>. Decide el Crítico
          {arbitraje.modelo && <> (<span className="font-mono text-xs">{arbitraje.modelo}</span>)</>}.
        </p>
      </header>
      <div className="space-y-3 p-3">
        <div>
          <p className="mb-1.5 text-xs font-bold uppercase tracking-wide text-slate-600">Criterios aplicados</p>
          <ol className="space-y-2">
            {arbitraje.criterios.map((c, i) => {
              const l = LECTURAS[c.favorece];
              return (
                <li key={i} className="flex gap-3 rounded bg-white p-2 ring-1 ring-slate-200">
                  <span className="font-mono text-sm font-bold text-slate-500">{i + 1}.</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold">{c.criterio}</p>
                    <p className="text-sm text-slate-700">{c.aplicacion}</p>
                  </div>
                  <span className={`h-fit shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold ${l ? `${l.fondo} ${l.texto}` : "bg-slate-100"}`}>
                    favorece {c.favorece}
                  </span>
                </li>
              );
            })}
          </ol>
          <p className="mt-2 text-xs text-slate-600">
            Recuento: {Object.entries(conteo).map(([k, n]) => `lectura ${k}: ${n}`).join(" · ")}
          </p>
        </div>
        <div className={`rounded border-l-4 ${elegida?.borde ?? "border-slate-400"} bg-white p-2.5`}>
          <p className="text-xs font-bold uppercase tracking-wide text-slate-600">
            Decisión: {elegida ? elegida.etiqueta : "síntesis"}
          </p>
          <p className="text-sm text-slate-900">{arbitraje.interpretacion}</p>
          <p className="mt-1 text-sm text-slate-600"><span className="font-semibold">Justificación:</span> {arbitraje.justificacion}</p>
        </div>
      </div>
    </article>
  );
}
