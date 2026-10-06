/*
 * Sigue un requisito en vivo (SSE) y, si se le da una coreografía, anima cada
 * mensaje en orden con un ritmo legible. Los mensajes llegan a veces de golpe
 * (al reabrir un requisito terminado, o si los LLM responden rápido): la cola
 * los reparte en el tiempo; `acelerar()` vacía la cola sin animar.
 *
 * Devuelve { mensajes, animados, estado, terminado, error, acelerar, ritmo, setRitmo }.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { seguirRequisito } from "../services/eventos";

const espera = (ms) => new Promise((r) => setTimeout(r, ms));

export function useEnVivo(reqId, { coreografia = null, ritmoInicial = 1 } = {}) {
  const [mensajes, setMensajes] = useState([]);
  const [animados, setAnimados] = useState(0);
  const [estado, setEstado] = useState(null);
  const [terminado, setTerminado] = useState(false);
  const [error, setError] = useState(null);
  const [ritmo, setRitmo] = useState(ritmoInicial);
  const ritmoRef = useRef(ritmoInicial);
  const saltarRef = useRef(false);

  useEffect(() => { ritmoRef.current = ritmo; }, [ritmo]);

  useEffect(() => {
    if (!reqId) return undefined;
    setMensajes([]); setAnimados(0); setEstado(null); setTerminado(false); setError(null);
    saltarRef.current = false;
    coreografia?.reiniciar();

    const cola = [];
    let vivo = true;
    let despertar = null;
    const avisar = () => { despertar?.(); despertar = null; };

    (async () => {
      while (vivo) {
        if (!cola.length) {
          await new Promise((r) => { despertar = r; });
          continue;
        }
        const item = cola.shift();
        if (item.estado) {
          setEstado(item.estado);
          coreografia?.estado(item.estado);
          if (item.fin) setTerminado(true);
          continue;
        }
        const dur = coreografia && !saltarRef.current ? coreografia.aplicar(item) : 0;
        setAnimados((n) => n + 1);
        if (dur && !saltarRef.current) await espera(dur / Math.max(0.25, ritmoRef.current));
        if (!cola.length) saltarRef.current = false;
      }
    })();

    const detener = seguirRequisito(reqId, {
      onMensaje: (m) => { setMensajes((l) => (l.some((x) => x.secuencia === m.secuencia) ? l : [...l, m])); cola.push(m); avisar(); },
      onEstado: (d) => { cola.push({ estado: d.estado }); avisar(); },
      onFin: (d) => { cola.push({ estado: d.estado, fin: true }); avisar(); },
      onError: (e) => setError(e),
    });
    return () => { vivo = false; avisar(); detener(); };
  }, [reqId, coreografia]);

  const acelerar = useCallback(() => { saltarRef.current = true; }, []);
  return { mensajes, animados, estado, terminado, error, acelerar, ritmo, setRitmo };
}
