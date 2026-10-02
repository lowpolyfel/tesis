import { useEffect, useState } from "react";

/*
 * Pantalla de carga en blanco. Cuando todo está listo, el orbe nace pequeño
 * en el centro y su mundo oscuro se abre paso hasta cubrir la pantalla.
 */
const MIN_WHITE_MS = 1500;
const BLOOM_MS = 2600;

export default function Loader({ onReveal, onFinished }) {
  const [phase, setPhase] = useState("white");

  useEffect(() => {
    let alive = true;
    const minWait = new Promise((r) => setTimeout(r, MIN_WHITE_MS));
    const fonts = document.fonts?.ready ?? Promise.resolve();
    const timers = [];
    Promise.all([minWait, fonts]).then(() => {
      if (!alive) return;
      setPhase("bloom");
      onReveal();
      timers.push(setTimeout(onFinished, BLOOM_MS));
    });
    return () => { alive = false; timers.forEach(clearTimeout); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={`loader is-${phase}`} role="status" aria-label="Cargando Dudamel">
      <div className="loader-mark">
        <span className="loader-word">
          {"DUDAMEL".split("").map((ch, i) => (
            <i key={i} style={{ "--i": i }}>{ch}</i>
          ))}
        </span>
        <span className="loader-bar"><span /></span>
        <span className="loader-caption">Cargando</span>
      </div>
    </div>
  );
}
