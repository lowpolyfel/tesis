import { NavLink, Navigate, useParams } from "react-router";
import { useApi } from "../hooks/useApi";
import { obtenerCatalogos } from "../services/backend";
import { tipo as infoTipo } from "../constants/agentes";

/*
 * Catálogos que usan los filtros deterministas (ADR 0003): regionales (siempre
 * pasan al Clasificador) y vaguedad (se marcan y no se debaten). Son de solo
 * lectura: se editan en data/catalogos/*.json (CATALOGOS_DIR), versionados con git, y
 * cada traza guarda la versión con la que corrió.
 */
const TIPOS = {
  regionales: { titulo: "Regionales", tono: "regional" },
  vaguedad: { titulo: "Vaguedad", tono: "vaguedad" },
};

export default function Catalogos() {
  const { tipo } = useParams();
  const { datos, error } = useApi(obtenerCatalogos);

  if (!TIPOS[tipo]) return <Navigate to="/catalogos/regionales" replace />;
  if (error) return <p className="text-sm text-[var(--danger)]">{error.message}</p>;
  if (!datos) return <p className="text-sm text-[var(--bone-dim)]">Cargando catálogos…</p>;

  const cat = datos[tipo];

  return (
    <div className="space-y-5">
      <header className="space-y-2">
        <p className="mono text-[10px] text-[var(--bone-faint)]">Filtros deterministas · {datos.nota}</p>
        <h1>Catálogos.</h1>
      </header>

      <div className="mono flex gap-5 border-b border-[var(--line)] pb-3 text-[10px]">
        {Object.entries(TIPOS).map(([k, v]) => (
          <NavLink
            key={k}
            to={`/catalogos/${k}`}
            className={({ isActive }) => (isActive ? "text-[var(--bone)] underline decoration-[var(--c1)] underline-offset-[8px]" : "text-[var(--bone-faint)] hover:text-[var(--bone)]")}
          >
            {v.titulo} ({datos[k]?.terminos?.length ?? 0})
          </NavLink>
        ))}
      </div>

      {!cat ? (
        <p className="text-sm text-[var(--bone-dim)]">El backend no cargó este catálogo.</p>
      ) : (
        <>
          <p className="max-w-3xl text-sm text-[var(--bone-dim)]">{cat.descripcion}</p>
          <p className="mono text-[9.5px] text-[var(--bone-faint)]">versión {cat.version} · archivo data/catalogos/{tipo}.json</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="mono text-[9px] text-[var(--bone-faint)]">
                <tr>
                  <th className="py-1.5 font-normal">Expresión</th>
                  <th className="py-1.5 font-normal">Clasificación</th>
                  <th className="py-1.5 font-normal">{tipo === "regionales" ? "Significados posibles" : "Tipo y nota"}</th>
                  <th className="py-1.5 font-normal">Formas que reconoce</th>
                </tr>
              </thead>
              <tbody>
                {cat.terminos.map((t) => (
                  <tr key={t.expresion} className="border-t border-[var(--line)] align-top">
                    <td className="py-2 pr-3"><span className={`rounded px-1.5 ${infoTipo(TIPOS[tipo].tono).clase}`}>{t.expresion}</span></td>
                    <td className="py-2 pr-3 text-[var(--bone-dim)]">{t.clasificacion ?? "—"}</td>
                    <td className="py-2 pr-3">
                      {tipo === "regionales"
                        ? (t.significados_posibles ?? []).join(" · ")
                        : [t.tipo, t.nota].filter(Boolean).join(" — ")}
                    </td>
                    <td className="mono py-2 text-[10px] text-[var(--bone-faint)]">{(t.formas ?? []).join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
