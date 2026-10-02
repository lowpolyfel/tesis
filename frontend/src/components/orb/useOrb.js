import { createContext, useContext, useEffect } from "react";
import { isMobile } from "./poses";

/* La esfera es global: cualquier pantalla la mueve desde aquí */
export const OrbContext = createContext(null);
export const useOrb = () => useContext(OrbContext);

/*
 * Coloca la esfera principal al montar la pantalla (y al cambiar el tamaño).
 * `pose` = { d: {x,y,s}, m: {x,y,s} } para escritorio y móvil.
 */
export function usePoseEsfera(pose, deps = []) {
  const orb = useOrb();
  useEffect(() => {
    if (!pose) return;
    const aplicar = () => orb.setPose(isMobile() ? pose.m ?? pose.d : pose.d);
    aplicar();
    window.addEventListener("resize", aplicar);
    return () => window.removeEventListener("resize", aplicar);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
