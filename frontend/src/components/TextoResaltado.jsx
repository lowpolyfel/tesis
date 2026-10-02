import { TIPOS_AMBIGUEDAD } from "../constants/agentes";

/*
 * Requisito original con los términos ambiguos resaltados y numerados.
 * `marcados`: [{ texto, tipo, fuente, inicio, fin }] (posiciones en el texto)
 */
export default function TextoResaltado({ texto, marcados = [], conLeyenda = true }) {
  const partes = [];
  let cursor = 0;
  marcados.forEach((m, i) => {
    if (m.inicio < cursor) return; // solapado: se ignora
    if (m.inicio > cursor) partes.push(texto.slice(cursor, m.inicio));
    const tipo = TIPOS_AMBIGUEDAD[m.tipo];
    partes.push(
      <mark key={i} className={`rounded px-0.5 underline decoration-2 underline-offset-4 ${tipo?.clase ?? "bg-yellow-100"}`}>
        {texto.slice(m.inicio, m.fin)}
        <sup className="ml-0.5 text-[10px] font-semibold no-underline">{i + 1}</sup>
      </mark>
    );
    cursor = m.fin;
  });
  partes.push(texto.slice(cursor));

  return (
    <div>
      <p className="font-serif text-xl leading-relaxed text-slate-900">«{partes}»</p>
      {conLeyenda && (
        marcados.length > 0 ? (
          <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-600">
            {marcados.map((m, i) => (
              <li key={i}>
                <span className="font-semibold">{i + 1}.</span> «{texto.slice(m.inicio, m.fin)}» —{" "}
                <span className="font-medium">{TIPOS_AMBIGUEDAD[m.tipo]?.etiqueta ?? m.tipo}</span>
                <span className="text-slate-400"> · {m.fuente}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-slate-500">No se marcaron términos ambiguos.</p>
        )
      )}
    </div>
  );
}
