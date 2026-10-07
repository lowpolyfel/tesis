import { useEffect, useState } from "react";
import { crearProyecto, listarProyectos } from "../services/backend";

/* Elegir el proyecto donde caerán los requisitos (o crear uno) */
const CLAVE = "dudamel.proyecto";
export const proyectoRecordado = () => {
  try { return localStorage.getItem(CLAVE); } catch { return null; }
};
export const recordarProyecto = (id) => {
  try { localStorage.setItem(CLAVE, id); } catch { /* sin almacenamiento */ }
};

export default function SelectorProyecto({ valor, onCambio }) {
  const [proyectos, setProyectos] = useState(null);
  const [creando, setCreando] = useState(false);
  const [nombre, setNombre] = useState("");
  const [error, setError] = useState(null); // no se pudo listar: no hay qué elegir
  const [errorCrear, setErrorCrear] = useState(null);
  const [aviso, setAviso] = useState(null);

  const elegir = (id) => {
    recordarProyecto(id);
    onCambio(id);
  };

  const normales = (proyectos ?? []).filter((p) => p.tipo !== "evaluacion");

  useEffect(() => {
    listarProyectos()
      .then((l) => {
        setProyectos(l);
        const opciones = l.filter((p) => p.tipo !== "evaluacion");
        if (!valor || !opciones.some((p) => p.proyecto_id === valor)) {
          // el más reciente que no sea el General; si no hay, el General
          const otro = (opciones.filter((p) => p.proyecto_id !== "P00").at(-1) ?? opciones[0])?.proyecto_id;
          // si se pidió uno que no admite cargas, se dice en lugar de cambiarlo en silencio
          const pedido = valor && l.find((p) => p.proyecto_id === valor);
          if (pedido) setAviso(`${pedido.proyecto_id} es un proyecto de evaluación: sus requisitos los carga la evaluación del corpus. Elige dónde cargar estos.`);
          else if (valor) setAviso(`No existe el proyecto ${valor}.`);
          elegir(otro);
        }
      })
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const crear = async () => {
    if (!nombre.trim()) return;
    setErrorCrear(null);
    try {
      const p = await crearProyecto({ nombre });
      setProyectos(await listarProyectos());
      setNombre("");
      setCreando(false);
      setAviso(null);
      elegir(p.proyecto_id);
    } catch (e) {
      setErrorCrear(e.message); // el formulario sigue abierto para corregir o cancelar
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
            onKeyDown={(e) => { if (e.key === "Enter") crear(); if (e.key === "Escape") { setCreando(false); setErrorCrear(null); } }}
            placeholder="Nombre del proyecto"
            className="linea w-56 py-1 text-[12px] normal-case tracking-normal"
          />
          <button onClick={crear} className="text-[var(--bone)] hover:text-[var(--c1)]">crear</button>
          <button onClick={() => { setCreando(false); setErrorCrear(null); }} className="hover:text-[var(--bone)]">cancelar</button>
        </>
      ) : (
        <>
          <select
            value={valor ?? ""}
            onChange={(e) => { setAviso(null); elegir(e.target.value); }}
            className="cursor-pointer rounded-full border border-[var(--line)] bg-transparent px-3 py-1.5 text-[11px] normal-case tracking-normal text-[var(--bone)] outline-none hover:border-[var(--c1)]"
          >
            {normales.map((p) => <option key={p.proyecto_id} value={p.proyecto_id} className="bg-[#16130f]">{p.proyecto_id} · {p.nombre}</option>)}
          </select>
          <button onClick={() => setCreando(true)} className="hover:text-[var(--bone)]">+ nuevo</button>
        </>
      )}
      {creando && errorCrear && <p className="basis-full normal-case tracking-normal text-[11px] text-[var(--danger)]">{errorCrear}</p>}
      {aviso && <p className="basis-full normal-case tracking-normal text-[11px] text-amber-200/80">{aviso}</p>}
    </div>
  );
}
