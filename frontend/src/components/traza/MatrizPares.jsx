import { colorInterpretacion } from "../../constants/agentes";

/*
 * Similitud coseno entre cada par de paráfrasis ("I1-I2": 0.41). La decisión
 * usa la mínima (marcada); el color va de divergente (cálido) a parecida (frío).
 */
const tono = (x, umbral) => {
  if (x == null) return "transparent";
  const t = Math.max(0, Math.min(1, x));
  return x >= umbral ? `rgba(52, 211, 153, ${0.18 + t * 0.5})` : `rgba(251, 191, 36, ${0.18 + (1 - t) * 0.55})`;
};

export default function MatrizPares({ pares = {}, parMinimo, umbral }) {
  const ids = [...new Set(Object.keys(pares).flatMap((k) => k.split("-")))].sort((a, b) => a.localeCompare(b, "es", { numeric: true }));
  if (ids.length < 2) return null;
  const valor = (a, b) => pares[`${a}-${b}`] ?? pares[`${b}-${a}`];
  const minimo = parMinimo ? new Set(parMinimo) : null;
  return (
    <table className="border-separate border-spacing-0.5 text-center font-mono text-[11px]">
      <thead>
        <tr>
          <th />
          {ids.map((b) => <th key={b} className="px-1 font-semibold" style={{ color: colorInterpretacion(b).trazo }}>{b}</th>)}
        </tr>
      </thead>
      <tbody>
        {ids.map((a) => (
          <tr key={a}>
            <th className="pr-1 text-right font-semibold" style={{ color: colorInterpretacion(a).trazo }}>{a}</th>
            {ids.map((b) => {
              if (a === b) return <td key={b} className="h-7 w-12 rounded text-slate-400">—</td>;
              const x = valor(a, b);
              const esMin = minimo && minimo.has(a) && minimo.has(b);
              return (
                <td key={b} title={`${a}–${b}: ${x?.toFixed(4)}`}
                  className={`h-7 w-12 rounded ${esMin ? "ring-2 ring-slate-900" : ""}`} style={{ background: tono(x, umbral) }}>
                  {x == null ? "" : x.toFixed(2)}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
