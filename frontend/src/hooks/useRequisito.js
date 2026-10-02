import { useCallback, useEffect, useState } from "react";
import { seguirRequisito } from "../services/polling";

/* Requisito con sondeo: se actualiza solo mientras los agentes trabajan */
export function useRequisito(id) {
  const [requisito, setRequisito] = useState(null);
  const [error, setError] = useState(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    setError(null);
    const detener = seguirRequisito(id, setRequisito);
    return detener;
  }, [id, version]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);
  return { requisito, error, recargar };
}
