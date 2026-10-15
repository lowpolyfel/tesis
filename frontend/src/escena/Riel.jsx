import { useEffect, useState } from "react";
import { tintaNodo } from "../constants/agentes";

/*
 * El riel de la escena: los nombres de las estaciones en texto tenue, entre el sistema y el
 * agente, cada uno sobre el lugar adonde viaja el agente, con la estación que tiene el turno
 * en el tono de quien habla. Es texto fijo, sin animación: se coloca con la geometría de la
 * coreografía (fracciones de la pantalla desde el centro, como los botones de Orbita.jsx).
 * Si los nombres no caben (el teléfono), solo dice la estación actual.
 *
 * Se vuelve a dibujar con la página, que cambia con cada mensaje animado.
 */
export default function Riel({ coreografia }) {
  const [, setVentana] = useState(0);
  useEffect(() => {
    const alCambiar = () => setVentana((n) => n + 1);
    addEventListener("resize", alCambiar);
    return () => removeEventListener("resize", alCambiar);
  }, []);

  const r = coreografia.riel();
  if (!r) return null;
  // caben todos si entre dos estaciones hay sitio para el nombre más largo (.etiqueta: ~7.5 px por letra)
  const paso = r.estaciones.length > 1 ? (r.estaciones[1].x - r.estaciones[0].x) * innerWidth : Infinity;
  const todas = paso >= Math.max(...r.estaciones.map((e) => e.nombre.length)) * 7.5 + 16;
  return (
    <ol className="pointer-events-none fixed inset-0 z-[5]" aria-label="Estaciones del flujo">
      {r.estaciones.map((e, i) => (todas || i === r.actual) && (
        <li key={e.id} aria-current={i === r.actual ? "step" : undefined}
          className={`etiqueta absolute -translate-x-1/2 -translate-y-1/2 whitespace-nowrap ${i === r.actual ? "" : "opacity-70"}`}
          style={{ left: `calc(50% + ${e.x * 100}vw)`, top: `calc(50% + ${r.y * 100}vh)`, color: i === r.actual ? tintaNodo(r.nodo) : undefined }}>
          {e.nombre}
        </li>
      ))}
    </ol>
  );
}
