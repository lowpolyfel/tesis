/*
 * Sigue un requisito en vivo (SSE) y, si se le da una coreografía, anima cada
 * mensaje en orden con un ritmo legible. Los mensajes llegan a veces de golpe
 * (al reabrir un requisito terminado, o si los LLM responden rápido): la cola
 * los reparte en el tiempo; `acelerar()` vacía la cola sin pausas, aplicando
 * cada mensaje a la escena para que quede como dice la traza. En
 * pendiente_validacion el SSE se cierra: nada cambia hasta que una persona
 * valide, y una conexión retenida por pestaña agota las del navegador.
 *
 * `seguir` cambia la fuente (una entrevista en la versión 2: seguirEntrevista) y `pausa` el estado
 * en que se deja de escuchar.
 *
 * Devuelve { mensajes, animados, estado, terminado, error, acelerar, ritmo, setRitmo }.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { seguirRequisito } from "../services/eventos";
import { ESTADOS } from "../constants/estados";

const espera = (ms) => new Promise((r) => setTimeout(r, ms));

export function useEnVivo(reqId, { coreografia = null, ritmoInicial = 1, seguir = seguirRequisito, pausa = ESTADOS.PENDIENTE_VALIDACION } = {}) {
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
    const recibidos = new Set();
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
        const saltando = saltarRef.current;
        const dur = coreografia ? coreografia.aplicar(item, { rapido: saltando }) : 0;
        setAnimados((n) => n + 1);
        if (dur && !saltando) await espera(dur / Math.max(0.25, ritmoRef.current));
        if (!cola.length) saltarRef.current = false;
      }
    })();

    const detener = seguir(reqId, {
      onMensaje: (m) => {
        if (recibidos.has(m.secuencia)) return; // reconexión: el mismo mensaje no se anima dos veces
        recibidos.add(m.secuencia);
        setMensajes((l) => [...l, m]);
        cola.push(m);
        avisar();
      },
      onEstado: (d) => {
        cola.push({ estado: d.estado });
        avisar();
        if (d.estado === pausa) detener(); // ya llegaron todos sus mensajes
      },
      onFin: (d) => { cola.push({ estado: d.estado, fin: true }); avisar(); },
      onError: (e) => setError(e),
    });
    return () => { vivo = false; avisar(); detener(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reqId, coreografia]);

  const acelerar = useCallback(() => { saltarRef.current = true; }, []);
  return { mensajes, animados, estado, terminado, error, acelerar, ritmo, setRitmo };
}
