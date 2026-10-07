import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useSearchParams } from "react-router";
import { useOrb } from "../orb/useOrb";
import { isMobile } from "../orb/poses";
import { poseSeccion, seccion } from "../orb/secciones";
import Orbita from "../orb/Orbita";
import { proyectoRecordado } from "../proyectoRecordado";
import { Volver } from "../ui";

/*
 * Marco de la aplicación.
 *  - "escena": analizar y la escena en vivo; la página coreografía la esfera.
 *  - "herramienta": todo lo demás. El contenido va en una columna al centro y la
 *    esfera principal vive enorme en el margen de la sección; al cambiar de
 *    sección cruza al otro lado. Tocarla (o «Menú») abre el menú de la esfera.
 * Con ?figura=1 la herramienta se muestra clara y a ancho fijo, para capturas.
 */

/* La sección de la ruta: define el lado, la altura y el tono de la esfera */
export function seccionDe(pathname, params) {
  if (/^\/proyectos\/[^/]+\/analizar/.test(pathname)) return "analizar";
  if (/^\/proyectos\/[^/]+/.test(pathname)) {
    const vista = params.get("vista");
    return ["especificacion", "lexico", "mapa"].includes(vista) ? vista : "requisitos";
  }
  if (pathname === "/proyectos") return "proyectos";
  if (pathname === "/mas") return "mas";
  if (/^\/requisitos\/[^/]+\/validacion/.test(pathname)) return "revision";
  if (/^\/requisitos\//.test(pathname)) return "requisito";
  return "avanzado";
}

/* El proyecto en el que está la persona: el de la ruta, el de ?proyecto= o el último abierto */
function proyectoActual(pathname, params) {
  const m = pathname.match(/^\/proyectos\/([^/]+)/);
  return m?.[1] ?? params.get("proyecto") ?? proyectoRecordado();
}

function destinosDelMenu(pid) {
  const base = [{ id: "proyectos", etiqueta: "Proyectos", a: "/proyectos", mood: "idle" }];
  if (pid) {
    base.push(
      { id: "analizar", etiqueta: "Analizar", a: `/proyectos/${pid}/analizar`, mood: "listening" },
      { id: "requisitos", etiqueta: "Requisitos", a: `/proyectos/${pid}`, mood: seccion("requisitos").mood },
      { id: "especificacion", etiqueta: "Especificación", a: `/proyectos/${pid}?vista=especificacion`, mood: seccion("especificacion").mood },
      { id: "lexico", etiqueta: "Léxico", a: `/proyectos/${pid}?vista=lexico`, mood: seccion("lexico").mood },
      { id: "mapa", etiqueta: "Mapa", a: `/proyectos/${pid}?vista=mapa`, mood: seccion("mapa").mood },
    );
  }
  base.push({ id: "mas", etiqueta: "Más", a: pid ? `/mas?proyecto=${pid}` : "/mas", mood: "sistema" });
  return base;
}

export default function Shell({ modo }) {
  const [params] = useSearchParams();
  const { pathname } = useLocation();
  const figura = params.get("figura") === "1";
  const [menu, setMenu] = useState(false);
  const abrirMenu = useCallback(() => setMenu(true), []);
  const pid = proyectoActual(pathname, params);
  const destinos = useMemo(() => destinosDelMenu(pid), [pid]);

  useEffect(() => setMenu(false), [pathname]);

  if (figura) {
    return (
      <div className="fixed inset-0 z-30 overflow-auto bg-white text-slate-900">
        <main className="mx-auto w-[1040px] px-8 py-8"><Outlet /></main>
      </div>
    );
  }

  return (
    <>
      <BarraSuperior pid={pid} onMenu={modo === "escena" ? null : abrirMenu} />
      {modo === "escena" ? <Outlet /> : <Herramienta onMenu={abrirMenu} />}
      {modo !== "escena" && <Orbita abierta={menu} onCerrar={() => setMenu(false)} destinos={destinos} />}
    </>
  );
}

/* Barra mínima: la marca, los proyectos, «Más» y el menú de la esfera */
function BarraSuperior({ pid, onMenu }) {
  const enlace = ({ isActive }) =>
    `mono text-[10.5px] transition-colors ${isActive ? "text-[var(--bone)]" : "text-[var(--bone-faint)] hover:text-[var(--bone)]"}`;
  return (
    <header data-barra className="no-print fixed inset-x-0 top-0 z-30 flex items-center justify-between gap-4 bg-[linear-gradient(to_bottom,var(--bg)_55%,transparent)] px-5 pt-5 pb-8 md:px-10 md:pt-6">
      <Link to="/proyectos" className="mono flex items-center gap-2.5 text-[11px] text-[var(--bone)] opacity-90 hover:opacity-100">
        <span className="punto" style={{ background: "radial-gradient(circle at 35% 30%,#fffaf0,#d9cdb8)", boxShadow: "0 0 0 1.5px var(--c1),0 0 12px var(--glow)" }} />
        Dudamel
      </Link>
      <nav className="flex items-center gap-5 md:gap-7">
        <NavLink to="/proyectos" end className={enlace}>Proyectos</NavLink>
        <NavLink to={pid ? `/mas?proyecto=${pid}` : "/mas"} className={enlace}>Más</NavLink>
        {onMenu && (
          <button onClick={onMenu} className="mono flex items-center gap-2 rounded-full border border-[var(--line)] px-3 py-1.5 text-[10.5px] text-[var(--bone-dim)] hover:border-[var(--c1)] hover:text-[var(--bone)]" aria-haspopup="dialog">
            <span className="punto" style={{ background: "var(--c1)", boxShadow: "0 0 10px var(--glow)" }} /> Menú
          </button>
        )}
      </nav>
    </header>
  );
}

/*
 * La columna de contenido y la esfera de la sección. La capa exterior no recibe
 * el puntero: en los márgenes, el clic llega a la esfera (que abre el menú).
 */
function Herramienta({ onMenu }) {
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const orb = useOrb();
  const sec = seccionDe(pathname, params);
  const pid = params.get("proyecto");
  const ancha = sec === "avanzado"; // tablas anchas de las herramientas de experimentación

  useEffect(() => {
    const colocar = () => orb.setPose(poseSeccion(sec, ancha ? 1080 : undefined));
    colocar();
    orb.setMood(seccion(sec).mood);
    orb.update("core", { label: null, sub: null, active: false });
    orb.poke(0.6);
    addEventListener("resize", colocar);
    return () => removeEventListener("resize", colocar);
  }, [orb, sec, ancha]);

  // la esfera se puede tocar mientras se está en una herramienta
  useEffect(() => {
    orb.update("core", { onClick: onMenu });
    return () => orb.update("core", { onClick: undefined });
  }, [orb, onMenu]);

  return (
    <div className="tema-oscuro pointer-events-none relative z-10 min-h-screen px-4 pt-24 pb-20 md:pt-28">
      <div key={pathname} className={`aparece pointer-events-auto mx-auto ${ancha ? "max-w-[1080px]" : "max-w-[860px]"} ${isMobile() ? "pb-[36vh]" : ""}`}>
        {/* las herramientas de «Más» regresan a «Más» */}
        {sec === "avanzado" && <div className="mb-6"><Volver a={pid ? `/mas?proyecto=${pid}` : "/mas"}>Más</Volver></div>}
        <Outlet />
      </div>
    </div>
  );
}
