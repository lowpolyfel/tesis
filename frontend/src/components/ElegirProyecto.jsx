import { useEffect } from "react";
import { useSearchParams } from "react-router";
import { useApi } from "../hooks/useApi";
import { listarProyectos } from "../services/backend";
import { proyectoRecordado, recordarProyecto } from "./SelectorProyecto";

/*
 * Las vistas de análisis (ambigüedades, comparaciones, flujo, calibración) son
 * por proyecto: el proyecto vive en `?proyecto=` para que el enlace se pueda
 * compartir. Sin parámetro se usa el último elegido o el más reciente.
 */
export function useProyectoElegido() {
  const [params, setParams] = useSearchParams();
  const { datos: proyectos, error } = useApi(listarProyectos);
  const proyectoId = params.get("proyecto");

  const elegir = (id) => {
    recordarProyecto(id);
    setParams((prev) => {
      const p = new URLSearchParams(prev);
      p.set("proyecto", id);
      return p;
    }, { replace: true });
  };

  useEffect(() => {
    if (proyectoId || !proyectos?.length) return;
    const recordado = proyectoRecordado();
    const normales = proyectos.filter((p) => p.tipo !== "evaluacion");
    const id = proyectos.some((p) => p.proyecto_id === recordado)
      ? recordado
      : (normales.filter((p) => p.proyecto_id !== "P00").at(-1) ?? normales[0])?.proyecto_id;
    if (id) elegir(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [proyectoId, proyectos]);

  const proyecto = proyectos?.find((p) => p.proyecto_id === proyectoId) ?? null;
  return { proyectoId, proyecto, proyectos: proyectos ?? [], elegir, error };
}

export default function ElegirProyecto({ proyectoId, proyectos, onCambio }) {
  const normales = proyectos.filter((p) => p.tipo !== "evaluacion");
  const evaluaciones = proyectos.filter((p) => p.tipo === "evaluacion");
  const opcion = (p) => <option key={p.proyecto_id} value={p.proyecto_id} className="bg-[#16130f]">{p.proyecto_id} · {p.nombre}</option>;
  return (
    <select
      value={proyectoId ?? ""}
      onChange={(e) => onCambio(e.target.value)}
      aria-label="Proyecto"
      className="w-fit max-w-full cursor-pointer rounded-full border border-[var(--line)] bg-transparent px-3 py-1.5 text-[12px] text-[var(--bone)] outline-none hover:border-[var(--c1)]"
    >
      {!proyectoId && <option value="" className="bg-[#16130f]">Elige un proyecto…</option>}
      {normales.map(opcion)}
      {evaluaciones.length > 0 && <optgroup label="Evaluación" className="bg-[#16130f]">{evaluaciones.map(opcion)}</optgroup>}
    </select>
  );
}
