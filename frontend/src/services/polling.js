/*
 * Sondeo de estado, aislado aquí. El proceso de los agentes tarda varios
 * segundos por requisito: la UI pregunta periódicamente y solo pide el
 * detalle completo cuando algo cambió. Hoy el "servidor" es la simulación;
 * con el backend real basta con que api.js apunte a los endpoints (o
 * cambiar este archivo por WebSocket/SSE sin tocar las pantallas).
 */
import * as api from "./api";
import { estaEnProceso } from "../constants/estados";

const INTERVALO_MS = 1500;

/** Sigue un requisito hasta que sale de los estados en proceso. Devuelve la función para detener. */
export function seguirRequisito(id, onCambio, { intervaloMs = INTERVALO_MS } = {}) {
  let activo = true;
  let ultimo = null;
  let timer;
  const tick = async () => {
    try {
      const s = await api.obtenerEstadoRequisito(id);
      if (!activo) return;
      if (s.actualizadoEn !== ultimo) {
        ultimo = s.actualizadoEn;
        const req = await api.obtenerRequisito(id);
        if (activo) onCambio(req);
      }
      if (activo && estaEnProceso(s.estado)) timer = setTimeout(tick, intervaloMs);
    } catch (e) {
      console.error("Sondeo de requisito", e);
      if (activo) timer = setTimeout(tick, intervaloMs * 2);
    }
  };
  tick();
  return () => { activo = false; clearTimeout(timer); };
}

/** Refresca la cola mientras haya requisitos en proceso. */
export function seguirCola(onCambio, { intervaloMs = INTERVALO_MS } = {}) {
  let activo = true;
  let timer;
  const tick = async () => {
    try {
      const lista = await api.listarRequisitos();
      if (!activo) return;
      onCambio(lista);
      if (lista.some((r) => estaEnProceso(r.estado))) timer = setTimeout(tick, intervaloMs);
    } catch (e) {
      console.error("Sondeo de cola", e);
      if (activo) timer = setTimeout(tick, intervaloMs * 2);
    }
  };
  tick();
  return () => { activo = false; clearTimeout(timer); };
}

/** Sigue una corrida del corpus hasta que termina. */
export function seguirEjecucion(id, onCambio, { intervaloMs = 700 } = {}) {
  let activo = true;
  let timer;
  const tick = async () => {
    const ej = await api.obtenerEjecucion(id);
    if (!activo) return;
    onCambio(ej);
    if (ej.estado === "en_curso") timer = setTimeout(tick, intervaloMs);
  };
  tick();
  return () => { activo = false; clearTimeout(timer); };
}

/** Sigue un lote de requisitos (traza completa de cada uno) hasta que todos terminan. */
export function seguirLote(ids, onCambio, { intervaloMs = 900 } = {}) {
  let activo = true;
  let timer;
  const tick = async () => {
    try {
      const lista = await Promise.all(ids.map((id) => api.obtenerRequisito(id)));
      if (!activo) return;
      onCambio(lista);
      if (lista.some((r) => estaEnProceso(r.estado))) timer = setTimeout(tick, intervaloMs);
    } catch (e) {
      console.error("Sondeo de lote", e);
      if (activo) timer = setTimeout(tick, intervaloMs * 2);
    }
  };
  tick();
  return () => { activo = false; clearTimeout(timer); };
}
