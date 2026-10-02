import { DIAGRAMA, INFO_ESTADO, alcanzo } from "../constants/estados";

/*
 * La máquina de estados dibujada de izquierda a derecha. Marca el camino
 * que siguió este requisito y su estado actual; las ramas no tomadas
 * quedan atenuadas.
 */
export default function LineaEstados({ historial, estado }) {
  return (
    <ol className="grid grid-cols-4 gap-x-1 gap-y-3 sm:grid-cols-8" aria-label="Camino del requisito por la máquina de estados">
      {DIAGRAMA.map((columna, i) => (
        <li key={i} className="relative flex flex-col justify-center gap-1.5">
          {i > 0 && (
            <span aria-hidden="true" className="absolute top-1/2 -left-1.5 hidden -translate-y-1/2 text-slate-300 sm:block">›</span>
          )}
          {columna.map((e) => {
            const info = INFO_ESTADO[e];
            const actual = e === estado;
            const visitado = alcanzo(historial, e);
            const clase = actual
              ? `${info.clase} ring-2 font-semibold`
              : visitado
                ? `${info.clase} ring-1`
                : "border border-dashed border-slate-300 bg-white text-slate-400";
            return (
              <span
                key={e}
                title={info.descripcion}
                className={`flex items-center gap-1.5 rounded px-1.5 py-1 text-[11px] leading-tight ring-inset ${clase}`}
              >
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${visitado || actual ? info.punto : "bg-slate-200"}`} />
                {info.etiqueta}
              </span>
            );
          })}
        </li>
      ))}
    </ol>
  );
}
