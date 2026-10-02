import { LECTURAS } from "../../constants/agentes";

/*
 * Evolución de la similitud: valor inicial y cierre de cada ronda contra el
 * umbral (línea punteada). SVG con viewBox: se adapta al ancho sin desbordar.
 */
export default function GraficaSimilitud({ inicial, rondas, umbral, maxRondas }) {
  const puntos = [{ etiqueta: "Inicial", valor: inicial }, ...rondas.map((r) => ({ etiqueta: `R${r.numero}`, valor: r.similitudCierre }))];
  const columnas = Math.max(maxRondas, rondas.length) + 1;
  const W = 540, H = 180, izq = 40, der = 44, arr = 22, abj = 28;
  const x = (i) => izq + (i * (W - izq - der)) / Math.max(1, columnas - 1);
  const y = (v) => arr + (1 - v) * (H - arr - abj);
  const ruta = puntos.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.valor)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full max-w-xl" role="img" aria-label="Similitud por ronda contra el umbral">
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line x1={izq} x2={W - der} y1={y(v)} y2={y(v)} stroke="#e2e8f0" />
          <text x={izq - 6} y={y(v) + 4} textAnchor="end" fontSize="10" fill="#94a3b8">{v.toFixed(2)}</text>
        </g>
      ))}
      <line x1={izq} x2={W - der} y1={y(umbral)} y2={y(umbral)} stroke="#0f172a" strokeDasharray="5 4" />
      <text x={izq + 4} y={y(umbral) - 5} fontSize="10" fill="#0f172a" fontWeight="600">umbral {umbral.toFixed(2)}</text>
      {Array.from({ length: columnas }, (_, i) => (
        <text key={i} x={x(i)} y={H - 8} textAnchor="middle" fontSize="11" fill={i < puntos.length ? "#334155" : "#cbd5e1"}>
          {i === 0 ? "Inicial" : `Ronda ${i}`}
        </text>
      ))}
      <path d={ruta} fill="none" stroke={LECTURAS.A.trazo} strokeWidth="2" />
      {puntos.map((p, i) => (
        <g key={i}>
          <circle cx={x(i)} cy={y(p.valor)} r="4.5" fill={p.valor >= umbral ? "#14b8a6" : "#f59e0b"} stroke="white" strokeWidth="1.5" />
          <text x={x(i) + (i === 0 ? 8 : 0)} y={y(p.valor) + (Math.abs(p.valor - umbral) < 0.15 && p.valor < umbral ? 16 : -9)} textAnchor={i === 0 ? "start" : "middle"} fontSize="11" fontWeight="600" fill="#0f172a">{p.valor.toFixed(2)}</text>
        </g>
      ))}
    </svg>
  );
}
