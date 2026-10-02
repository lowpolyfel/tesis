import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { seguirCola } from "../services/polling";
import { ORDEN_ESTADOS, INFO_ESTADO, VIAS_RESOLUCION as V, estaEnProceso } from "../constants/estados";
import EstadoBadge from "../components/EstadoBadge";

const VIA = { [V.DIRECTO]: "directo", [V.CONSENSO]: "consenso", [V.ARBITRAJE]: "arbitraje" };

/* Pantalla 2: todos los requisitos con su estado; se refresca mientras haya trabajo en curso */
export default function Cola() {
  const [lista, setLista] = useState(null);
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const filtro = params.get("estado");
  const nuevos = useMemo(() => new Set((params.get("nuevos") ?? "").split(",").filter(Boolean)), [params]);

  useEffect(() => seguirCola(setLista), []);

  if (!lista) return <p className="text-sm text-slate-500">Cargando la cola…</p>;

  const conteo = Object.fromEntries(ORDEN_ESTADOS.map((e) => [e, lista.filter((r) => r.estado === e).length]));
  const visibles = filtro ? lista.filter((r) => r.estado === filtro) : lista;
  const filtrar = (e) => setParams(e && e !== filtro ? { estado: e } : {});

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Historial</h1>
        <span className="text-sm text-slate-500">{lista.length} requisitos</span>
        <Link to="/inicio" className="ml-auto rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-sobre hover:bg-slate-700">
          + Analizar documento
        </Link>
      </header>

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrar por estado">
        <button
          onClick={() => filtrar(null)}
          className={`rounded-full px-2.5 py-0.5 text-xs ring-1 ring-inset ${!filtro ? "bg-slate-900 text-sobre ring-slate-900" : "bg-white text-slate-600 ring-slate-300"}`}
        >
          Todos ({lista.length})
        </button>
        {ORDEN_ESTADOS.map((e) => (
          <button
            key={e}
            onClick={() => filtrar(e)}
            disabled={!conteo[e] && filtro !== e}
            className={`rounded-full px-2.5 py-0.5 text-xs ring-1 ring-inset disabled:opacity-40 ${filtro === e ? `${INFO_ESTADO[e].clase} ring-2` : "bg-white text-slate-600 ring-slate-300"}`}
          >
            {INFO_ESTADO[e].etiqueta} ({conteo[e]})
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full table-fixed text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="w-24 px-3 py-2">ID</th>
              <th className="px-3 py-2">Requisito</th>
              <th className="w-48 px-3 py-2">Estado</th>
              <th className="hidden w-24 px-3 py-2 text-right md:table-cell">Similitud</th>
              <th className="hidden w-28 px-3 py-2 lg:table-cell">Resolución</th>
            </tr>
          </thead>
          <tbody>
            {visibles.map((r) => (
              <tr
                key={r.id}
                onClick={() => navigate(`/requisitos/${r.id}`)}
                className={`cursor-pointer border-t border-slate-100 hover:bg-slate-50 ${nuevos.has(r.id) ? "bg-indigo-50/60" : ""}`}
              >
                <td className="px-3 py-2 font-mono text-xs">
                  <Link to={`/requisitos/${r.id}`} onClick={(e) => e.stopPropagation()} className="hover:underline">{r.id}</Link>
                </td>
                <td className="px-3 py-2"><p className="line-clamp-2">{r.texto}</p></td>
                <td className="px-3 py-2">
                  <span className="flex items-center gap-2">
                    <EstadoBadge estado={r.estado} />
                    {estaEnProceso(r.estado) && (
                      <span title="Procesando" className="h-3 w-3 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
                    )}
                  </span>
                </td>
                <td className="hidden px-3 py-2 text-right font-mono md:table-cell">{r.similitud?.toFixed(2) ?? "—"}</td>
                <td className="hidden px-3 py-2 text-slate-600 lg:table-cell">
                  {r.via ? VIA[r.via] : "—"}
                  {r.rondas > 0 && <span className="text-slate-400"> · {r.rondas}R</span>}
                </td>
              </tr>
            ))}
            {visibles.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-slate-500">No hay requisitos en este estado.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
