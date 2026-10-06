/*
 * Similitud mínima entre interpretaciones al inicio y tras cada ronda, contra
 * el umbral. Un punto sin valor (null) significa que quedó una sola
 * interpretación: no hay nada que comparar.
 */
export default function GraficaRondas({ inicial, rondas = [], umbral }) {
  const puntos = [{ etiqueta: "inicio", valor: inicial }, ...rondas.map((r) => ({ etiqueta: `r${r.ronda}`, valor: r.similitud?.similitud ?? null }))];
  if (puntos.length < 2 || umbral == null) return null;
  const W = 260, H = 110, m = { l: 30, r: 10, t: 10, b: 22 };
  const x = (i) => m.l + (i * (W - m.l - m.r)) / (puntos.length - 1);
  const y = (v) => m.t + (1 - v) * (H - m.t - m.b);
  const conValor = puntos.map((p, i) => ({ ...p, i })).filter((p) => p.valor != null);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-xs" role="img" aria-label="Similitud por ronda">
      {[0, 0.5, 1].map((v) => (
        <g key={v}>
          <line x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} stroke="currentColor" className="text-slate-200" />
          <text x={m.l - 4} y={y(v) + 3} textAnchor="end" fontSize="9" className="fill-slate-500">{v.toFixed(1)}</text>
        </g>
      ))}
      <line x1={m.l} x2={W - m.r} y1={y(umbral)} y2={y(umbral)} stroke="#fbbf24" strokeDasharray="4 3" />
      <text x={W - m.r} y={y(umbral) - 3} textAnchor="end" fontSize="9" fill="#fbbf24">umbral {umbral}</text>
      <polyline fill="none" stroke="#a78bfa" strokeWidth="2" points={conValor.map((p) => `${x(p.i)},${y(p.valor)}`).join(" ")} />
      {puntos.map((p, i) => (
        <g key={p.etiqueta}>
          {p.valor != null
            ? <circle cx={x(i)} cy={y(p.valor)} r="3.5" fill={p.valor >= umbral ? "#34d399" : "#fbbf24"}><title>{`${p.etiqueta}: ${p.valor.toFixed(3)}`}</title></circle>
            : <text x={x(i)} y={y(0.5)} textAnchor="middle" fontSize="9" className="fill-slate-500">1 sola</text>}
          <text x={x(i)} y={H - 6} textAnchor="middle" fontSize="9" className="fill-slate-500">{p.etiqueta}</text>
        </g>
      ))}
    </svg>
  );
}
