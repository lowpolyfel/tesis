import { REGLAS, colorInterpretacion } from "../../constants/agentes";

/*
 * Evaluación del Crítico en una ronda: interpretación × regla. Decide la versión
 * relajada de R1/R2 (ADR 0004); la estricta se registra para el Capítulo 4.
 * La evidencia separa los tokens nuevos que aportó el significado de los que
 * nadie justificó.
 */
const Celda = ({ r, className = "" }) => {
  if (!r) return <td className={`px-2 text-center text-slate-400 ${className}`}>—</td>;
  const d = r.detalle ?? {};
  const partes = [
    r.evidencia,
    d.de_ellos_no_justificados?.length ? `no justificados: ${d.de_ellos_no_justificados.join(", ")}` : null,
    d.de_ellos_cubiertos_por_significado?.length ? `aportados por el significado: ${d.de_ellos_cubiertos_por_significado.join(", ")}` : null,
    d.evidencia_es_cita_de_la_parafrasis === false ? "la evidencia no es cita literal de la paráfrasis" : null,
  ].filter(Boolean);
  return (
    <td title={partes.join("\n")} className={`px-2 py-1 text-center ${r.cumple ? "text-emerald-600" : "font-semibold text-rose-600"} ${className}`}>
      {r.cumple ? "✓" : "✗"}
    </td>
  );
};

export default function MatrizReglas({ evaluaciones = [] }) {
  if (!evaluaciones.length) return null;
  return (
    <div className="overflow-x-auto">
      <table className="text-sm">
        <thead className="text-[11px] text-slate-500">
          <tr>
            <th className="px-2 text-left font-normal">interpretación</th>
            {["R1", "R2", "R3"].map((r) => <th key={r} className="px-2 font-normal" title={`${REGLAS[r].nombre}: ${REGLAS[r].como}`}>{r}</th>)}
            <th className="border-l border-slate-200 px-2 font-normal" title="Versión estricta (solo requisito + LEL): se registra, no decide">R1 estricta</th>
            <th className="px-2 font-normal" title="Versión estricta (solo requisito + LEL): se registra, no decide">R2 estricta</th>
          </tr>
        </thead>
        <tbody>
          {evaluaciones.map((e) => {
            const por = Object.fromEntries((e.reglas ?? []).map((r) => [r.regla, r]));
            return (
              <tr key={e.interpretacion_id} className="border-t border-slate-100">
                <td className="px-2 py-1 font-mono font-semibold" style={{ color: colorInterpretacion(e.interpretacion_id).trazo }}>{e.interpretacion_id}</td>
                <Celda r={por.R1} /><Celda r={por.R2} /><Celda r={por.R3} />
                <Celda r={e.r1_estricta} className="border-l border-slate-200 opacity-70" />
                <Celda r={e.r2_estricta} className="opacity-70" />
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-1 text-[11px] text-slate-500">Pasa el cursor sobre ✓/✗ para ver la evidencia. Decide la versión relajada; la estricta solo se registra (ADR 0004).</p>
    </div>
  );
}
