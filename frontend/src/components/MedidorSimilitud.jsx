/*
 * Similitud coseno contra el umbral, dicho explícitamente en texto y
 * dibujado en una barra de 0 a 1 con la marca del umbral.
 */
export default function MedidorSimilitud({ similitud, umbral, modelo }) {
  const arriba = similitud >= umbral;
  return (
    <div className="space-y-3">
      <div className="relative h-7 rounded bg-slate-100" role="img" aria-label={`Similitud ${similitud.toFixed(2)}, umbral ${umbral.toFixed(2)}`}>
        <div
          className={`h-full rounded ${arriba ? "bg-teal-500" : "bg-amber-500"}`}
          style={{ width: `${similitud * 100}%` }}
        />
        <div className="absolute inset-y-[-4px] w-0.5 bg-slate-900" style={{ left: `${umbral * 100}%` }} />
        <span className="absolute -top-5 -translate-x-1/2 text-xs font-medium text-slate-700" style={{ left: `${umbral * 100}%` }}>
          umbral {umbral.toFixed(2)}
        </span>
        <span className="absolute inset-y-0 left-2 flex items-center font-mono text-sm font-semibold text-white">
          {similitud.toFixed(2)}
        </span>
      </div>
      <div className="flex justify-between font-mono text-[11px] text-slate-400">
        <span>0.00</span><span>0.50</span><span>1.00</span>
      </div>
      <p className={`rounded px-3 py-2 text-sm ${arriba ? "bg-teal-50 text-teal-900" : "bg-amber-50 text-amber-900"}`}>
        Similitud coseno <strong className="font-mono">{similitud.toFixed(2)}</strong>{" "}
        {arriba ? "≥" : "<"} umbral <strong className="font-mono">{umbral.toFixed(2)}</strong>:{" "}
        <strong>{arriba ? "POR ARRIBA del umbral" : "POR DEBAJO del umbral"}</strong>.{" "}
        {arriba
          ? "Las interpretaciones se consideran equivalentes: el requisito se acepta sin debate."
          : "Las interpretaciones divergen: se activa el debate entre agentes."}
      </p>
      {modelo && <p className="text-xs text-slate-500">Embeddings: <span className="font-mono">{modelo}</span>. La divergencia es un mecanismo aparte, no un agente.</p>}
    </div>
  );
}
