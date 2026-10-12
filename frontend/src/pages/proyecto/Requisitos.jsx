import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { ESTADOS as E, MOOD_SIMPLE, estadoSimple } from "../../constants/estados";
import { seccion } from "../../components/orb/secciones";
import { useOrb } from "../../components/orb/useOrb";
import { Confirmar, EstadoChip, Vacio } from "../../components/ui";
import { cancelarRequisitos, reanalizarRequisitos } from "../../services/backend";

/*
 * Los requisitos del proyecto, por carga (ciclo KMoS-SSA), con su estado en
 * lenguaje claro. Se pueden elegir varios para armar su mapa (Big Picture) o
 * ver solo su especificación, y los que terminaron en error por algo ajeno al
 * texto (una clave sin acceso al modelo, Ollama apagado) se pueden volver a
 * analizar: queda una versión nueva y la del error se oculta. Al pasar por un
 * requisito, la esfera toma el tono de su estado.
 */
const FILTROS = [
  ["todos", "Todos"],
  ["listo", "Listos"],
  ["revisar", "Por revisar"],
  ["analizando", "Analizando"],
  ["error", "Con error"],
];

export default function Requisitos({ r, onElegir, onCambio }) {
  const orb = useOrb();
  const navigate = useNavigate();
  const [filtro, setFiltro] = useState("todos");
  const [elegidos, setElegidos] = useState(() => new Set());
  const [anteriores, setAnteriores] = useState(false); // ver las versiones con error ya reanalizadas
  const [reanalizando, setReanalizando] = useState(false);
  const [falloReanalisis, setFalloReanalisis] = useState(null);
  const [descartando, setDescartando] = useState(false); // confirmar cancelar y descartar
  const pid = r.proyecto.proyecto_id;
  const reemplazados = r.requisitos.filter((q) => q.reemplazado_por).length;

  const visibles = r.requisitos.filter((q) => {
    if (q.reemplazado_por && !anteriores) return false;
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
  const fallidos = [...elegidos].filter((id) => {
    const q = r.requisitos.find((x) => x.req_id === id);
    return q?.estado === E.ERROR && !q.reemplazado_por;
  });
  // lo que no ha terminado: se cancela su análisis y se descarta por completo
  const sinTerminar = [...elegidos].filter((id) => {
    const e = estadoSimple(r.requisitos.find((x) => x.req_id === id)?.estado).id;
    return e === "cola" || e === "analizando" || e === "revisar";
  });
  const reanalizar = async (ids) => {
    setReanalizando(true);
    setFalloReanalisis(null);
    try {
      const { req_ids: nuevos } = await reanalizarRequisitos(pid, ids);
      navigate(`/analisis?proyecto=${pid}&ids=${nuevos.join(",")}`);
    } catch (e) {
      setFalloReanalisis(e.message);
      setReanalizando(false);
    }
  };
  const cuenta = (id) => r.requisitos.filter((q) => !q.reemplazado_por).filter((q) => {
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
        {reemplazados > 0 && (
          <button className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setAnteriores((x) => !x)}>
            {anteriores ? "ocultar" : "ver"} {reemplazados} {reemplazados === 1 ? "versión" : "versiones"} con error ya {reemplazados === 1 ? "reanalizada" : "reanalizadas"}
          </button>
        )}
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
                    <span className={`min-w-0 flex-1 text-[15px] leading-relaxed sm:order-2 ${q.reemplazado_por ? "text-[var(--bone-faint)]" : ""}`}>
                      {q.texto}
                      {q.reemplazado_por && <span className="mono ml-2 text-[10px]">· se volvió a analizar como {q.reemplazado_por}</span>}
                    </span>
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
            {fallidos.length > 0 && <span className="text-[var(--bone-faint)]"> · {fallidos.length} con error</span>}
            {falloReanalisis && <span className="block text-[13px] text-[var(--danger)]">{falloReanalisis}</span>}
          </p>
          <button className="pill sm" disabled={!listos.length} onClick={() => onElegir("mapa", listos)}>Crear mapa</button>
          <button className="pill ghost sm" disabled={!listos.length} onClick={() => onElegir("especificacion", listos)}>Ver especificación</button>
          {fallidos.length > 0 && (
            <button className="pill ghost sm" disabled={reanalizando} onClick={() => reanalizar(fallidos)}
              title="Para los que fallaron por algo ajeno al texto: una clave sin acceso al modelo, Ollama apagado…">
              {reanalizando ? "Enviando…" : `Volver a analizar (${fallidos.length})`}
            </button>
          )}
          {sinTerminar.length > 0 && (
            <button className="pill ghost sm" onClick={() => setDescartando(true)}>Cancelar y descartar ({sinTerminar.length})</button>
          )}
          <button className="mono px-2 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setElegidos(new Set())}>Quitar</button>
          {descartando && (
            <div className="basis-full">
              <Confirmar
                pregunta={`¿Cancelar el análisis y descartar ${sinTerminar.length === 1 ? "este requisito" : `estos ${sinTerminar.length} requisitos`}?`}
                detalle={`Se borran por completo: ${sinTerminar.join(", ")}. El que se está analizando se detiene al terminar el paso en curso.`}
                accion="Cancelar y descartar" enviando="Descartando…" volver="No"
                onCancelar={() => setDescartando(false)}
                onConfirmar={async () => {
                  await cancelarRequisitos(pid, sinTerminar);
                  setDescartando(false);
                  setElegidos(new Set());
                  onCambio?.();
                }} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
