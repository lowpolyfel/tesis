/*
 * La lista de pasos de una pantalla de carga con la esfera (Preparacion.jsx y la
 * generación del mapa): cada paso con su marca (en curso, listo, aviso o falló) y
 * un detalle corto debajo.
 *   pasos: [{ texto, estado: "curso" | "ok" | "aviso" | "error", detalle }]
 */
export default function Pasos({ pasos }) {
  return (
    <ol className="mx-auto max-w-lg space-y-2.5">
      {pasos.map((p, i) => (
        <li key={i} className="flex items-start gap-3">
          <Marca estado={p.estado} />
          <span className="min-w-0 flex-1">
            <span className={`block text-[14.5px] ${p.estado === "curso" ? "text-[var(--bone)]" : "text-[var(--bone-dim)]"}`}>{p.texto}</span>
            {p.detalle && (
              <span className={`block break-words text-[12px] ${p.estado === "error" ? "text-[var(--danger)]" : p.estado === "aviso" ? "text-[var(--aviso)]" : "text-[var(--bone-faint)]"}`}>
                {p.detalle}
              </span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}

function Marca({ estado }) {
  if (estado === "curso") return <span className="gira mt-1 shrink-0" aria-label="en curso" />;
  const [signo, color, nombre] = {
    ok: ["✓", "var(--ok)", "listo"], aviso: ["!", "var(--aviso)", "aviso"], error: ["✕", "var(--danger)", "falló"],
  }[estado];
  return <span className="mono mt-0.5 w-3 shrink-0 text-center text-[12px]" style={{ color }} aria-label={nombre}>{signo}</span>;
}
