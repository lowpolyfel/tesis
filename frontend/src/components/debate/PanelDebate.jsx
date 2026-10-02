import GraficaSimilitud from "./GraficaSimilitud";
import Ronda from "./Ronda";
import Arbitraje from "./Arbitraje";

/*
 * Vista de debate (pantalla 4): ronda por ronda, con la similitud
 * recalculada al cierre y, si se agotaron las rondas, el arbitraje.
 */
export default function PanelDebate({ debate, similitudInicial }) {
  const { rondas, maxRondas, umbral, resultado } = debate;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start gap-x-6 gap-y-2">
        <dl className="grid grid-cols-[auto_auto] gap-x-3 gap-y-0.5 text-sm">
          <dt className="text-slate-500">Rondas máximas</dt><dd className="font-mono">{maxRondas}</dd>
          <dt className="text-slate-500">Rondas jugadas</dt><dd className="font-mono">{rondas.length}</dd>
          <dt className="text-slate-500">Umbral</dt><dd className="font-mono">{umbral.toFixed(2)}</dd>
          <dt className="text-slate-500">Resultado</dt>
          <dd className="font-semibold">
            {resultado === "consenso" && "Consenso"}
            {resultado === "agotado" && "Rondas agotadas → arbitraje"}
            {resultado === "en_curso" && "En curso"}
          </dd>
        </dl>
        <div className="min-w-0 flex-1">
          <GraficaSimilitud inicial={similitudInicial} rondas={rondas} umbral={umbral} maxRondas={maxRondas} />
        </div>
      </div>

      {rondas.map((r, i) => (
        <Ronda key={r.numero} ronda={r} umbral={umbral} maxRondas={maxRondas} ultima={i === maxRondas - 1} />
      ))}

      {resultado === "en_curso" && (
        <p className="flex items-center gap-2 rounded border border-dashed border-amber-300 px-3 py-2 text-sm text-amber-800">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
          {rondas.at(-1)?.similitudCierre >= umbral
            ? "Consenso alcanzado; cerrando el debate…"
            : rondas.length < maxRondas
              ? `Ronda ${rondas.length + 1} en curso…`
              : "Se agotaron las rondas: el Crítico está arbitrando…"}
        </p>
      )}

      {debate.arbitraje && <Arbitraje arbitraje={debate.arbitraje} rondas={rondas} maxRondas={maxRondas} umbral={umbral} />}
    </div>
  );
}
