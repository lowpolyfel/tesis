import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useSearchParams } from "react-router";
import { useOrb, usePoseEsfera } from "../orb/useOrb";

const ENLACES = [
  { a: "/inicio", texto: "Analizar" },
  { a: "/proyectos", texto: "Proyectos" },
  { a: "/ambiguedades", texto: "Ambigüedades" },
  { a: "/flujo", texto: "Flujo" },
  { a: "/historial", texto: "Historial" },
  { a: "/lel", texto: "Léxico" },
];
const AJUSTES = [
  { a: "/catalogos", texto: "Catálogos" },
  { a: "/calibracion", texto: "Calibración" },
  { a: "/evaluacion", texto: "Evaluación" },
];

const TITULOS = [
  [/^\/proyectos\/[^/]+/, "Proyecto"],
  [/^\/proyectos/, "Proyectos"],
  [/^\/ambiguedades/, "Ambigüedades"],
  [/^\/historial/, "Historial"],
  [/^\/requisitos\/[^/]+\/validacion/, "Validación"],
  [/^\/requisitos\//, "Traza"],
  [/^\/lel/, "Léxico"],
  [/^\/catalogos/, "Catálogos"],
  [/^\/calibracion/, "Calibración"],
  [/^\/evaluacion/, "Evaluación"],
];

/* En las herramientas la esfera se queda a la izquierda, viva, junto al contenido */
const POSE_HERRAMIENTA = { d: { x: -0.37, y: -0.06, s: 0.46 }, m: { x: 0.34, y: -0.43, s: 0.16 } };

/*
 * Marco de la aplicación.
 *  - "escena": pantallas del flujo; la página coreografía la esfera a pantalla completa
 *  - "herramienta": historial, léxico, catálogos, calibración, evaluación, traza
 * Con ?figura=1 la herramienta se muestra clara y a ancho fijo, para capturas.
 */
export default function Shell({ modo }) {
  const [params] = useSearchParams();
  const figura = params.get("figura") === "1";

  if (figura) {
    return (
      <div className="fixed inset-0 z-30 overflow-auto bg-white text-slate-900">
        <main className="mx-auto w-[1040px] px-8 py-8"><Outlet /></main>
      </div>
    );
  }

  return (
    <>
      <BarraSuperior />
      {modo === "escena" ? <Outlet /> : <Herramienta />}
    </>
  );
}

function BarraSuperior() {
  return (
    <header className="no-print fixed inset-x-0 top-0 z-20 flex items-center justify-between gap-4 px-5 py-5 md:px-10 md:py-7">
      <Link to="/inicio" className="mono flex items-center gap-2.5 text-[11px] text-[var(--bone)] opacity-85 hover:opacity-100">
        <span className="punto" style={{ background: "radial-gradient(circle at 35% 30%,#fffaf0,#d9cdb8)", boxShadow: "0 0 0 1.5px var(--c1),0 0 12px var(--glow)" }} />
        Dudamel
      </Link>
      <nav className="flex flex-wrap justify-end gap-x-5 gap-y-1">
        {ENLACES.map((e) => (
          <NavLink key={e.a} to={e.a} end={e.a === "/lel"} className={claseEnlace}>
            {e.texto}
          </NavLink>
        ))}
        <Ajustes />
      </nav>
    </header>
  );
}

const claseEnlace = ({ isActive }) =>
  `mono text-[10px] transition-colors ${isActive ? "text-[var(--bone)] underline decoration-[var(--c1)] underline-offset-[6px]" : "text-[var(--bone-faint)] hover:text-[var(--bone)]"}`;

/* Catálogos, calibración y evaluación: herramientas de experimentación, agrupadas */
function Ajustes() {
  const [abierto, setAbierto] = useState(false);
  const ref = useRef(null);
  const { pathname } = useLocation();
  const activo = AJUSTES.some((e) => pathname.startsWith(e.a));
  useEffect(() => setAbierto(false), [pathname]);
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e) => { if (!ref.current?.contains(e.target)) setAbierto(false); };
    document.addEventListener("pointerdown", fuera);
    return () => document.removeEventListener("pointerdown", fuera);
  }, [abierto]);
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setAbierto((x) => !x)} className={claseEnlace({ isActive: activo })}>Ajustes ▾</button>
      {abierto && (
        <div className="sube absolute top-7 right-0 flex min-w-40 flex-col gap-3 rounded-xl border border-[var(--line)] bg-[color-mix(in_oklab,var(--bg)_92%,transparent)] p-4 backdrop-blur-xl">
          {AJUSTES.map((e) => <NavLink key={e.a} to={e.a} className={claseEnlace}>{e.texto}</NavLink>)}
        </div>
      )}
    </div>
  );
}

function Herramienta() {
  const { pathname } = useLocation();
  const orb = useOrb();
  const titulo = TITULOS.find(([re]) => re.test(pathname))?.[1] ?? "";
  usePoseEsfera(POSE_HERRAMIENTA, []);

  useEffect(() => {
    orb.update("core", { label: titulo, sub: null });
  }, [orb, titulo]);
  useEffect(() => () => orb.update("core", { label: null, sub: null }), [orb]);

  return (
    <div className="tema-oscuro relative z-10 min-h-screen px-4 pt-28 pb-16 md:pr-10 md:pl-[30vw]">
      <div key={pathname} className="sube mx-auto max-w-5xl">
        <Outlet />
      </div>
    </div>
  );
}
