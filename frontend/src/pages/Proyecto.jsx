import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { useApi } from "../hooks/useApi";
import { documentosDeProyecto, editarProyecto, obtenerLel, resumenProyecto } from "../services/backend";
import { ESTADOS as E, INFO_VIA, infoEstado } from "../constants/estados";
import { tipo } from "../constants/agentes";
import { useOrb } from "../components/orb/useOrb";

/*
 * Un proyecto: sus requisitos agrupados por ciclo KMoS-SSA, los documentos de
 * los que salieron y su LEL (la memoria no se mezcla entre proyectos). Mientras
 * haya requisitos en proceso, la vista se refresca sola.
 */
const VISTAS = [
  ["requisitos", "Requisitos"],
  ["documentos", "Documentos"],
  ["lel", "LEL"],
];

const SONDEO_MS = 2500;

export default function Proyecto() {
  const { id } = useParams();
  const orb = useOrb();
  const [params, setParams] = useSearchParams();
  const vista = VISTAS.some(([k]) => k === params.get("vista")) ? params.get("vista") : "requisitos";
  const { datos: r, setDatos, error, recargar } = useApi(() => resumenProyecto(id), [id]);
  const enProceso = r?.contadores.en_proceso ?? 0;

  useEffect(() => {
    if (r) orb.update("core", { sub: r.proyecto.nombre });
  }, [orb, r]);

  // Sondeo mientras los agentes trabajan: los estados cambian sin que nadie recargue
  useEffect(() => {
    if (!enProceso) return undefined;
    const t = setInterval(recargar, SONDEO_MS);
    return () => clearInterval(t);
  }, [enProceso, recargar]);

  const ciclos = useMemo(() => {
    if (!r) return [];
    const m = new Map();
    for (const q of r.requisitos) m.set(q.ciclo, [...(m.get(q.ciclo) ?? []), q]);
    return [...m.entries()].sort((a, b) => b[0] - a[0]);
  }, [r]);

  if (error) return <p className="text-sm text-[var(--danger)]">{error.message}</p>;
  if (!r) return <p className="text-sm text-[var(--bone-dim)]">Cargando proyecto…</p>;

  const p = r.proyecto;
  const c = r.contadores;
  const porValidar = r.requisitos.filter((q) => q.estado === E.PENDIENTE_VALIDACION);
  const cambiarVista = (k) => { setParams(k === "requisitos" ? {} : { vista: k }, { replace: true }); orb.poke(0.4); };

  return (
    <div className="space-y-7">
      <header className="space-y-3">
        <nav className="mono text-[9.5px] text-[var(--bone-faint)]">
          <Link to="/proyectos" className="hover:text-[var(--bone)]">Proyectos</Link> / {p.proyecto_id}
          {p.tipo === "evaluacion" && " · evaluación"}
        </nav>
        <Encabezado p={p} onGuardado={(nuevo) => setDatos((x) => ({ ...x, proyecto: nuevo }))} />
        <p className="mono text-[9.5px] text-[var(--bone-faint)]">
          {c.requisitos} requisitos · {c.ciclos} ciclos · {c.ambiguos} ambiguos · {c.por_validar} por validar · {c.formalizados} formalizados · {c.lel} en el LEL
          {c.rechazados > 0 && ` · ${c.rechazados} rechazados`}
          {c.errores > 0 && <span className="text-[var(--danger)]"> · {c.errores} con error</span>}
          {enProceso > 0 && <span className="text-[var(--bone)]"> · <span className="gira" /> {enProceso} en proceso</span>}
        </p>
        <div className="flex flex-wrap gap-2 pt-1">
          <Link className="pill" to={`/inicio?proyecto=${p.proyecto_id}`}>Cargar requisitos aquí</Link>
          {porValidar.length > 0 && (
            <Link className="pill ghost" to={`/requisitos/${porValidar[0].req_id}/validacion`}>Validar ({porValidar.length})</Link>
          )}
          <Link className="pill ghost" to={`/ambiguedades?proyecto=${p.proyecto_id}`}>Ambigüedades</Link>
          <Link className="pill ghost" to={`/comparaciones?proyecto=${p.proyecto_id}`}>Comparar requisitos</Link>
          <Link className="pill ghost" to={`/big-picture?proyecto=${p.proyecto_id}`}>Metas y Big Picture</Link>
          <Link className="pill ghost" to={`/flujo?proyecto=${p.proyecto_id}`}>Flujo</Link>
          <Link className="pill ghost" to={`/calibracion?proyecto=${p.proyecto_id}`}>Calibración</Link>
        </div>
      </header>

      {r.por_ciclo.length > 0 && <BarraEstados porEstado={r.por_estado} total={c.requisitos} />}

      <div className="mono flex flex-wrap gap-5 border-b border-[var(--line)] pb-3 text-[10px]">
        {VISTAS.map(([k, t]) => (
          <button
            key={k}
            onClick={() => cambiarVista(k)}
            className={vista === k ? "text-[var(--bone)] underline decoration-[var(--c1)] underline-offset-[8px]" : "text-[var(--bone-faint)] hover:text-[var(--bone)]"}
          >
            {t}
          </button>
        ))}
      </div>

      {vista === "requisitos" && <Requisitos ciclos={ciclos} porCiclo={r.por_ciclo} proyectoId={p.proyecto_id} />}
      {vista === "documentos" && <Documentos proyectoId={p.proyecto_id} />}
      {vista === "lel" && <LelProyecto proyectoId={p.proyecto_id} />}
    </div>
  );
}

/* Nombre y descripción, editables en el sitio (PATCH /proyectos/{id}) */
function Encabezado({ p, onGuardado }) {
  const [editando, setEditando] = useState(false);
  const [nombre, setNombre] = useState(p.nombre);
  const [descripcion, setDescripcion] = useState(p.descripcion ?? "");
  const [aviso, setAviso] = useState(null);

  const abrir = () => { setNombre(p.nombre); setDescripcion(p.descripcion ?? ""); setAviso(null); setEditando(true); };
  const guardar = async (e) => {
    e.preventDefault();
    try {
      onGuardado(await editarProyecto(p.proyecto_id, { nombre, descripcion }));
      setEditando(false);
    } catch (err) {
      setAviso(err.message);
    }
  };

  if (!editando) {
    return (
      <div className="group">
        <h1>{p.nombre}.</h1>
        {p.descripcion && <p className="mt-2 text-sm text-[var(--bone-dim)]">{p.descripcion}</p>}
        <button className="mono mt-1 text-[9.5px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={abrir}>editar</button>
      </div>
    );
  }
  return (
    <form onSubmit={guardar} className="grid gap-3 sm:grid-cols-[1fr_1.4fr_auto_auto] sm:items-end">
      <label className="block">
        <span className="mono mb-1 block text-[9.5px] text-[var(--bone-faint)]">Nombre</span>
        <input autoFocus value={nombre} onChange={(e) => setNombre(e.target.value)} className="linea w-full py-1.5 text-[15px]" />
      </label>
      <label className="block">
        <span className="mono mb-1 block text-[9.5px] text-[var(--bone-faint)]">Dominio o descripción</span>
        <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} className="linea w-full py-1.5 text-[15px]" />
      </label>
      <button className="pill" disabled={!nombre.trim()}>Guardar</button>
      <button type="button" className="pill ghost" onClick={() => setEditando(false)}>Cancelar</button>
      {aviso && <p className="text-sm text-[var(--danger)] sm:col-span-4">{aviso}</p>}
    </form>
  );
}

/* Proporción de requisitos en cada estado, de un vistazo */
function BarraEstados({ porEstado, total }) {
  const partes = Object.entries(porEstado).filter(([, n]) => n > 0);
  return (
    <div className="space-y-2">
      <div className="flex h-2 overflow-hidden rounded-full bg-white/[0.04]">
        {partes.map(([e, n]) => (
          <span key={e} title={`${infoEstado(e).etiqueta}: ${n}`} className={infoEstado(e).punto} style={{ width: `${(100 * n) / total}%` }} />
        ))}
      </div>
      <p className="mono flex flex-wrap gap-x-4 gap-y-1 text-[9.5px] text-[var(--bone-faint)]">
        {partes.map(([e, n]) => (
          <span key={e} className="flex items-center gap-1.5"><span className={`punto ${infoEstado(e).punto}`} />{infoEstado(e).etiqueta} {n}</span>
        ))}
      </p>
    </div>
  );
}

function Requisitos({ ciclos, porCiclo, proyectoId }) {
  if (ciclos.length === 0) {
    return (
      <p className="text-sm text-[var(--bone-dim)]">
        Este proyecto aún no tiene requisitos. <Link className="underline" to={`/inicio?proyecto=${proyectoId}`}>Sube un PDF o pega el texto</Link>.
      </p>
    );
  }
  return (
    <div className="space-y-8">
      {ciclos.map(([ciclo, reqs]) => {
        const resumen = porCiclo.find((x) => x.ciclo === ciclo);
        return (
          <section key={ciclo}>
            <div className="mb-2 flex flex-wrap items-baseline gap-3">
              <p className="mono text-[9.5px] text-[var(--bone-faint)]">Ciclo C{ciclo} · {reqs.length} {reqs.length === 1 ? "requisito" : "requisitos"}</p>
              {resumen && (
                <p className="mono text-[9px] text-[var(--bone-faint)]">
                  {Object.entries(resumen.por_estado).filter(([, n]) => n).map(([e, n]) => `${infoEstado(e).etiqueta.toLowerCase()} ${n}`).join(" · ")}
                </p>
              )}
              <Link className="mono ml-auto text-[9.5px] text-[var(--bone-faint)] hover:text-[var(--bone)]" to={`/analisis?proyecto=${proyectoId}&ids=${reqs.map((q) => q.req_id).join(",")}`}>
                ver el ciclo en la escena →
              </Link>
            </div>
            <ol className="border-t border-[var(--line)]">
              {reqs.map((q) => <FilaRequisito key={q.req_id} q={q} />)}
            </ol>
          </section>
        );
      })}
    </div>
  );
}

function FilaRequisito({ q }) {
  const via = q.via ? INFO_VIA[q.via] : null;
  const destino = q.estado === E.PENDIENTE_VALIDACION ? `/requisitos/${q.req_id}/validacion` : `/requisitos/${q.req_id}`;
  const tipos = Object.entries(q.tipos ?? {}).filter(([, n]) => n > 0);
  return (
    <li>
      <Link to={destino} className="group flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-[var(--line)] py-3 hover:bg-white/[0.02] sm:flex-nowrap">
        <span className="mono w-14 shrink-0 text-[9.5px] text-[var(--bone-faint)]">{q.req_id}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-[15px] leading-relaxed">{q.texto}</span>
          <span className="mt-1 flex flex-wrap items-center gap-1.5">
            {tipos.map(([t, n]) => (
              <span key={t} className={`rounded px-1.5 text-[11px] ${tipo(t).clase}`}>{tipo(t).etiqueta}{n > 1 ? ` ×${n}` : ""}</span>
            ))}
            {q.vaguedad?.length > 0 && <span className={`rounded px-1.5 text-[11px] ${tipo("vaguedad").clase}`}>vago: {q.vaguedad.join(", ")}</span>}
            {q.origen?.archivo && (
              <span className="mono text-[9px] text-[var(--bone-faint)]">
                {q.origen.archivo}{q.origen.pagina ? ` · p. ${q.origen.pagina}` : ""}{q.origen.marca ? ` · ${q.origen.marca}` : ""}
              </span>
            )}
            {q.origen?.reproceso_de && <span className="mono text-[9px] text-[var(--bone-faint)]">reproceso de {q.origen.reproceso_de}</span>}
          </span>
        </span>
        <span className="mono flex w-full flex-wrap items-center gap-2 text-[9.5px] text-[var(--bone-dim)] sm:w-auto sm:shrink-0">
          {q.en_proceso && <span className="gira" />}
          {q.similitud_minima != null && <span title="Similitud mínima entre interpretaciones">sim {q.similitud_minima.toFixed(2)}</span>}
          {q.rondas_max > 0 && <span>{q.rondas_max}R</span>}
          {via && <span className="punto" style={{ background: via.tono }} />}
          {via ? `${via.etiqueta} · ` : ""}{infoEstado(q.estado).etiqueta}
        </span>
      </Link>
    </li>
  );
}

function Documentos({ proyectoId }) {
  const { datos: docs, error } = useApi(() => documentosDeProyecto(proyectoId), [proyectoId]);
  if (error) return <p className="text-sm text-[var(--danger)]">{error.message}</p>;
  if (!docs) return <p className="text-sm text-[var(--bone-dim)]">Cargando documentos…</p>;
  if (docs.length === 0) {
    return (
      <p className="text-sm text-[var(--bone-dim)]">
        Ningún documento cargado. <Link className="underline" to={`/inicio?proyecto=${proyectoId}`}>Sube un PDF o un .txt</Link>; el sistema separa los requisitos y conserva la página de cada uno.
      </p>
    );
  }
  return (
    <ol className="border-t border-[var(--line)]">
      {docs.map((d) => (
        <li key={d.documento_id} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-[var(--line)] py-3">
          <span className="mono w-14 shrink-0 text-[9.5px] text-[var(--bone-faint)]">{d.documento_id}</span>
          <span className="min-w-0 flex-1 text-[15px]">{d.archivo}</span>
          <span className="mono text-[9.5px] text-[var(--bone-dim)]">
            {d.tipo.toUpperCase()} · {d.paginas} {d.paginas === 1 ? "página" : "páginas"} · {d.total_requisitos} requisitos · {d.total_descartados} descartados · {new Date(d.creado).toLocaleDateString("es-MX")}
          </span>
        </li>
      ))}
    </ol>
  );
}

/* LEL del proyecto: solo términos resueltos y validados por una persona (ADR 0008) */
export function LelProyecto({ proyectoId }) {
  const { datos: lel, error } = useApi(() => obtenerLel(proyectoId), [proyectoId]);
  if (error) return <p className="text-sm text-[var(--danger)]">{error.message}</p>;
  if (!lel) return <p className="text-sm text-[var(--bone-dim)]">Cargando el LEL…</p>;
  if (lel.length === 0) {
    return <p className="text-sm text-[var(--bone-dim)]">El LEL de este proyecto está vacío. Se llena cuando una persona valida un término léxico resuelto.</p>;
  }
  const orden = [...lel].sort((a, b) => a.simbolo.localeCompare(b.simbolo, "es"));
  return (
    <div className="space-y-4">
      <p className="mono text-[9.5px] text-[var(--bone-faint)]">{lel.length} símbolos</p>
      <ol className="grid gap-3 md:grid-cols-2">{orden.map((e) => <EntradaLel key={`${e.req_id}-${e.simbolo}`} e={e} />)}</ol>
    </div>
  );
}

export function EntradaLel({ e, conProyecto = null }) {
  const via = INFO_VIA[e.via];
  return (
    <li className="rounded-2xl border border-[var(--line)] bg-white/[0.02] p-4 text-sm">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="serif text-[24px] leading-tight">{e.simbolo}</span>
        <span className="mono text-[9.5px] text-[var(--c1)]">{e.tipo}</span>
        <Link to={`/requisitos/${e.req_id}`} className="mono ml-auto text-[9px] text-[var(--bone-faint)] hover:text-[var(--bone)]">resuelto en {e.req_id} →</Link>
      </div>
      <p className="mono mt-1 flex flex-wrap items-center gap-2 text-[9px] text-[var(--bone-faint)]">
        {e.termino !== e.simbolo && <span>término «{e.termino}»</span>}
        {via && <span className="flex items-center gap-1"><span className="punto" style={{ background: via.tono }} />{via.etiqueta}</span>}
        {e.editada_por_humano && <span>editada por una persona</span>}
        <span>{e.fecha?.slice(0, 10)}</span>
        {conProyecto}
      </p>
      <p className="mono mt-3 text-[9px] text-[var(--bone-faint)]">Noción</p>
      <ul className="mt-1 space-y-1 text-[var(--bone-dim)]">{e.nocion.map((x, j) => <li key={j}>{x}</li>)}</ul>
      <p className="mono mt-3 text-[9px] text-[var(--bone-faint)]">Impacto</p>
      <ul className="mt-1 space-y-1 text-[var(--bone-dim)]">{e.impacto.map((x, j) => <li key={j}>{x}</li>)}</ul>
    </li>
  );
}
