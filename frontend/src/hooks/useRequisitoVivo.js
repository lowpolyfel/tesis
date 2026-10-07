import { useCallback, useEffect, useRef, useState } from "react";
import { obtenerRequisito } from "../services/backend";
import { seguirRequisito } from "../services/eventos";
import { ESTADOS as E, esTerminal } from "../constants/estados";

/*
 * Vista por término de un requisito (GET /requisitos/{id}) que se mantiene al
 * día con el SSE: cada mensaje o cambio de estado vuelve a pedir la vista
 * (agrupado, a lo más una petición cada 400 ms). El SSE solo se abre mientras
 * los agentes trabajan: en un estado terminal o en pendiente_validacion nada
 * cambia hasta que una persona actúa, y una conexión abierta por pestaña agota
 * las seis que el navegador permite por servidor. Tras validar, `recargar({
 * seguir: true })` lo vuelve a abrir hasta que la validación se procese.
 */
const enReposo = (estado) => esTerminal(estado) || estado === E.PENDIENTE_VALIDACION;

export function useRequisitoVivo(reqId) {
  const [vista, setVista] = useState(null);
  const [error, setError] = useState(null);
  const [version, setVersion] = useState(0);
  const pendiente = useRef(null);
  const seguirAunque = useRef(false); // seguir aunque esté en pendiente_validacion (se acaba de validar)

  useEffect(() => {
    setVista(null);
    setError(null);
  }, [reqId]);

  useEffect(() => {
    if (!reqId) return undefined;
    let activo = true;
    let detener = () => {};
    const esperarValidacion = seguirAunque.current;
    seguirAunque.current = false;

    const cargar = () => obtenerRequisito(reqId)
      .then((v) => { if (activo) { setVista(v); setError(null); } return v; })
      .catch((e) => { if (activo) setError(e); return null; });
    const programar = () => {
      if (pendiente.current) return;
      pendiente.current = setTimeout(() => { pendiente.current = null; cargar(); }, 400);
    };
    const cerrar = () => {
      detener();
      clearTimeout(pendiente.current);
      pendiente.current = null;
      cargar();
    };

    cargar().then((v) => {
      if (!activo || !v || (enReposo(v.estado) && !esperarValidacion)) return;
      let validacionTomada = !esperarValidacion;
      detener = seguirRequisito(reqId, {
        desde: v.ultima_secuencia, // lo anterior ya está en la vista
        onMensaje: programar,
        onEstado: ({ estado }) => {
          // recién validado sigue en pendiente_validacion hasta que la cola lo toma
          if (estado !== E.PENDIENTE_VALIDACION) validacionTomada = true;
          if (validacionTomada && enReposo(estado)) cerrar();
          else programar();
        },
        onFin: cerrar,
      });
    });
    return () => {
      activo = false;
      clearTimeout(pendiente.current);
      pendiente.current = null;
      detener();
    };
  }, [reqId, version]);

  const recargar = useCallback(({ seguir = false } = {}) => {
    if (seguir) seguirAunque.current = true;
    setVersion((v) => v + 1);
  }, []);
  return { vista, error, recargar, terminado: vista ? esTerminal(vista.estado) : false };
}
