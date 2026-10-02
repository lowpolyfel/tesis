/*
 * Tabla de filas editables. `columnas`: [{ clave, titulo, tipo: "texto"|"lista", ancho }]
 * Las columnas "lista" se editan una lectura por renglón.
 */
export default function TablaEditable({ columnas, filas, onChange, nuevaFila }) {
  const editar = (i, clave, valor) => onChange(filas.map((f, j) => (j === i ? { ...f, [clave]: valor } : f)));

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <table className="w-full table-fixed text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            {columnas.map((c) => <th key={c.clave} className={`px-2 py-2 ${c.ancho ?? ""}`}>{c.titulo}</th>)}
            <th className="w-10" />
          </tr>
        </thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={f.id} className="border-t border-slate-100 align-top">
              {columnas.map((c) => (
                <td key={c.clave} className="px-1.5 py-1.5">
                  {c.tipo === "lista" ? (
                    <textarea
                      value={(f[c.clave] ?? []).join("\n")}
                      rows={Math.max(2, (f[c.clave] ?? []).length)}
                      onChange={(e) => editar(i, c.clave, e.target.value.split("\n"))}
                      className="w-full rounded border border-transparent p-1 hover:border-slate-200 focus:border-slate-400"
                    />
                  ) : (
                    <textarea
                      value={f[c.clave] ?? ""}
                      rows={2}
                      onChange={(e) => editar(i, c.clave, e.target.value)}
                      className="w-full rounded border border-transparent p-1 hover:border-slate-200 focus:border-slate-400"
                    />
                  )}
                </td>
              ))}
              <td className="py-2 text-center">
                <button onClick={() => onChange(filas.filter((_, j) => j !== i))} className="text-slate-400 hover:text-red-600" aria-label="Eliminar fila">✕</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button onClick={() => onChange([...filas, nuevaFila()])} className="w-full border-t border-slate-100 py-2 text-sm text-slate-600 hover:bg-slate-50">
        + Agregar expresión
      </button>
    </div>
  );
}
