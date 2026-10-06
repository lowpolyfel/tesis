/*
 * Requisito con los términos ambiguos subrayados en el tono de su tipo,
 * para las pantallas oscuras del flujo (sin leyenda).
 */
export const TONO_AMBIGUEDAD = {
  lexica: "#5cc8ff",
  alcance: "#8f9bff",
  anaforica: "#ef8cf5",
  sintactica: "#4fe0f0",
  vaguedad: "#c78bff",
  regional: "#ffb347",
  lel: "#57f7a7",
};

export default function TextoMarcado({ texto, marcados = [], className = "" }) {
  const partes = [];
  let cursor = 0;
  [...marcados].sort((a, b) => a.inicio - b.inicio || b.fin - a.fin).forEach((m, i) => {
    if (m.inicio < cursor || m.fin <= m.inicio) return;
    if (m.inicio > cursor) partes.push(texto.slice(cursor, m.inicio));
    const tono = TONO_AMBIGUEDAD[m.tipo] ?? "#efe9de";
    partes.push(
      <span
        key={i}
        title={[m.tipo, m.detalle ?? m.fuente].filter(Boolean).join(" · ")}
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
