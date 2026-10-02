import { AGENTES, LECTURAS } from "../../constants/agentes";

/* Una ronda del debate: argumento de cada postura, nota del Crítico y similitud al cerrar */
export default function Ronda({ ronda, umbral, ultima, maxRondas }) {
  const de = (p) => ronda.intervenciones.find((x) => x.postura === p);
  const moderador = de("moderador");
  const delta = ronda.similitudCierre - ronda.similitudApertura;
  const alcanza = ronda.similitudCierre >= umbral;

  return (
    <article className="rounded-md border border-slate-200">
      <header className="flex items-baseline justify-between border-b border-slate-200 bg-slate-50 px-3 py-1.5">
        <h4 className="text-sm font-semibold">Ronda {ronda.numero} <span className="font-normal text-slate-500">de {maxRondas}</span></h4>
      </header>
      <div className="grid gap-3 p-3 sm:grid-cols-2">
        {["A", "B"].map((p) => {
          const x = de(p);
          const l = LECTURAS[p];
          return (
            <div key={p} className={`rounded border-l-4 ${l.borde} ${l.fondo} p-2.5`}>
              <p className={`mb-1 text-xs font-bold uppercase tracking-wide ${l.texto}`}>
                {AGENTES[x?.agente]?.nombre ?? "Agente"} · defiende la {l.etiqueta.toLowerCase()}
              </p>
              <p className="text-sm text-slate-800">{x?.argumento ?? "—"}</p>
              {ronda.ajustes?.[p] && (
                <p className="mt-2 border-t border-slate-200 pt-2 text-xs text-slate-700">
                  <span className="font-semibold">Reformula su lectura:</span> {ronda.ajustes[p]}
                </p>
              )}
            </div>
          );
        })}
        {moderador && (
          <div className="rounded border-l-4 border-slate-400 bg-white p-2.5 sm:col-span-2">
            <p className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-600">Crítico · conduce el debate</p>
            <p className="text-sm text-slate-800">{moderador.argumento}</p>
          </div>
        )}
      </div>
      <footer className={`border-t px-3 py-2 text-sm ${alcanza ? "border-teal-200 bg-teal-50 text-teal-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
        Similitud recalculada al cerrar la ronda:{" "}
        <strong className="font-mono">{ronda.similitudCierre.toFixed(2)}</strong>{" "}
        <span className="font-mono text-xs">({delta >= 0 ? "+" : ""}{delta.toFixed(2)} respecto a {ronda.similitudApertura.toFixed(2)})</span>
        {" — "}
        {alcanza
          ? <strong>≥ umbral {umbral.toFixed(2)}: hay consenso, el debate termina.</strong>
          : ultima
            ? <strong>{"<"} umbral {umbral.toFixed(2)} y no quedan rondas.</strong>
            : <>{"<"} umbral {umbral.toFixed(2)}: sigue la divergencia, pasa a la siguiente ronda.</>}
      </footer>
    </article>
  );
}
