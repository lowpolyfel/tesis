import { Link, NavLink, useNavigate } from "react-router";
import { reiniciarDatosDePrueba } from "../../services/api";

const SECCIONES = [
  {
    titulo: "Flujo",
    enlaces: [
      { a: "/cargar", texto: "1 · Cargar requisitos" },
      { a: "/cola", texto: "2 · Cola de requisitos" },
    ],
  },
  {
    titulo: "Resultados",
    enlaces: [{ a: "/lel", texto: "6 · LEL acumulado" }],
  },
  {
    titulo: "Experimentación",
    enlaces: [
      { a: "/catalogos", texto: "7 · Catálogos regionales" },
      { a: "/calibracion", texto: "8 · Calibración" },
      { a: "/evaluacion", texto: "9 · Corpus y evaluación" },
    ],
  },
];

export default function Nav() {
  const navigate = useNavigate();

  const reiniciar = async () => {
    if (!confirm("¿Restaurar todos los datos de prueba? Se pierden los cambios hechos en esta sesión.")) return;
    await reiniciarDatosDePrueba();
    navigate("/cola");
    window.location.reload();
  };

  return (
    <aside className="no-print border-b border-slate-200 bg-white md:sticky md:top-0 md:h-screen md:w-60 md:shrink-0 md:border-r md:border-b-0">
      <div className="flex h-full flex-col gap-6 p-4">
        <Link to="/" className="flex items-center gap-2 font-semibold tracking-wide">
          <span className="h-3 w-3 rounded-full bg-gradient-to-br from-indigo-400 to-violet-500" />
          Dudamel
        </Link>
        <nav className="flex flex-wrap gap-x-6 gap-y-4 md:flex-col">
          {SECCIONES.map((s) => (
            <div key={s.titulo}>
              <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-400">{s.titulo}</p>
              <ul className="space-y-0.5">
                {s.enlaces.map((e) => (
                  <li key={e.a}>
                    <NavLink
                      to={e.a}
                      className={({ isActive }) =>
                        `block rounded px-2 py-1 text-sm ${isActive ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"}`
                      }
                    >
                      {e.texto}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="mt-auto space-y-2 text-xs text-slate-500">
          <p>Datos de prueba: el backend aún no está conectado.</p>
          <button type="button" onClick={reiniciar} className="underline hover:text-slate-800">
            Restaurar datos de prueba
          </button>
        </div>
      </div>
    </aside>
  );
}
