import { useCallback, useEffect, useState } from "react";

/* Ejecuta una llamada de api.js y expone datos, error y carga */
export function useApi(llamada, deps = []) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let activo = true;
    setCargando(true);
    llamada()
      .then((d) => { if (activo) { setDatos(d); setError(null); } })
      .catch((e) => { if (activo) setError(e); })
      .finally(() => { if (activo) setCargando(false); });
    return () => { activo = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);
  return { datos, setDatos, error, cargando, recargar };
}
