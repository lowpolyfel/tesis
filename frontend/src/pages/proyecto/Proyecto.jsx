import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { useApi } from "../../hooks/useApi";
import { borrarProyecto, resumenProyecto } from "../../services/backend";
import { ESTADOS as E } from "../../constants/estados";
import { seccion } from "../../components/orb/secciones";
import { olvidarProyecto, recordarProyecto } from "../../components/proyectoRecordado";
import { useOrb } from "../../components/orb/useOrb";
import { Aviso, Cargando, Confirmar, Encabezado, Pestanas, Volver } from "../../components/ui";
import Requisitos from "./Requisitos";
import Especificacion from "./Especificacion";
import Lexico from "./Lexico";
import Mapa from "./Mapa";
import Contexto from "./Contexto";

/*
 * Versión 1 (ADR 0018): el proyecto por requisitos, en /proyectos/:id/v1. La versión 2
 * (ADR 0024) parte de una entrevista (pages/fases/Proyecto.jsx); esta vista queda para los
 * requisitos analizados antes y para la evaluación contra el corpus.
 *
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
  const navigate = useNavigate();
  const orb = useOrb();
  const [editarPedido, setEditarPedido] = useState(0);
  const [borrando, setBorrando] = useState(false);

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
        volver={<Volver a={evaluacion ? "/proyectos" : `/proyectos/${id}`}>{evaluacion ? "Proyectos" : p.nombre}</Volver>}
        antetitulo={`${p.proyecto_id}${evaluacion ? " · evaluación" : " · requisitos (versión 1)"}`}
        titulo={p.nombre}
        acciones={(
          <>
            {!evaluacion && <Link className="pill" to={`/proyectos/${id}/analizar`}>+ Analizar requisitos</Link>}
            {!evaluacion && <button className="pill ghost" onClick={() => setEditarPedido((n) => n + 1)}>Editar</button>}
            <button className="pill ghost" onClick={() => setBorrando(true)}>Borrar</button>
          </>
        )}
      >
        {borrando && (
          <Confirmar
            pregunta={`¿Borrar el proyecto «${p.nombre}»?`}
            detalle={`Se borran también sus ${c.requisitos} requisitos, su léxico, sus documentos y sus análisis. No se puede deshacer.`}
            accion="Borrar proyecto"
            onCancelar={() => setBorrando(false)}
            onConfirmar={async () => {
              await borrarProyecto(id);
              olvidarProyecto();
              orb.setMood("idle");
              navigate("/proyectos", { replace: true });
            }}
          />
        )}
        <Contexto p={p} editable={!evaluacion} pedirEdicion={editarPedido} onGuardado={(nuevo) => setDatos((x) => ({ ...x, proyecto: nuevo }))} />
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

      {vista === "requisitos" && <Requisitos r={r} onElegir={(v, ids) => ir(v, ids)} onCambio={recargar} />}
      {vista === "especificacion" && <Especificacion proyecto={p} seleccion={seleccion} onTodos={() => ir("especificacion")} />}
      {vista === "lexico" && <Lexico proyectoId={id} />}
      {vista === "mapa" && <Mapa proyectoId={id} requisitos={r.requisitos} seleccion={seleccion} onSeleccion={(ids) => ir("mapa", ids)} />}
    </div>
  );
}
