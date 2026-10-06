import { useEffect, useState } from "react";
import { crearProyecto, listarProyectos } from "../services/backend";

/* Elegir el proyecto donde caerán los requisitos (o crear uno) */
const CLAVE = "dudamel.proyecto";
export const proyectoRecordado = () => {
  try { return localStorage.getItem(CLAVE); } catch { return null; }
};

export default function SelectorProyecto({ valor, onCambio }) {
  const [proyectos, setProyectos] = useState([]);
  const [creando, setCreando] = useState(false);
  const [nombre, setNombre] = useState("");

  const elegir = (id) => {
    try { localStorage.setItem(CLAVE, id); } catch { /* sin almacenamiento */ }
    onCambio(id);
  };

  const [error, setError] = useState(null);
  const normales = proyectos.filter((p) => p.tipo !== "evaluacion");

  useEffect(() => {
    listarProyectos()
      .then((l) => {
        setProyectos(l);
        const opciones = l.filter((p) => p.tipo !== "evaluacion");
        if (!valor || !opciones.some((p) => p.proyecto_id === valor)) {
          // el más reciente que no sea el General; si no hay, el General
          elegir((opciones.filter((p) => p.proyecto_id !== "P00").at(-1) ?? opciones[0])?.proyecto_id);
        }
      })
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const crear = async () => {
    if (!nombre.trim()) return;
    try {
      const p = await crearProyecto({ nombre });
      setProyectos(await listarProyectos());
      setNombre("");
      setCreando(false);
      elegir(p.proyecto_id);
    } catch (e) {
      setError(e.message);
    }
  };

  if (error) return <p className="mono text-[10px] text-[var(--danger)]">{error}</p>;

  return (
    <div className="mono flex flex-wrap items-center justify-center gap-3 text-[10px] text-[var(--bone-faint)]">
      <span>Proyecto</span>
      {creando ? (
        <>
          <input
            autoFocus
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") crear(); if (e.key === "Escape") setCreando(false); }}
            placeholder="Nombre del proyecto"
            className="linea w-56 py-1 text-[12px] normal-case tracking-normal"
          />
          <button onClick={crear} className="text-[var(--bone)] hover:text-[var(--c1)]">crear</button>
          <button onClick={() => setCreando(false)} className="hover:text-[var(--bone)]">cancelar</button>
        </>
      ) : (
        <>
          <select
            value={valor ?? ""}
            onChange={(e) => elegir(e.target.value)}
            className="cursor-pointer rounded-full border border-[var(--line)] bg-transparent px-3 py-1.5 text-[11px] normal-case tracking-normal text-[var(--bone)] outline-none hover:border-[var(--c1)]"
          >
            {normales.map((p) => <option key={p.proyecto_id} value={p.proyecto_id} className="bg-[#16130f]">{p.proyecto_id} · {p.nombre}</option>)}
          </select>
          <button onClick={() => setCreando(true)} className="hover:text-[var(--bone)]">+ nuevo</button>
        </>
      )}
    </div>
  );
}
