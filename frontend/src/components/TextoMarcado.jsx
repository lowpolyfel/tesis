/*
 * Requisito con los términos ambiguos subrayados en el tono de su tipo. Los
 * tonos son para fondo oscuro; con `claro` (la vista para figura, fondo blanco)
 * se usan sus equivalentes oscuros y los términos sin tipo (unívocos) quedan
 * en el color del texto.
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
const TONO_CLARO = {
  lexica: "#0369a1",
  alcance: "#4338ca",
  anaforica: "#a21caf",
  sintactica: "#0e7490",
  vaguedad: "#7e22ce",
  regional: "#b45309",
  lel: "#047857",
};
export const tonoMarcado = (tipo, claro = false) =>
  (claro ? TONO_CLARO[tipo] ?? "currentColor" : TONO_AMBIGUEDAD[tipo] ?? "#efe9de");

export default function TextoMarcado({ texto, marcados = [], className = "", claro = false }) {
  const partes = [];
  let cursor = 0;
  [...marcados].sort((a, b) => a.inicio - b.inicio || b.fin - a.fin).forEach((m, i) => {
    if (m.inicio < cursor || m.fin <= m.inicio) return;
    if (m.inicio > cursor) partes.push(texto.slice(cursor, m.inicio));
    const tono = tonoMarcado(m.tipo, claro);
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
