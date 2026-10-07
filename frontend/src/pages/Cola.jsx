import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { listarProyectos, obtenerCola, resumenProyecto } from "../services/backend";
import { ESTADOS as E, ORDEN_ESTADOS, INFO_VIA, infoEstado } from "../constants/estados";
import EstadoBadge from "../components/EstadoBadge";

/*
 * Historial: todos los requisitos de todos los proyectos, con su estado, y la
 * cola de trabajo del backend (un solo trabajador; ADR 0008). Se refresca
 * mientras haya algo en proceso o esperando turno.
 */
const SONDEO_MS = 2500;
const REPOSO_MS = 10000; // sin trabajo, se revisa con menos frecuencia

const TIPO_TRABAJO = {
  reanudar: "reanuda tras una validación",
  continuar: "continúa un requisito",
  ejecutar: "procesa un requisito",
  analisis: "análisis",
};

export default function Cola() {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const filtro = params.get("estado");
  const proyecto = params.get("proyecto") ?? "";
  const nuevos = useMemo(() => new Set((params.get("nuevos") ?? "").split(",").filter(Boolean)), [params]);

  useEffect(() => {
    let activo = true;
    let t = null;
    const leer = async () => {
      try {
        const [proyectos, cola] = await Promise.all([listarProyectos(), obtenerCola()]);
        // un proyecto que falla no tumba el historial: se omite y se avisa
        const leidos = await Promise.allSettled(proyectos.map((p) => resumenProyecto(p.proyecto_id)));
        const resumenes = leidos.filter((r) => r.status === "fulfilled").map((r) => r.value);
        const fallidos = proyectos.filter((_, i) => leidos[i].status === "rejected").map((p) => p.proyecto_id);
        if (!activo) return;
        const lista = resumenes.flatMap((r) => r.requisitos.map((q) => ({ ...q, proyecto: r.proyecto.nombre })))
          .sort((a, b) => b.creado.localeCompare(a.creado));
        setDatos({ proyectos, cola, lista, fallidos });
        setError(null);
        const ocupado = cola.en_proceso || cola.pendientes.length || lista.some((q) => q.en_proceso);
        t = setTimeout(leer, ocupado ? SONDEO_MS : REPOSO_MS);
      } catch (e) {
        if (activo) { setError(e); t = setTimeout(leer, REPOSO_MS); }
      }
    };
    leer();
    return () => { activo = false; clearTimeout(t); };
  }, []);

  if (error && !datos) return <p className="text-sm text-[var(--danger)]">{error.message}</p>;
  if (!datos) return <p className="text-sm text-[var(--bone-dim)]">Cargando el historial…</p>;

  const delProyecto = proyecto ? datos.lista.filter((q) => q.proyecto_id === proyecto) : datos.lista;
  const conteo = Object.fromEntries(ORDEN_ESTADOS.map((e) => [e, delProyecto.filter((q) => q.estado === e).length]));
  const visibles = filtro ? delProyecto.filter((q) => q.estado === filtro) : delProyecto;
  const actualizar = (cambios) => {
    const p = Object.fromEntries(params);
    setParams(Object.fromEntries(Object.entries({ ...p, ...cambios }).filter(([, v]) => v)), { replace: true });
  };
  const filtrar = (e) => actualizar({ estado: e && e !== filtro ? e : "" });

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end gap-3">
        <div>
          <p className="mono mb-3 text-[10px] text-[var(--bone-faint)]">{datos.lista.length} requisitos · {datos.proyectos.length} proyectos</p>
          <h1>Historial.</h1>
        </div>
        <Link to="/proyectos" className="pill ml-auto">Proyectos</Link>
      </header>

      {datos.fallidos?.length > 0 && (
        <p className="text-sm text-[var(--danger)]">No se pudo leer el resumen de {datos.fallidos.join(", ")}; sus requisitos no aparecen aquí.</p>
      )}

      <ColaTrabajo cola={datos.cola} />

      <div className="flex flex-wrap items-center gap-3">
        <select
          value={proyecto}
          onChange={(e) => actualizar({ proyecto: e.target.value })}
          className="rounded-full border border-[var(--line)] bg-transparent px-3 py-1.5 text-sm"
        >
          <option value="">Todos los proyectos</option>
          {datos.proyectos.map((p) => <option key={p.proyecto_id} value={p.proyecto_id}>{p.nombre}</option>)}
        </select>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrar por estado">
          <button
            onClick={() => filtrar(null)}
            className={`rounded-full px-2.5 py-0.5 text-xs ring-1 ring-inset ${!filtro ? "bg-slate-900 text-sobre ring-slate-900" : "text-slate-600 ring-slate-300"}`}
          >
            Todos ({delProyecto.length})
          </button>
          {ORDEN_ESTADOS.map((e) => (
            <button
              key={e}
              onClick={() => filtrar(e)}
              disabled={!conteo[e] && filtro !== e}
              className={`rounded-full px-2.5 py-0.5 text-xs ring-1 ring-inset disabled:opacity-30 ${filtro === e ? `${infoEstado(e).clase} ring-2` : "text-slate-600 ring-slate-300"}`}
            >
              {infoEstado(e).etiqueta} ({conteo[e]})
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-[var(--line)]">
        <table className="w-full min-w-[640px] table-fixed text-left text-sm">
          <thead className="mono text-[9.5px] text-[var(--bone-faint)]">
            <tr>
              <th className="w-28 px-3 py-2 font-normal">ID</th>
              <th className="px-3 py-2 font-normal">Requisito</th>
              <th className="w-52 px-3 py-2 font-normal">Estado</th>
              <th className="hidden w-20 px-3 py-2 text-right font-normal md:table-cell">Similitud</th>
              <th className="hidden w-36 px-3 py-2 font-normal lg:table-cell">Resolución</th>
            </tr>
          </thead>
          <tbody>
            {visibles.map((q) => {
              const destino = q.estado === E.PENDIENTE_VALIDACION ? `/requisitos/${q.req_id}/validacion` : `/requisitos/${q.req_id}`;
              const via = q.via ? INFO_VIA[q.via] : null;
              return (
                <tr
                  key={q.req_id}
                  onClick={() => navigate(destino)}
                  className={`cursor-pointer border-t border-[var(--line)] hover:bg-white/[0.03] ${nuevos.has(q.req_id) ? "bg-indigo-50" : ""}`}
                >
                  <td className="px-3 py-2 font-mono text-xs">
                    <Link to={destino} onClick={(e) => e.stopPropagation()} className="hover:underline">{q.req_id}</Link>
                    <span className="block truncate text-[10px] text-[var(--bone-faint)]">{q.proyecto} · C{q.ciclo}</span>
                  </td>
                  <td className="px-3 py-2"><p className="line-clamp-2">{q.texto}</p></td>
                  <td className="px-3 py-2">
                    <span className="flex items-center gap-2">
                      <EstadoBadge estado={q.estado} />
                      {q.en_proceso && <span title="Procesando" className="gira" />}
                    </span>
                  </td>
                  <td className="hidden px-3 py-2 text-right font-mono text-xs md:table-cell">{q.similitud_minima?.toFixed(2) ?? "—"}</td>
                  <td className="hidden px-3 py-2 text-xs text-[var(--bone-dim)] lg:table-cell">
                    {via ? <span className="inline-flex items-center gap-1.5"><span className="punto" style={{ background: via.tono }} />{via.etiqueta}</span> : "—"}
                    {q.rondas_max > 0 && <span className="text-[var(--bone-faint)]"> · {q.rondas_max}R</span>}
                  </td>
                </tr>
              );
            })}
            {visibles.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-[var(--bone-dim)]">No hay requisitos con este filtro.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* Qué hace ahora el trabajador del backend y qué espera turno */
function ColaTrabajo({ cola }) {
  if (!cola.en_proceso && cola.pendientes.length === 0) {
    return <p className="mono text-[9.5px] text-[var(--bone-faint)]">Cola vacía: ningún agente trabajando.</p>;
  }
  const enlace = (t) => (t.tipo === "analisis" ? <span>{t.clave}</span> : <Link className="underline" to={`/requisitos/${t.clave}`}>{t.clave}</Link>);
  return (
    <div className="rounded-2xl border border-[var(--line)] p-4 text-sm">
      {cola.en_proceso && (
        <p className="flex items-center gap-2"><span className="gira" /> Ahora: {TIPO_TRABAJO[cola.en_proceso.tipo] ?? cola.en_proceso.tipo} {enlace(cola.en_proceso)}</p>
      )}
      {cola.pendientes.length > 0 && (
        <p className="mono mt-2 text-[9.5px] text-[var(--bone-faint)]">
          En espera ({cola.pendientes.length}):{" "}
          {cola.pendientes.slice(0, 12).map((t, i) => <span key={`${t.tipo}-${t.clave}`}>{i ? ", " : ""}{enlace(t)}</span>)}
          {cola.pendientes.length > 12 && " …"}
        </p>
      )}
    </div>
  );
}
