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
 * pintar (los sondeos cuestan una petición, no un render). Con `{ silencioso: false }` cada
 * recarga vuelve a poner `cargando` (un botón «Probar otra vez» que debe decir que está probando).
 * Un cambio local (`setDatos`) gana a una respuesta que salió antes de él: esa se descarta y se
 * vuelve a pedir, para no regresar la pantalla a como estaba en el servidor antes del cambio.
 */
export function useApi(llamada, deps = [], { silencioso = true } = {}) {
  const [datos, setDatosApi] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [version, setVersion] = useState(0);
  const hayDatos = useRef(false);
  const ediciones = useRef(0); // cambios locales hechos con setDatos

  useEffect(() => {
    let activo = true;
    const desde = ediciones.current;
    if (!hayDatos.current || !silencioso) setCargando(true);
    llamada()
      .then((d) => {
        if (!activo) return;
        if (ediciones.current !== desde) { setVersion((v) => v + 1); return; } // salió antes de un cambio local
        hayDatos.current = d != null;
        setDatosApi((previo) => igualar(previo, d));
        setError(null);
      })
      .catch((e) => { if (activo) setError(e); })
      .finally(() => { if (activo) setCargando(false); });
    return () => { activo = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);
  const setDatos = useCallback((valor) => { ediciones.current++; setDatosApi(valor); }, []);
  return { datos, setDatos, error, cargando, recargar };
}
