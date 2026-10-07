import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { useApi } from "../../hooks/useApi";
import { CONTEXTO_MAX, editarProyecto, resumenProyecto } from "../../services/backend";
import { ESTADOS as E } from "../../constants/estados";
import { seccion } from "../../components/orb/secciones";
import { recordarProyecto } from "../../components/proyectoRecordado";
import { useOrb } from "../../components/orb/useOrb";
import { Aviso, Cargando, Encabezado, Pestanas, Volver } from "../../components/ui";
import Requisitos from "./Requisitos";
import Especificacion from "./Especificacion";
import Lexico from "./Lexico";
import Mapa from "./Mapa";

/*
 * Un proyecto: su contexto general y cuatro vistas.
 *   Requisitos      lo que se cargó y en qué va cada uno; se eligen varios para el mapa
 *   Especificación  la salida: requisitos funcionales y no funcionales, completos
 *   Léxico          el LEL del proyecto (la memoria): qué significa cada término
 *   Mapa            el Big Picture y el modelo de metas, de todos o de los elegidos
 * Mientras haya requisitos en proceso, el resumen se refresca solo.
 */
const VISTAS = ["requisitos", "especificacion", "lexico", "mapa"];
const SONDEO_MS = 2500;

export default function Proyecto() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const vista = VISTAS.includes(params.get("vista")) ? params.get("vista") : "requisitos";
  const seleccion = (params.get("req") ?? "").split(",").filter(Boolean);
  const { datos: r, setDatos, error, recargar } = useApi(() => resumenProyecto(id), [id]);
  const enProceso = r?.contadores.en_proceso ?? 0;

  useEffect(() => recordarProyecto(id), [id]);
  useEffect(() => {
    if (!enProceso) return undefined;
    const t = setInterval(recargar, SONDEO_MS);
    return () => clearInterval(t);
  }, [enProceso, recargar]);

  const ir = (v, req = []) => {
    const p = new URLSearchParams();
    if (v !== "requisitos") p.set("vista", v);
    if (req.length) p.set("req", req.join(","));
    setParams(p);
  };

  if (error) return <div className="space-y-4"><Volver a="/proyectos">Proyectos</Volver><Aviso error={error} /></div>;
  if (!r) return <Cargando>Cargando el proyecto…</Cargando>;

  const p = r.proyecto;
  const c = r.contadores;
  const evaluacion = p.tipo === "evaluacion";
  const porRevisar = r.requisitos.filter((q) => q.estado === E.PENDIENTE_VALIDACION);

  return (
    <div className="space-y-8">
      <Encabezado
        volver={<Volver a="/proyectos">Proyectos</Volver>}
        antetitulo={`${p.proyecto_id}${evaluacion ? " · evaluación" : ""}`}
        titulo={p.nombre}
        acciones={!evaluacion && <Link className="pill" to={`/proyectos/${id}/analizar`}>+ Analizar requisitos</Link>}
      >
        <Contexto p={p} editable={!evaluacion} onGuardado={(nuevo) => setDatos((x) => ({ ...x, proyecto: nuevo }))} />
        <p className="mono flex flex-wrap gap-x-5 gap-y-1 text-[10.5px] text-[var(--bone-faint)]">
          <span><b className="font-normal text-[var(--bone)]">{c.requisitos}</b> requisitos</span>
          <span><b className="font-normal text-[#57f7a7]">{c.formalizados}</b> listos</span>
          {c.por_validar > 0 && (
            <Link className="hover:text-[var(--bone)]" to={`/requisitos/${porRevisar[0]?.req_id}/validacion`}>
              <b className="font-normal text-[#f9a8d4]">{c.por_validar}</b> por revisar
            </Link>
          )}
          {enProceso > 0 && <span className="flex items-center gap-1.5"><span className="gira" /> {enProceso} analizando</span>}
          {c.errores > 0 && <span className="text-[var(--danger)]">{c.errores} con error</span>}
        </p>
      </Encabezado>

      {porRevisar.length > 0 && vista === "requisitos" && (
        <div className="tarjeta flex flex-wrap items-center gap-4 !border-[#f9a8d4]/30 px-5 py-4">
          <span className="punto" style={{ background: "#f9a8d4", boxShadow: "0 0 12px #f9a8d4" }} />
          <p className="min-w-0 flex-1 text-[14.5px]">
            {porRevisar.length === 1 ? "Un requisito necesita" : `${porRevisar.length} requisitos necesitan`} tu revisión: los agentes no se pusieron de acuerdo.
          </p>
          <Link className="pill sm" to={`/requisitos/${porRevisar[0].req_id}/validacion`}>Revisar</Link>
        </div>
      )}

      <Pestanas
        etiqueta="Vistas del proyecto"
        valor={vista}
        onCambio={(v) => ir(v, v === "requisitos" ? [] : seleccion)}
        opciones={[
          { id: "requisitos", texto: "Requisitos", cuenta: c.requisitos, mood: seccion("requisitos").mood },
          { id: "especificacion", texto: "Especificación", cuenta: c.formalizados, mood: seccion("especificacion").mood },
          { id: "lexico", texto: "Léxico", cuenta: c.lel, mood: seccion("lexico").mood },
          { id: "mapa", texto: "Mapa", mood: seccion("mapa").mood },
        ]}
      />

      {vista === "requisitos" && <Requisitos r={r} onElegir={(v, ids) => ir(v, ids)} />}
      {vista === "especificacion" && <Especificacion proyecto={p} seleccion={seleccion} onTodos={() => ir("especificacion")} />}
      {vista === "lexico" && <Lexico proyectoId={id} />}
      {vista === "mapa" && <Mapa proyectoId={id} requisitos={r.requisitos} seleccion={seleccion} onSeleccion={(ids) => ir("mapa", ids)} />}
    </div>
  );
}

/*
 * El contexto general: lo leen los agentes con cada requisito. Plegado a tres
 * renglones; editable en el sitio, junto con el nombre.
 */
function Contexto({ p, editable, onGuardado }) {
  const orb = useOrb();
  const [editando, setEditando] = useState(false);
  const [completo, setCompleto] = useState(false);
  const [nombre, setNombre] = useState(p.nombre);
  const [contexto, setContexto] = useState(p.contexto ?? "");
  const [error, setError] = useState(null);

  const abrir = () => { setNombre(p.nombre); setContexto(p.contexto ?? ""); setError(null); setEditando(true); };
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
          <span className="block text-[12px] text-[var(--bone-faint)]">Se aplica a los requisitos que analices desde ahora; los anteriores conservan el contexto con el que se analizaron.</span>
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
          {editable ? "Sin contexto general. Agrégalo para que los agentes entiendan tus requisitos dentro de su dominio." : "Sin contexto general."}
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
    </div>
  );
}
