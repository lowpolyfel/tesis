import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { ESTADOS as E, MOOD_SIMPLE, estadoSimple } from "../../constants/estados";
import { seccion } from "../../components/orb/secciones";
import { useOrb } from "../../components/orb/useOrb";
import { EstadoChip, Vacio } from "../../components/ui";

/*
 * Los requisitos del proyecto, por carga (ciclo KMoS-SSA), con su estado en
 * lenguaje claro. Se pueden elegir varios para armar su mapa (Big Picture) o
 * ver solo su especificación. Al pasar por un requisito, la esfera toma el tono
 * de su estado.
 */
const FILTROS = [
  ["todos", "Todos"],
  ["listo", "Listos"],
  ["revisar", "Por revisar"],
  ["analizando", "Analizando"],
  ["error", "Con error"],
];

export default function Requisitos({ r, onElegir }) {
  const orb = useOrb();
  const navigate = useNavigate();
  const [filtro, setFiltro] = useState("todos");
  const [elegidos, setElegidos] = useState(() => new Set());
  const pid = r.proyecto.proyecto_id;

  const visibles = r.requisitos.filter((q) => {
    const s = estadoSimple(q.estado).id;
    return filtro === "todos" || s === filtro || (filtro === "analizando" && s === "cola");
  });
  const cargas = useMemo(() => {
    const m = new Map();
    for (const q of visibles) m.set(q.ciclo, [...(m.get(q.ciclo) ?? []), q]);
    return [...m.entries()].sort((a, b) => b[0] - a[0]);
  }, [visibles]);

  if (!r.requisitos.length) {
    return (
      <Vacio accion={r.proyecto.tipo !== "evaluacion" && <Link className="pill" to={`/proyectos/${pid}/analizar`}>Analizar requisitos</Link>}>
        {r.proyecto.tipo === "evaluacion" ? "Los requisitos de este proyecto los carga la evaluación del corpus." : "Aún no hay requisitos. Pega o sube los tuyos."}
      </Vacio>
    );
  }

  const alternar = (id) => setElegidos((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });
  const todos = visibles.length > 0 && visibles.every((q) => elegidos.has(q.req_id));
  const listos = [...elegidos].filter((id) => r.requisitos.find((q) => q.req_id === id)?.estado === E.FORMALIZADO);
  const cuenta = (id) => r.requisitos.filter((q) => {
    const s = estadoSimple(q.estado).id;
    return s === id || (id === "analizando" && s === "cola");
  }).length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <label className="flex cursor-pointer items-center gap-2.5 text-[13px] text-[var(--bone-dim)]">
          <input type="checkbox" className="casilla" checked={todos}
            onChange={() => setElegidos(todos ? new Set() : new Set(visibles.map((q) => q.req_id)))} />
          Elegir {filtro === "todos" ? "todos" : "estos"}
        </label>
        <div className="ml-auto flex flex-wrap gap-1">
          {FILTROS.filter(([id]) => id === "todos" || cuenta(id) > 0).map(([id, texto]) => (
            <button key={id} onClick={() => setFiltro(id)}
              className={`mono rounded-full px-3 py-1.5 text-[10px] ${filtro === id ? "bg-[var(--bone)] text-[#16130f]" : "text-[var(--bone-faint)] hover:text-[var(--bone)]"}`}>
              {texto}{id !== "todos" && ` ${cuenta(id)}`}
            </button>
          ))}
        </div>
      </div>

      {cargas.map(([ciclo, reqs]) => (
        <section key={ciclo} className="space-y-1">
          <p className="etiqueta flex items-center gap-3 pb-1">
            Carga {ciclo} · {reqs.length}
            <Link className="normal-case tracking-normal text-[11px] hover:text-[var(--bone)]"
              to={`/analisis?proyecto=${pid}&ids=${reqs.map((q) => q.req_id).join(",")}&escena=1`}>
              ver en la escena
            </Link>
          </p>
          <ol className="tarjeta divide-y divide-[var(--line)] overflow-hidden">
            {reqs.map((q) => {
              const destino = q.estado === E.PENDIENTE_VALIDACION ? `/requisitos/${q.req_id}/validacion` : `/requisitos/${q.req_id}`;
              return (
                <li key={q.req_id}
                  onPointerEnter={() => orb.setMood(MOOD_SIMPLE[estadoSimple(q.estado).id])}
                  onPointerLeave={() => orb.setMood(seccion("requisitos").mood)}
                  className="flex items-start gap-4 px-4 py-3.5 transition-colors hover:bg-white/[0.03]">
                  <input type="checkbox" aria-label={`Elegir ${q.req_id}`} className="casilla mt-1" checked={elegidos.has(q.req_id)} onChange={() => alternar(q.req_id)} />
                  <button onClick={() => navigate(destino)} className="flex min-w-0 flex-1 flex-col gap-1.5 text-left sm:flex-row sm:items-baseline sm:gap-4">
                    <span className="flex items-center justify-between gap-3 sm:contents">
                      <span className="mono w-10 shrink-0 text-[10px] text-[var(--bone-faint)] sm:order-1">{q.req_id}</span>
                      <EstadoChip estado={q.estado} className="sm:order-3" />
                    </span>
                    <span className="min-w-0 flex-1 text-[15px] leading-relaxed sm:order-2">{q.texto}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
      {!visibles.length && <p className="text-[14px] text-[var(--bone-faint)]">Ningún requisito con ese estado.</p>}

      {elegidos.size > 0 && (
        <div className="sticky bottom-4 z-10 tarjeta flex flex-wrap items-center gap-3 px-4 py-3 shadow-2xl">
          <p className="min-w-0 flex-1 text-[14px]">
            <b className="font-medium">{elegidos.size}</b> elegido{elegidos.size === 1 ? "" : "s"}
            {listos.length < elegidos.size && <span className="text-[var(--bone-faint)]"> · {listos.length} listo{listos.length === 1 ? "" : "s"} para el mapa</span>}
          </p>
          <button className="pill sm" disabled={!listos.length} onClick={() => onElegir("mapa", listos)}>Crear mapa</button>
          <button className="pill ghost sm" disabled={!listos.length} onClick={() => onElegir("especificacion", listos)}>Ver especificación</button>
          <button className="mono px-2 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setElegidos(new Set())}>Quitar</button>
        </div>
      )}
    </div>
  );
}
