/* Lista de textos editable (noción, impacto, sinónimos…) */
export default function ListaEditable({ valores, onChange, placeholder = "", filas = 2 }) {
  const editar = (i, v) => onChange(valores.map((x, j) => (j === i ? v : x)));
  return (
    <div className="space-y-1.5">
      {valores.map((v, i) => (
        <div key={i} className="flex gap-1.5">
          <textarea
            value={v}
            rows={filas}
            onChange={(e) => editar(i, e.target.value)}
            placeholder={placeholder}
            className="min-w-0 flex-1 rounded border border-slate-300 p-1.5 text-sm"
          />
          <button type="button" onClick={() => onChange(valores.filter((_, j) => j !== i))} className="px-1 text-slate-400 hover:text-red-600" aria-label="Quitar">
            ✕
          </button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...valores, ""])} className="text-xs text-slate-600 underline">
        + agregar
      </button>
    </div>
  );
}
