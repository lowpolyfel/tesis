import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useOrb } from "./useOrb";
import { isMobile } from "./poses";

/*
 * Menú de la esfera. Al tocar la esfera principal (o el botón «Menú»), viaja al
 * centro y se divide en una esfera por destino; tocar una lleva ahí y todas
 * vuelven a fundirse. Las esferas se dibujan por encima del velo (la capa de
 * las esferas se eleva); los botones van encima de ellas, en el mismo lugar.
 *
 * destinos: [{ id, etiqueta, a, mood }]
 */
const RETIRO_MS = 650;

function lugares(destinos) {
  const m = isMobile();
  const n = destinos.length;
  const rx = m ? 0.31 : Math.min(0.24, 290 / innerWidth);
  const ry = m ? 0.24 : Math.min(0.3, 270 / innerHeight);
  return destinos.map((d, i) => {
    const ang = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    return { ...d, x: Math.cos(ang) * rx, y: Math.sin(ang) * ry };
  });
}

export default function Orbita({ abierta, onCerrar, destinos }) {
  const orb = useOrb();
  const navigate = useNavigate();
  const [puestos, setPuestos] = useState([]);
  const primero = useRef(null);
  const retiro = useRef(null);

  useEffect(() => {
    if (!abierta) return undefined;
    clearTimeout(retiro.current);
    const core = orb.state.bodies.get("core");
    const previa = { ...core.target };
    const pos = lugares(destinos);
    const ids = pos.map((d) => `menu:${d.id}`);
    setPuestos(pos);
    orb.setElevada(true);
    orb.setPose({ x: 0, y: 0, s: isMobile() ? 0.42 : 0.55 });
    orb.divide("core", pos.map((d) => ({
      id: `menu:${d.id}`, mood: d.mood, x: d.x, y: d.y, s: isMobile() ? 0.24 : 0.3, label: null, sub: null,
    })));
    const t = setTimeout(() => primero.current?.focus(), 80);
    const tecla = (e) => { if (e.key === "Escape") onCerrar(); };
    addEventListener("keydown", tecla);
    return () => {
      clearTimeout(t);
      removeEventListener("keydown", tecla);
      orb.fuse(ids, "core");
      orb.setPose(previa); // si se navega, la sección nueva pone su pose después
      retiro.current = setTimeout(() => orb.setElevada(false), RETIRO_MS);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierta]);

  if (!abierta) return null;

  const elegir = (d) => {
    orb.poke(1, "core");
    onCerrar();
    navigate(d.a);
  };

  return (
    <>
      <div className="velo fixed inset-0 z-40" onClick={onCerrar} aria-hidden="true" />
      <nav className="fixed inset-0 z-50 pointer-events-none" aria-label="Menú de la esfera">
        {puestos.map((d, i) => (
          <button
            key={d.id}
            ref={i === 0 ? primero : undefined}
            onClick={() => elegir(d)}
            onPointerEnter={() => orb.poke(0.7, `menu:${d.id}`)}
            onFocus={() => orb.poke(0.5, `menu:${d.id}`)}
            className="punto-menu pointer-events-auto absolute h-24 w-24 -translate-x-1/2 -translate-y-1/2 rounded-full"
            style={{ left: `calc(50% + ${d.x * 100}vw)`, top: `calc(50% + ${d.y * 100}vh)` }}
          >
            <span className="mono absolute top-[calc(100%+2px)] left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] text-[var(--bone)]">
              {d.etiqueta}
            </span>
          </button>
        ))}
        <button
          onClick={onCerrar}
          aria-label="Cerrar el menú"
          className="pointer-events-auto absolute top-1/2 left-1/2 h-28 w-28 -translate-x-1/2 -translate-y-1/2 rounded-full"
        />
        <p className="mono absolute inset-x-0 bottom-8 text-center text-[10px] text-[var(--bone-faint)]">
          Toca una esfera · Esc para cerrar
        </p>
      </nav>
    </>
  );
}
