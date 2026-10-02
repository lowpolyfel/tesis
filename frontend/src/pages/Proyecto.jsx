import { useEffect, useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { useApi } from "../hooks/useApi";
import { obtenerLel, obtenerProyecto } from "../services/api";
import { ESTADOS as E, INFO_ESTADO, estaEnProceso } from "../constants/estados";
import { useOrb } from "../components/orb/useOrb";
import TextoMarcado from "../components/TextoMarcado";
import Panorama from "../components/artefactos/Panorama";
import ModeloConceptual from "../components/artefactos/ModeloConceptual";
import { artefactosDe } from "../components/artefactos/modelo";
import { VIA } from "./Analisis";

/*
 * Un proyecto: sus requisitos por ciclo, su LEL, su Big Picture y su modelo
 * conceptual, todo separado del resto de los proyectos.
 */
const VISTAS = [
  ["requisitos", "Requisitos"],
  ["lel", "LEL"],
  ["bigpicture", "Big Picture"],
  ["modelo", "Modelo conceptual"],
];

export default function Proyecto() {
  const { id } = useParams();
  const orb = useOrb();
  const [params, setParams] = useSearchParams();
  const vista = VISTAS.some(([k]) => k === params.get("vista")) ? params.get("vista") : "requisitos";
  const { datos: p, error } = useApi(() => obtenerProyecto(id), [id]);
  const { datos: lelTodo } = useApi(obtenerLel);

  useEffect(() => {
    if (p) orb.update("core", { sub: p.nombre });
  }, [orb, p]);

  const ciclos = useMemo(() => {
    if (!p) return [];
    const m = new Map();
    for (const r of p.lista) m.set(r.ciclo, [...(m.get(r.ciclo) ?? []), r]);
    return [...m.entries()].sort((a, b) => b[0] - a[0]);
  }, [p]);

  if (error) return <p className="text-sm text-[var(--danger)]">{error.message}</p>;
  if (!p) return <p className="text-sm text-[var(--bone-dim)]">Cargando proyecto…</p>;

  const conArtefactos = p.lista.filter((r) => r.artefactos);
  const porAprobar = p.lista.filter((r) => r.estado === E.PENDIENTE_VALIDACION || r.estado === E.VALIDADO);

  return (
    <div className="space-y-7">
      <header className="space-y-3">
        <nav className="mono text-[9.5px] text-[var(--bone-faint)]"><Link to="/proyectos" className="hover:text-[var(--bone)]">Proyectos</Link> / {p.id}</nav>
        <h1>{p.nombre}.</h1>
        {p.descripcion && <p className="text-sm text-[var(--bone-dim)]">{p.descripcion}</p>}
        <p className="mono text-[9.5px] text-[var(--bone-faint)]">
          {p.requisitos} requisitos · {p.ciclos} ciclos · {p.formalizados} en el léxico · {p.porValidar} por validar · {p.ambiguedades} ambigüedades
        </p>
        <div className="flex flex-wrap gap-2 pt-1">
          <Link className="pill" to={`/inicio?proyecto=${p.id}`}>Analizar requisitos aquí</Link>
          <button className="pill ghost" onClick={() => { setParams({ vista: "bigpicture" }, { replace: true }); orb.poke(0.4); }}>Big Picture</button>
          <button className="pill ghost" onClick={() => { setParams({ vista: "modelo" }, { replace: true }); orb.poke(0.4); }}>Modelo UML</button>
          <Link className="pill ghost" to={`/flujo?proyecto=${p.id}`}>Flujo</Link>
          <Link className="pill ghost" to={`/ambiguedades?proyecto=${p.id}`}>Ambigüedades</Link>
        </div>
      </header>

      <div className="mono flex flex-wrap gap-5 border-b border-[var(--line)] pb-3 text-[10px]">
        {VISTAS.map(([k, t]) => (
          <button
            key={k}
            onClick={() => { setParams(k === "requisitos" ? {} : { vista: k }, { replace: true }); orb.poke(0.4); }}
            className={vista === k ? "text-[var(--bone)] underline decoration-[var(--c1)] underline-offset-[8px]" : "text-[var(--bone-faint)] hover:text-[var(--bone)]"}
          >
            {t}
          </button>
        ))}
      </div>

      {vista === "requisitos" && (
        <div className="space-y-8">
          {ciclos.length === 0 && <p className="text-sm text-[var(--bone-dim)]">Este proyecto aún no tiene requisitos.</p>}
          {ciclos.map(([c, reqs]) => (
            <section key={c}>
              <p className="mono mb-2 text-[9.5px] text-[var(--bone-faint)]">Ciclo C{c} · {reqs.length} {reqs.length === 1 ? "requisito" : "requisitos"}</p>
              <ol className="border-t border-[var(--line)]">
                {reqs.map((r) => {
                  const via = VIA[r.via];
                  return (
                    <li key={r.id}>
                      <Link to={`/requisitos/${r.id}`} className="group flex items-baseline gap-4 border-b border-[var(--line)] py-3 hover:bg-white/[0.02]">
                        <span className="mono w-16 shrink-0 text-[9.5px] text-[var(--bone-faint)]">{r.id}</span>
                        <span className="min-w-0 flex-1 text-[15px] leading-relaxed"><TextoMarcado texto={r.texto} marcados={r.traza.extraccion?.marcados ?? []} /></span>
                        <span className="mono flex shrink-0 items-center gap-2 text-[9.5px] text-[var(--bone-dim)]">
                          {estaEnProceso(r.estado) && <span className="gira" />}
                          {via && <span className="punto" style={{ background: via.tono }} />}
                          {via ? `${via.texto} · ` : ""}{INFO_ESTADO[r.estado].etiqueta}
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
        </div>
      )}

      {vista === "lel" && (
        <LelProyecto p={p} lelTodo={lelTodo ?? []} porAprobar={porAprobar} />
      )}

      {vista === "bigpicture" && <Panorama lista={conArtefactos} nombre={`big-picture-${p.id}`} />}

      {vista === "modelo" && (
        <ModeloConceptual lista={conArtefactos} nombre={`modelo-conceptual-${p.id}`} titulo={`Modelo conceptual — ${p.nombre}`} />
      )}
    </div>
  );
}

const ESTADO_ENTRADA = {
  [E.PENDIENTE_VALIDACION]: "por aprobar",
  [E.VALIDADO]: "aprobada",
  [E.FORMALIZADO]: "en el léxico",
  [E.RECHAZADO]: "rechazada",
};

function LelProyecto({ p, lelTodo, porAprobar }) {
  // Entradas principales (una por requisito) + símbolos secundarios ya formalizados
  const principales = p.lista.filter((r) => r.artefactos).map((r) => ({ ...artefactosDe(r).lel, requisitoId: r.id, estado: r.estado }));
  const secundarias = lelTodo.filter((e) => e.proyectoId === p.id && !e.principal);
  const todas = [...principales, ...secundarias.map((e) => ({ ...e, estado: E.FORMALIZADO }))].sort((a, b) => a.simbolo.localeCompare(b.simbolo, "es"));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="mono text-[9.5px] text-[var(--bone-faint)]">{todas.length} símbolos</p>
        {porAprobar.length > 0 && (
          <Link className="pill ml-auto" to={`/lel/generar?ids=${porAprobar.map((r) => r.id).join(",")}`}>Revisar y aprobar {porAprobar.length}</Link>
        )}
      </div>
      <ol className="grid gap-3 md:grid-cols-2">
        {todas.map((e, i) => (
          <li key={`${e.requisitoId}-${e.simbolo}-${i}`} className="rounded-2xl border border-[var(--line)] bg-white/[0.02] p-4 text-sm">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="serif text-[24px] leading-tight">{e.simbolo}</span>
              <span className="mono text-[9.5px] text-[var(--c1)]">{e.tipo}</span>
              <span className="mono ml-auto text-[9px] text-[var(--bone-faint)]">{ESTADO_ENTRADA[e.estado] ?? e.estado}</span>
            </div>
            <ul className="mt-2 space-y-1 text-[var(--bone-dim)]">{e.nocion.filter(Boolean).map((x, j) => <li key={j}>{x}</li>)}</ul>
            <Link to={`/requisitos/${e.requisitoId}`} className="mono mt-3 inline-block text-[9px] text-[var(--bone-faint)] hover:text-[var(--bone)]">{e.requisitoId} →</Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
