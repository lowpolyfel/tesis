import { LECTURAS } from "../constants/agentes";

export default function InterpretacionCard({ clave, interpretacion, destacada = false }) {
  const l = LECTURAS[clave];
  return (
    <article className={`rounded-md border-l-4 ${l.borde} ${l.fondo} p-3 ${destacada ? "ring-2 ring-slate-900" : ""}`}>
      <h3 className={`mb-1 text-xs font-bold uppercase tracking-wide ${l.texto}`}>
        {l.etiqueta}{destacada && " · elegida"}
      </h3>
      <p className="text-sm text-slate-900">{interpretacion.texto}</p>
      {interpretacion.lecturas?.length > 0 && (
        <dl className="mt-2 space-y-0.5 text-xs text-slate-600">
          {interpretacion.lecturas.map((x) => (
            <div key={x.termino}>
              <dt className="inline font-semibold">«{x.termino}»</dt> <dd className="inline">= {x.significado}</dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  );
}
