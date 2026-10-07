import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useApi } from "../hooks/useApi";
import { CONTEXTO_MAX, crearProyecto, listarProyectos, resumenProyecto } from "../services/backend";
import { PROYECTO_GENERAL_ID } from "../constants/proyectos";
import { useOrb } from "../components/orb/useOrb";
import { Aviso, Cargando, Encabezado, Plegable } from "../components/ui";

/*
 * Todos los proyectos. Un proyecto agrupa los requisitos de un dominio con su
 * contexto general y su propio léxico (la memoria no se mezcla entre dominios).
 * Los que crea una evaluación contra el corpus van aparte, plegados.
 */
export default function Proyectos() {
  const { datos: proyectos, error } = useApi(listarProyectos);
  const [contadores, setContadores] = useState({});
  const [creando, setCreando] = useState(false);

  useEffect(() => {
    if (!proyectos) return undefined;
    let activo = true;
    Promise.all(proyectos.map((p) => resumenProyecto(p.proyecto_id).then((r) => [p.proyecto_id, r.contadores]).catch(() => [p.proyecto_id, null])))
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
        <p className="max-w-xl text-[15px] text-[var(--bone-dim)]">Cada proyecto tiene su contexto y su léxico. Elige uno o crea otro.</p>
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
        <p className="mono mt-auto flex flex-wrap gap-x-4 gap-y-1 pt-5 text-[10px] text-[var(--bone-faint)]">
          {c ? (
            <>
              <span><b className="font-normal text-[var(--bone)]">{c.requisitos}</b> requisitos</span>
              <span><b className="font-normal text-[#57f7a7]">{c.formalizados}</b> listos</span>
              {c.por_validar > 0 && <span><b className="font-normal text-[#f9a8d4]">{c.por_validar}</b> por revisar</span>}
              {c.en_proceso > 0 && <span><b className="font-normal text-amber-300">{c.en_proceso}</b> analizando</span>}
            </>
          ) : <span>contando…</span>}
        </p>
      </Link>
    </li>
  );
}

/* Nombre y contexto general: el contexto es lo que los agentes leen con cada requisito */
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
          onFocus={() => orb.setMood("listening")} onBlur={() => orb.setMood("idle")}
          className="campo text-[14.5px]"
          placeholder="¿De qué trata el sistema? ¿Quién lo usa? ¿Cómo hablan en ese trabajo? Ej.: Sistema de caja para una ferretería de Ciudad Juárez; lo usan cajeros y el encargado; «checar» es revisar existencias."
        />
        <span className="block text-[12px] text-[var(--bone-faint)]">Con el contexto, los agentes entienden «ahorita» o «checar» como en tu dominio y escriben requisitos más completos.</span>
      </label>
      <Aviso error={error} />
      <div className="flex flex-wrap gap-2">
        <button className="pill" disabled={!nombre.trim() || enviando}>Crear proyecto</button>
        <button type="button" className="pill ghost" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  );
}
