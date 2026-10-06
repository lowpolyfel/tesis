/*
 * Mensajes en vivo de un requisito: GET /eventos/{req_id} (SSE).
 *   evento "mensaje": un Mensaje del protocolo (id = secuencia)
 *   evento "estado":  { estado, secuencia } al cambiar de estado
 *   evento "fin":     { estado } al llegar a un estado terminal; el servidor cierra
 * Al reconectar, el navegador manda Last-Event-ID y el servidor no repite mensajes.
 */
import { BASE_URL } from "./http";

export function seguirRequisito(reqId, { desde = 0, onMensaje, onEstado, onFin, onError } = {}) {
  const url = new URL(`${BASE_URL}/eventos/${encodeURIComponent(reqId)}`);
  if (desde) url.searchParams.set("desde", desde);
  const fuente = new EventSource(url);
  let cerrado = false;
  const parse = (e) => { try { return JSON.parse(e.data); } catch { return null; } };

  fuente.addEventListener("mensaje", (e) => { const m = parse(e); if (m) onMensaje?.(m); });
  fuente.addEventListener("estado", (e) => { const d = parse(e); if (d) onEstado?.(d); });
  fuente.addEventListener("fin", (e) => {
    cerrado = true;
    fuente.close();
    onFin?.(parse(e) ?? {});
  });
  fuente.onerror = () => {
    // EventSource reintenta solo; si el servidor ya cerró por fin, no es error
    if (!cerrado && fuente.readyState === EventSource.CLOSED) onError?.(new Error("Se perdió la conexión de eventos"));
  };
  return () => { cerrado = true; fuente.close(); };
}
