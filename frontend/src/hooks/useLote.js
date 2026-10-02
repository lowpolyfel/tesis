import { useCallback, useEffect, useState } from "react";
import { obtenerRequisito } from "../services/api";

/* Carga una vez los requisitos de un lote (sin sondeo) */
export function useLote(ids) {
  const [lista, setLista] = useState(null);
  const [version, setVersion] = useState(0);
  const clave = ids.join(",");
  useEffect(() => {
    let activo = true;
    Promise.all(ids.map((id) => obtenerRequisito(id))).then((l) => activo && setLista(l));
    return () => { activo = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave, version]);
  const recargar = useCallback(() => setVersion((v) => v + 1), []);
  return { lista, recargar };
}
