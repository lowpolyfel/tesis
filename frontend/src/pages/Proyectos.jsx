import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useApi } from "../hooks/useApi";
import { CONTEXTO_MAX, crearProyecto, fasesDeProyecto, listarProyectos, resumenProyecto } from "../services/backend";
import { FASES, fase as datosFase } from "../constants/fases";
import { estadoCorto } from "../components/fases/Camino";
import { PROYECTO_GENERAL_ID } from "../constants/proyectos";
import { useOrb } from "../components/orb/useOrb";
import { Aviso, Cargando, Encabezado, Plegable } from "../components/ui";

/*
 * Todos los proyectos. Un proyecto va de las entrevistas de un dominio a sus requisitos
 * (ADR 0024), con su contexto general, su propio léxico y lo que el sistema aprendió en él
 * (la memoria no se mezcla entre dominios). Cada tarjeta dice en qué fase va. Los que crea
 * una evaluación contra el corpus (versión 1) van aparte, plegados.
 */
export default function Proyectos() {
  const { datos: proyectos, error } = useApi(listarProyectos);
  const [contadores, setContadores] = useState({});
  const [creando, setCreando] = useState(false);

  useEffect(() => {
    if (!proyectos) return undefined;
    let activo = true;
    Promise.all(proyectos.map((p) => (p.tipo === "evaluacion"
      ? resumenProyecto(p.proyecto_id).then((r) => [p.proyecto_id, { v1: r.contadores }])
      : fasesDeProyecto(p.proyecto_id).then((f) => [p.proyecto_id, { fases: f }])).catch(() => [p.proyecto_id, null])))
      .then((pares) => { if (activo) setContadores(Object.fromEntries(pares)); });
    return () => { activo = false; };
  }, [proyectos]);

  const normales = (proyectos ?? []).filter((p) => p.tipo !== "evaluacion")
    .sort((a, b) => (a.proyecto_id === PROYECTO_GENERAL_ID) - (b.proyecto_id === PROYECTO_GENERAL_ID) || b.creado.localeCompare(a.creado));
  const evaluaciones = (proyectos ?? []).filter((p) => p.tipo === "evaluacion");

  return (
    <div className="space-y-8">
      <Encabezado
        titulo="Proyectos"
        acciones={!creando && <button className="pill" onClick={() => setCreando(true)}>+ Nuevo proyecto</button>}
      >
        <p className="max-w-xl text-[15px] text-[var(--bone-dim)]">Cada proyecto va de la entrevista con el cliente a sus requisitos: léxico, mapa conceptual y metas, validados por ti. Elige uno o crea otro.</p>
      </Encabezado>

      {creando && <NuevoProyecto onCancelar={() => setCreando(false)} />}
      <Aviso error={error} />
      {!proyectos && !error && <Cargando>Cargando proyectos…</Cargando>}

      {proyectos && (
        <ol className="grid gap-4 sm:grid-cols-2">
          {normales.map((p) => <Tarjeta key={p.proyecto_id} p={p} c={contadores[p.proyecto_id]} />)}
        </ol>
      )}

      {evaluaciones.length > 0 && (
        <Plegable titulo={`Proyectos de evaluación · ${evaluaciones.length}`} nota="los crea una corrida contra el corpus">
          <ol className="grid gap-4 sm:grid-cols-2">
            {evaluaciones.map((p) => <Tarjeta key={p.proyecto_id} p={p} c={contadores[p.proyecto_id]} />)}
          </ol>
        </Plegable>
      )}
    </div>
  );
}

function Tarjeta({ p, c }) {
  const orb = useOrb();
  const texto = p.contexto || (p.proyecto_id !== PROYECTO_GENERAL_ID ? p.descripcion : null);
  return (
    <li>
      <Link
        to={`/proyectos/${p.proyecto_id}`}
        onPointerEnter={() => orb.poke(0.35)}
        className="tarjeta tarjeta-viva flex h-full min-h-[190px] flex-col p-5"
      >
        <p className="etiqueta">{p.proyecto_id}{p.tipo === "evaluacion" ? " · evaluación" : ""}</p>
        <p className="serif mt-1 text-[28px] leading-tight">{p.nombre}</p>
        <p className={`mt-2 line-clamp-2 text-[14px] leading-relaxed ${texto ? "text-[var(--bone-dim)]" : "text-[var(--bone-faint)] italic"}`}>
          {texto || (p.proyecto_id === PROYECTO_GENERAL_ID ? "Requisitos sin proyecto." : "Sin contexto todavía.")}
        </p>
        {c?.fases ? <Avance f={c.fases} /> : (
          <p className="mono mt-auto flex flex-wrap gap-x-4 gap-y-1 pt-5 text-[10px] text-[var(--bone-faint)]">
            {c?.v1 ? (
              <>
                <span><b className="font-normal text-[var(--bone)]">{c.v1.requisitos}</b> requisitos</span>
                <span><b className="font-normal text-[#57f7a7]">{c.v1.formalizados}</b> listos</span>
              </>
            ) : <span>contando…</span>}
          </p>
        )}
      </Link>
    </li>
  );
}

/* Las cinco fases en esferas pequeñas (llenas las validadas) y lo que sigue */
function Avance({ f }) {
  const siguiente = f.fases.find((x) => x.id === f.siguiente);
  return (
    <div className="mt-auto space-y-2 pt-5">
      <span className="flex items-center gap-1.5" aria-label="Avance por fases">
        {FASES.map((x) => {
          const info = f.fases.find((y) => y.id === x.id);
          return <span key={x.id} title={`${x.nombre}: ${estadoCorto(info)}`} className={`esferita mini ${info?.hecho ? "hecha" : ""}`} style={{ "--tono": x.tono, opacity: info?.disponible ? 1 : 0.4 }} />;
        })}
      </span>
      <p className="mono text-[10px] text-[var(--bone-faint)]">
        {siguiente ? <>Sigue: <span className="text-[var(--bone-dim)]">{datosFase(siguiente.id).nombre}</span> · {estadoCorto(siguiente)}</> : "Requisitos validados"}
      </p>
    </div>
  );
}

/* Nombre y contexto general: el contexto es lo que los agentes leen con la entrevista */
export function NuevoProyecto({ onCancelar }) {
  const navigate = useNavigate();
  const orb = useOrb();
  const [nombre, setNombre] = useState("");
  const [contexto, setContexto] = useState("");
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const crear = async (e) => {
    e.preventDefault();
    if (!nombre.trim()) return;
    setEnviando(true);
    setError(null);
    try {
      const p = await crearProyecto({ nombre, contexto });
      orb.setMood("success", { revertAfter: 1200 });
      navigate(`/proyectos/${p.proyecto_id}`);
    } catch (err) {
      setError(err);
      setEnviando(false);
    }
  };

  return (
    <form onSubmit={crear} className="tarjeta space-y-4 p-5">
      <label className="block space-y-1.5">
        <span className="etiqueta">Nombre</span>
        <input autoFocus value={nombre} maxLength={120} onChange={(e) => setNombre(e.target.value)} className="campo text-[15px]" placeholder="Ej.: Punto de venta de la ferretería" />
      </label>
      <label className="block space-y-1.5">
        <span className="etiqueta">Contexto general <span className="normal-case tracking-normal">(recomendado)</span></span>
        <textarea
          value={contexto} maxLength={CONTEXTO_MAX} rows={4} onChange={(e) => setContexto(e.target.value)}
          onFocus={() => orb.setMood("listening", { ambiente: false })} onBlur={() => orb.setMood("idle", { ambiente: false })}
          className="campo text-[14.5px]"
          placeholder="¿De qué trata el sistema? ¿Quién lo usa? ¿Cómo hablan en ese trabajo? Ej.: Consultorio médico de una doctora con su asistente en Ciudad Juárez; agendan citas y registran consultas."
        />
        <span className="block text-[12px] text-[var(--bone-faint)]">Con el contexto, los agentes entienden la entrevista dentro de tu dominio: qué quiere decir «consulta» o «checar» en ese trabajo.</span>
      </label>
      <Aviso error={error} />
      <div className="flex flex-wrap gap-2">
        <button className="pill" disabled={!nombre.trim() || enviando}>Crear proyecto</button>
        <button type="button" className="pill ghost" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  );
}
