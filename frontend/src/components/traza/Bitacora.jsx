import { Fragment, useState } from "react";
import { obtenerTraza } from "../../services/backend";
import { nodo } from "../../constants/agentes";
import { resumenMensaje } from "../../escena/resumenMensaje";

/* Todos los mensajes del protocolo (GET /traza): la reconstrucción completa del caso */
const hora = (iso) => new Date(iso).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export default function Bitacora({ reqId, total }) {
  const [mensajes, setMensajes] = useState(null);
  const [error, setError] = useState(null);
  const [abierto, setAbierto] = useState(null);

  const cargar = () => obtenerTraza(reqId).then((t) => setMensajes(t.mensajes)).catch(setError);

  if (!mensajes) {
    return (
      <div className="flex items-center gap-3 text-sm">
        <button className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50" onClick={cargar}>Ver los {total} mensajes del protocolo</button>
        {error && <span className="text-rose-600">{error.message}</span>}
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-[12.5px]">
        <thead className="text-[11px] text-slate-500">
          <tr><th className="px-2">#</th><th className="px-2">ronda</th><th className="px-2">emisor → receptor</th><th className="px-2">tipo</th><th className="px-2">resumen</th><th className="px-2">modelo · prompt</th><th className="px-2">hora</th></tr>
        </thead>
        <tbody>
          {mensajes.map((m) => (
            <Fragment key={m.secuencia}>
              <tr className="cursor-pointer border-t border-slate-100 align-top hover:bg-slate-50"
                onClick={() => setAbierto((a) => (a === m.secuencia ? null : m.secuencia))}>
                <td className="px-2 py-1 font-mono text-slate-500">{m.secuencia}</td>
                <td className="px-2 py-1 font-mono text-slate-500">{m.ronda || ""}</td>
                <td className="whitespace-nowrap px-2 py-1 font-mono">
                  <span style={{ color: nodo(m.emisor).tono }}>{m.emisor}</span> → <span style={{ color: nodo(m.receptor).tono }}>{m.receptor}</span>
                </td>
                <td className="px-2 py-1 font-mono text-slate-600">{m.tipo}</td>
                <td className="px-2 py-1">{resumenMensaje(m)}</td>
                <td className="whitespace-nowrap px-2 py-1 font-mono text-[11px] text-slate-500">{[m.modelo, m.prompt_version].filter(Boolean).join(" · ")}</td>
                <td className="whitespace-nowrap px-2 py-1 font-mono text-[11px] text-slate-500">{hora(m.timestamp)}</td>
              </tr>
              {abierto === m.secuencia && (
                <tr>
                  <td colSpan={7} className="px-2 pb-2">
                    <pre className="max-h-96 overflow-auto rounded bg-slate-100 p-2 text-[11px]">{JSON.stringify(m.payload, null, 2)}</pre>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
