import { infoEstado } from "../../constants/estados";

/* Camino real que siguió el requisito por la máquina de estados (transiciones de la traza) */
const hora = (iso) => new Date(iso).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export default function RutaEstados({ transiciones = [], enProceso = false }) {
  // tras un reinicio un estado puede repetirse: se muestran todas, en orden
  return (
    <ol className="flex flex-wrap items-center gap-1.5 text-xs">
      {transiciones.map((t, i) => {
        const info = infoEstado(t.estado);
        const ultimo = i === transiciones.length - 1;
        return (
          <li key={`${t.estado}-${i}`} className="flex items-center gap-1.5">
            <span title={`${info.descripcion}\n${hora(t.timestamp)} · tras el mensaje ${t.secuencia}`}
              className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 ring-1 ring-inset ${info.clase} ${ultimo ? "font-semibold" : "opacity-80"}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${info.punto}`} />
              {info.etiqueta}
              <span className="font-mono text-[10px] opacity-60">#{t.secuencia}</span>
            </span>
            {!ultimo && <span className="text-slate-400">→</span>}
          </li>
        );
      })}
      {enProceso && <li className="flex items-center gap-1.5 text-slate-500"><span>→</span><span className="gira" /> en proceso</li>}
    </ol>
  );
}
