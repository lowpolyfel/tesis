import { useEffect, useState } from "react";
import { CONTEXTO_MAX, editarProyecto } from "../../services/backend";
import { useOrb } from "../../components/orb/useOrb";
import { Aviso } from "../../components/ui";
import FichaContexto from "./FichaContexto";

/*
 * El contexto general: lo leen los agentes con cada entrevista (y, en la versión 1, con
 * cada requisito). Plegado a tres renglones; editable en el sitio, junto con el nombre.
 */
export default function Contexto({ p, editable, pedirEdicion, onGuardado }) {
  const orb = useOrb();
  const [editando, setEditando] = useState(false);
  const [completo, setCompleto] = useState(false);
  const [nombre, setNombre] = useState(p.nombre);
  const [contexto, setContexto] = useState(p.contexto ?? "");
  const [error, setError] = useState(null);

  const abrir = () => { setNombre(p.nombre); setContexto(p.contexto ?? ""); setError(null); setEditando(true); };
  // «Editar» del encabezado abre este mismo formulario
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (pedirEdicion) abrir(); }, [pedirEdicion]);
  const guardar = async (e) => {
    e.preventDefault();
    try {
      onGuardado(await editarProyecto(p.proyecto_id, { nombre, contexto }));
      orb.setMood("success", { revertAfter: 1000 });
      setEditando(false);
    } catch (err) {
      setError(err);
    }
  };

  if (editando) {
    return (
      <form onSubmit={guardar} className="tarjeta space-y-4 p-5">
        <label className="block space-y-1.5">
          <span className="etiqueta">Nombre</span>
          <input value={nombre} maxLength={120} onChange={(e) => setNombre(e.target.value)} className="campo text-[15px]" />
        </label>
        <label className="block space-y-1.5">
          <span className="etiqueta">Contexto general</span>
          <textarea autoFocus value={contexto} maxLength={CONTEXTO_MAX} rows={5} onChange={(e) => setContexto(e.target.value)} className="campo text-[14.5px]"
            placeholder="¿De qué trata el sistema? ¿Quién lo usa? ¿Qué palabras usan en ese trabajo?" />
          <span className="block text-[12px] text-[var(--bone-faint)]">Se aplica a lo que los agentes procesen desde ahora; lo anterior conserva el contexto con el que se procesó.</span>
        </label>
        <Aviso error={error} />
        <div className="flex gap-2">
          <button className="pill sm" disabled={!nombre.trim()}>Guardar</button>
          <button type="button" className="pill ghost sm" onClick={() => setEditando(false)}>Cancelar</button>
        </div>
      </form>
    );
  }

  if (!p.contexto) {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-dashed border-[var(--line)] px-5 py-4">
        <p className="min-w-0 flex-1 text-[14px] text-[var(--bone-dim)]">
          {editable ? "Sin contexto general. Agrégalo para que los agentes entiendan la entrevista dentro de su dominio." : "Sin contexto general."}
        </p>
        {editable && <button className="pill ghost sm" onClick={abrir}>Agregar contexto</button>}
      </div>
    );
  }
  return (
    <div className="group space-y-1.5">
      <p className="etiqueta">Contexto</p>
      <p className={`max-w-2xl whitespace-pre-line text-[15px] leading-relaxed text-[var(--bone-dim)] ${completo ? "" : "line-clamp-2"}`}>{p.contexto}</p>
      <p className="mono flex gap-4 text-[10px] text-[var(--bone-faint)]">
        {p.contexto.length > 150 && <button className="hover:text-[var(--bone)]" onClick={() => setCompleto((x) => !x)}>{completo ? "ver menos" : "ver todo"}</button>}
        {editable && <button className="hover:text-[var(--bone)]" onClick={abrir}>editar</button>}
      </p>
      {editable && <FichaContexto proyecto={p} />}
    </div>
  );
}
