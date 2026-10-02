/*
 * Requisito con los términos ambiguos subrayados en el tono de su tipo,
 * para las pantallas oscuras del flujo (sin leyenda).
 */
export const TONO_AMBIGUEDAD = {
  mexicanismo: "#ffb347",
  vaguedad: "#c78bff",
  polisemia: "#5cc8ff",
};

export default function TextoMarcado({ texto, marcados = [], className = "" }) {
  const partes = [];
  let cursor = 0;
  marcados.forEach((m, i) => {
    if (m.inicio < cursor) return;
    if (m.inicio > cursor) partes.push(texto.slice(cursor, m.inicio));
    const tono = TONO_AMBIGUEDAD[m.tipo] ?? "#efe9de";
    partes.push(
      <span
        key={i}
        title={`${m.tipo} · ${m.fuente}`}
        className="marcado"
        style={{ "--tono": tono }}
      >
        {texto.slice(m.inicio, m.fin)}
      </span>
    );
    cursor = m.fin;
  });
  partes.push(texto.slice(cursor));
  return <span className={className}>{partes}</span>;
}
