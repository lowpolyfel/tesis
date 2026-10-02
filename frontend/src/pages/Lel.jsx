import { Link, useSearchParams } from "react-router";
import { useApi } from "../hooks/useApi";
import { obtenerLel } from "../services/api";
import { TIPOS_LEL } from "../constants/agentes";

const normalizar = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/* Pantalla 6: léxico acumulado, con búsqueda por símbolo y filtro por tipo */
export default function Lel() {
  const { datos: entradas, cargando } = useApi(obtenerLel);
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const tipo = params.get("tipo") ?? "";
  const actualizar = (cambios) => {
    const p = Object.fromEntries(params);
    setParams(Object.fromEntries(Object.entries({ ...p, ...cambios }).filter(([, v]) => v)), { replace: true });
  };

  if (cargando) return <p className="text-sm text-slate-500">Cargando el LEL…</p>;

  const visibles = entradas
    .filter((e) => !tipo || e.tipo === tipo)
    .filter((e) => !q || [e.simbolo, ...(e.sinonimos ?? [])].some((s) => normalizar(s).includes(normalizar(q))))
    .sort((a, b) => a.simbolo.localeCompare(b.simbolo, "es"));

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">LEL acumulado</h1>
        <p className="text-sm text-slate-500">{entradas.length} símbolos formalizados. Cada entrada enlaza al requisito donde se resolvió.</p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <input
          value={q}
          onChange={(e) => actualizar({ q: e.target.value })}
          placeholder="Buscar símbolo o sinónimo…"
          className="w-64 rounded border border-slate-300 px-3 py-1.5 text-sm"
        />
        <div className="flex gap-1.5">
          {["", ...TIPOS_LEL].map((t) => (
            <button
              key={t || "todos"}
              onClick={() => actualizar({ tipo: t })}
              className={`rounded-full px-2.5 py-0.5 text-xs ring-1 ring-inset ${tipo === t ? "bg-slate-900 text-sobre ring-slate-900" : "bg-white ring-slate-300"}`}
            >
              {t || "todos"} ({t ? entradas.filter((e) => e.tipo === t).length : entradas.length})
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {visibles.map((e) => (
          <article key={e.id} className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
            <header className="mb-2 flex flex-wrap items-baseline gap-2">
              <h2 className="text-base font-semibold">{e.simbolo}</h2>
              <span className="rounded bg-slate-100 px-1.5 text-xs text-slate-600">{e.tipo}</span>
              <Link to={`/requisitos/${e.requisitoId}`} className="ml-auto font-mono text-xs text-indigo-700 hover:underline">
                resuelto en {e.requisitoId} →
              </Link>
            </header>
            {e.sinonimos?.length > 0 && <p className="mb-2 text-xs text-slate-500">Sinónimos: {e.sinonimos.join(", ")}</p>}
            <p className="text-xs font-medium text-slate-500">Noción</p>
            <ul className="mb-2 list-disc pl-5">{e.nocion.map((x, i) => <li key={i}>{x}</li>)}</ul>
            <p className="text-xs font-medium text-slate-500">Impacto</p>
            <ul className="list-disc pl-5">{e.impacto.map((x, i) => <li key={i}>{x}</li>)}</ul>
          </article>
        ))}
        {visibles.length === 0 && <p className="text-sm text-slate-500">Ningún símbolo coincide.</p>}
      </div>
    </div>
  );
}
