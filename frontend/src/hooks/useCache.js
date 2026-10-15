import { useEffect, useSyncExternalStore } from "react";
import { igualar } from "./useApi";

/*
 * Datos que se piden otra vez al cambiar de fase (el léxico, la lista de entrevistas y sus
 * turnos): se guardan en memoria por clave («P01:lexico») y se muestran al instante mientras se
 * vuelven a pedir en segundo plano (stale-while-revalidate). Si la respuesta no cambió se
 * conserva la misma referencia y nadie vuelve a pintar. Una sola petición en camino por clave.
 *
 * `invalidarCache(prefijo)` descarta lo que venía en camino y vuelve a pedir lo que esté a la
 * vista; lo demás se pide de nuevo la próxima vez que se monte. Lo llaman quienes cambian esos
 * datos: validar o corregir el léxico, procesar o borrar una entrevista.
 */
const VACIO = { datos: null, error: null };
const guardados = new Map(); // clave -> { actual: {datos, error}, pedir, pidiendo, gen, montados }
const oyentes = new Set();
const suscribir = (fn) => { oyentes.add(fn); return () => oyentes.delete(fn); };
const avisar = () => oyentes.forEach((fn) => fn());

function guardado(clave) {
  if (!guardados.has(clave)) guardados.set(clave, { actual: VACIO, pedir: null, pidiendo: null, gen: 0, montados: 0 });
  return guardados.get(clave);
}

function pedirDeNuevo(clave) {
  const g = guardado(clave);
  if (g.pidiendo || !g.pedir) return;
  const gen = g.gen;
  g.pidiendo = g.pedir().then(
    (d) => {
      if (g.gen !== gen) return;
      const datos = igualar(g.actual.datos, d);
      if (datos !== g.actual.datos || g.actual.error) { g.actual = { datos, error: null }; avisar(); }
    },
    (error) => {
      if (g.gen !== gen) return;
      g.actual = { ...g.actual, error };
      avisar();
    },
  ).finally(() => { if (g.gen === gen) g.pidiendo = null; });
}

export function invalidarCache(prefijo) {
  for (const [clave, g] of guardados) {
    if (!clave.startsWith(prefijo)) continue;
    g.gen += 1;
    g.pidiendo = null;
    if (g.montados > 0) pedirDeNuevo(clave);
  }
}

/*
 * { datos, error } de `clave` (null: no pedir nada todavía). `revalidar: false` para lo que no
 * cambia con la misma clave (el documento de una entrevista en una versión dada): solo se pide
 * si no está guardado.
 */
export function useCache(clave, pedir, { revalidar = true } = {}) {
  const actual = useSyncExternalStore(suscribir, () => (clave ? guardados.get(clave)?.actual ?? VACIO : VACIO));
  useEffect(() => {
    if (!clave) return undefined;
    const g = guardado(clave);
    g.pedir = pedir;
    g.montados += 1;
    if (revalidar || g.actual.datos == null) pedirDeNuevo(clave);
    return () => { g.montados -= 1; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave]);
  return { datos: actual.datos, error: actual.datos == null ? actual.error : null };
}
