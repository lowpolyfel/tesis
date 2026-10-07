import { useCallback, useEffect, useRef, useState } from "react";
import { obtenerRequisito } from "../services/backend";
import { seguirRequisito } from "../services/eventos";
import { esTerminal } from "../constants/estados";

/*
 * Vista por término de un requisito (GET /requisitos/{id}) que se mantiene al
 * día con el SSE: cada mensaje o cambio de estado vuelve a pedir la vista
 * (agrupado, a lo más una petición cada 400 ms). Al llegar a un estado
 * terminal se deja de escuchar.
 */
export function useRequisitoVivo(reqId) {
  const [vista, setVista] = useState(null);
  const [error, setError] = useState(null);
  const [version, setVersion] = useState(0);
  const pendiente = useRef(null);

  useEffect(() => {
    if (!reqId) return undefined;
    let activo = true;
    setVista(null);
    setError(null);

    const cargar = () => obtenerRequisito(reqId)
      .then((v) => { if (activo) { setVista(v); setError(null); } })
      .catch((e) => { if (activo) setError(e); });
    const programar = () => {
      if (pendiente.current) return;
      pendiente.current = setTimeout(() => { pendiente.current = null; cargar(); }, 400);
    };

    let detener = () => {};
    cargar().then(() => {
      if (!activo) return;
      detener = seguirRequisito(reqId, {
        onMensaje: programar,
        onEstado: programar,
        onFin: () => { clearTimeout(pendiente.current); pendiente.current = null; cargar(); },
      });
    });
    return () => {
      activo = false;
      clearTimeout(pendiente.current);
      pendiente.current = null;
      detener();
    };
  }, [reqId, version]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);
  return { vista, error, recargar, terminado: vista ? esTerminal(vista.estado) : false };
}
