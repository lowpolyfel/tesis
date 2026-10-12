import { useCallback, useSyncExternalStore } from "react";

/*
 * Modo oscuro (el de siempre) o claro. Se guarda en este navegador y se aplica como
 * <html data-tema="…">: los colores salen de variables CSS (styles/dudamel.css) y la
 * esfera lee el tema para el color del fondo.
 */
const CLAVE = "dudamel.tema";
const oyentes = new Set();

function guardado() {
  try {
    const t = localStorage.getItem(CLAVE);
    if (t === "claro" || t === "oscuro") return t;
  } catch { /* sin almacenamiento */ }
  return "oscuro";
}

export const temaActual = () => document.documentElement.dataset.tema ?? "oscuro";

export function aplicarTema(tema = guardado()) {
  document.documentElement.dataset.tema = tema;
  try { localStorage.setItem(CLAVE, tema); } catch { /* sin almacenamiento */ }
  oyentes.forEach((f) => f());
}

const suscribir = (f) => { oyentes.add(f); return () => oyentes.delete(f); };

export function useTema() {
  const tema = useSyncExternalStore(suscribir, temaActual);
  const alternar = useCallback(() => aplicarTema(temaActual() === "claro" ? "oscuro" : "claro"), []);
  return [tema, alternar];
}

/* Botón redondo ☀/☾ (estilo .boton-icono en styles/dudamel.css) */
export function BotonTema({ className = "" }) {
  const [tema, alternar] = useTema();
  const claro = tema === "claro";
  return (
    <button type="button" onClick={alternar} className={`boton-icono ${className}`}
      aria-label={claro ? "Cambiar a modo oscuro" : "Cambiar a modo claro"} title={claro ? "Modo oscuro" : "Modo claro"}>
      {claro ? "☾" : "☀"}
    </button>
  );
}
