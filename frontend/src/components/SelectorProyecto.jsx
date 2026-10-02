import { useEffect, useState } from "react";
import { crearProyecto, listarProyectos } from "../services/api";

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

  useEffect(() => {
    listarProyectos().then((l) => {
      setProyectos(l);
      if (!valor || !l.some((p) => p.id === valor)) elegir(l[0]?.id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const crear = async () => {
    if (!nombre.trim()) return;
    const { id } = await crearProyecto({ nombre });
    setProyectos(await listarProyectos());
    setNombre("");
    setCreando(false);
    elegir(id);
  };

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
            {proyectos.map((p) => <option key={p.id} value={p.id} className="bg-[#16130f]">{p.nombre}</option>)}
          </select>
          <button onClick={() => setCreando(true)} className="hover:text-[var(--bone)]">+ nuevo</button>
        </>
      )}
    </div>
  );
}
