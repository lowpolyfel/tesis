import { useCallback, useEffect, useRef, useState } from "react";

/*
 * El valor nuevo, reusando las partes del anterior que no cambiaron (iguales como JSON): si nada
 * cambió devuelve el anterior tal cual y React no vuelve a pintar; si cambió una entrada de una
 * lista, las demás conservan su referencia (y su memo). Solo mira arreglos y objetos planos.
 */
const plano = (x) => x !== null && typeof x === "object" && (Array.isArray(x) || Object.getPrototypeOf(x) === Object.prototype);

export function igualar(previo, nuevo) {
  if (previo === nuevo || !plano(previo) || !plano(nuevo) || Array.isArray(previo) !== Array.isArray(nuevo)) return nuevo;
  if (Array.isArray(nuevo)) {
    const r = nuevo.map((x, i) => igualar(previo[i], x));
    return r.length === previo.length && r.every((x, i) => x === previo[i]) ? previo : r;
  }
  const claves = Object.keys(nuevo);
  let igual = claves.length === Object.keys(previo).length;
  const r = {};
  for (const k of claves) {
    r[k] = igualar(previo[k], nuevo[k]);
    if (r[k] !== previo[k] || !(k in previo)) igual = false;
  }
  return igual ? previo : r;
}

/*
 * Ejecuta una llamada de api.js y expone datos, error y carga. `recargar` es silencioso: si ya
 * hay datos se quedan a la vista (sin `cargando`) y, si la respuesta no cambió, nada se vuelve a
 * pintar (los sondeos cuestan una petición, no un render).
 */
export function useApi(llamada, deps = []) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [version, setVersion] = useState(0);
  const hayDatos = useRef(false);

  useEffect(() => {
    let activo = true;
    if (!hayDatos.current) setCargando(true);
    llamada()
      .then((d) => { if (activo) { hayDatos.current = d != null; setDatos((previo) => igualar(previo, d)); setError(null); } })
      .catch((e) => { if (activo) setError(e); })
      .finally(() => { if (activo) setCargando(false); });
    return () => { activo = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);
  return { datos, setDatos, error, cargando, recargar };
}
