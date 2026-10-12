import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Navigate, useLocation } from "react-router";
import { miCuenta, salir as salirDelBackend } from "../services/backend";
import { SIN_SESION } from "../services/http";
import { olvidarProyecto } from "./proyectoRecordado";

/*
 * La cuenta con sesión. La sesión es una cookie HttpOnly del backend: aquí solo se
 * sabe quién es (GET /auth/yo al abrir la app). Un 401 de cualquier llamada (sesión
 * vencida o cerrada en otra pestaña) la borra y las rutas protegidas llevan a «Entrar».
 */
const SesionContext = createContext(null);
export const useSesion = () => useContext(SesionContext);

export function ProveedorSesion({ children }) {
  const [usuario, setUsuario] = useState(undefined); // undefined: preguntando · null: sin sesión
  const [salio, setSalio] = useState(false); // cerró la sesión a propósito: «Entrar» sin «volver a…»

  useEffect(() => {
    let activo = true;
    miCuenta().then((u) => { if (activo) setUsuario(u); }).catch(() => { if (activo) setUsuario(null); });
    const sinSesion = () => setUsuario(null);
    window.addEventListener(SIN_SESION, sinSesion);
    return () => { activo = false; window.removeEventListener(SIN_SESION, sinSesion); };
  }, []);

  // el último proyecto abierto es de la cuenta anterior: no se arrastra a otra
  const iniciar = useCallback((u) => { olvidarProyecto(); setSalio(false); setUsuario(u); }, []);
  // primero la sesión local (las rutas protegidas llevan a «Entrar») y luego la cookie del backend
  const cerrar = useCallback(async () => {
    setSalio(true);
    setUsuario(null);
    olvidarProyecto();
    try { await salirDelBackend(); } catch { /* sin backend: la sesión local ya se cerró */ }
  }, []);

  const valor = useMemo(() => ({ usuario, cargando: usuario === undefined, salio, iniciar, cerrar }),
    [usuario, salio, iniciar, cerrar]);
  return <SesionContext.Provider value={valor}>{children}</SesionContext.Provider>;
}

/* Las pantallas de la app: sin sesión, a «Entrar» (y de vuelta aquí al entrar) */
export function RequiereSesion({ children }) {
  const { usuario, cargando, salio } = useSesion();
  const { pathname, search } = useLocation();
  if (cargando) return null;
  if (!usuario) return <Navigate to={salio ? "/entrar" : `/entrar?volver=${encodeURIComponent(pathname + search)}`} replace />;
  return children;
}

/* A dónde volver tras entrar: solo rutas internas de la app */
export function destinoSeguro(volver) {
  const interna = volver && volver.startsWith("/") && !volver.startsWith("//") && !volver.includes("\\");
  return interna && !volver.startsWith("/entrar") ? volver : "/proyectos";
}
