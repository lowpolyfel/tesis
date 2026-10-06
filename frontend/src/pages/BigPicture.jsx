import { useMemo } from "react";
import { Link, useSearchParams } from "react-router";
import { useApi } from "../hooks/useApi";
import { bigPictureDeProyecto, metasDeProyecto } from "../services/backend";
import ElegirProyecto, { useProyectoElegido } from "../components/ElegirProyecto";
import Diagrama from "../components/artefactos/Diagrama";
import { INFO_VIA, infoEstado } from "../constants/estados";
import { tipo as infoTipo } from "../constants/agentes";

/*
 * Artefactos del proyecto (ADR 0011), armados por el backend sin LLM a partir de
 * los requisitos formalizados y del LEL del proyecto:
 *   - Metas: el modelo de metas (meta, meta blanda, tarea, recurso) con ids
 *     globales, actores normalizados y vaguedad candidata a meta blanda.
 *   - Panorama: actores, acciones, restricciones, términos resueltos y
 *     dependencias entre requisitos por símbolos del LEL.
 *   - Grafo: el Big Picture como diagrama, exportable a Mermaid y PlantUML.
 */
const VISTAS = [["metas", "Metas"], ["panorama", "Panorama"], ["grafo", "Grafo"]];

const TIPO_META = {
  meta: { etiqueta: "Meta", clase: "bg-emerald-100 text-emerald-900" },
  meta_blanda: { etiqueta: "Meta blanda", clase: "bg-amber-100 text-amber-900" },
  tarea: { etiqueta: "Tarea", clase: "bg-sky-100 text-sky-900" },
  recurso: { etiqueta: "Recurso", clase: "bg-slate-100 text-slate-800" },
};
const MOTIVO_FUERA = {
  en_proceso: "sin formalizar todavía", rechazado: "rechazado", error: "con error", reprocesado: "reprocesado por otro",
  sin_formalizacion: "sin formalizar", sin_traza: "sin traza",
};
const CAMBIO = { ninguno: "aprobada tal cual", eleccion: "la persona eligió otra", edicion: "la persona la editó" };

export default function BigPicture() {
  const { proyectoId, proyecto, proyectos, elegir } = useProyectoElegido();
  const [params, setParams] = useSearchParams();
  const vista = VISTAS.some(([k]) => k === params.get("vista")) ? params.get("vista") : "metas";
  const { datos: metas, error: errorMetas } = useApi(() => (proyectoId ? metasDeProyecto(proyectoId) : Promise.resolve(null)), [proyectoId]);
  const { datos: bp, error: errorBp } = useApi(() => (proyectoId ? bigPictureDeProyecto(proyectoId) : Promise.resolve(null)), [proyectoId]);
  const error = errorMetas ?? errorBp;

  const cambiar = (k) => setParams((prev) => {
    const p = new URLSearchParams(prev);
    if (k === "metas") p.delete("vista"); else p.set("vista", k);
    return p;
  }, { replace: true });

  const vacio = metas && bp && metas.metas.length === 0 && bp.nodos.length === 0;
  const fuera = metas?.requisitos_fuera ?? bp?.requisitos_fuera ?? [];

  return (
    <div className="space-y-7">
      <header className="space-y-3">
        <p className="mono text-[10px] text-[var(--bone-faint)]">Artefactos del proyecto</p>
        <h1>Metas y Big Picture.</h1>
        <p className="max-w-2xl text-sm text-[var(--bone-dim)]">
          Se arman a partir de los requisitos ya formalizados (requisito reescrito y metas del Modelador) y del LEL del proyecto. No intervienen LLM: se recalculan cada vez.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <ElegirProyecto proyectoId={proyectoId} proyectos={proyectos} onCambio={elegir} />
          {proyectoId && <Link className="pill ghost" to={`/proyectos/${proyectoId}`}>Proyecto</Link>}
        </div>
      </header>

      {error && <p className="text-sm text-[var(--danger)]">{error.message}</p>}
      {proyectoId && !error && (!metas || !bp) && <p className="text-sm text-[var(--bone-dim)]">Armando los artefactos…</p>}

      {vacio && (
        <p className="text-sm text-[var(--bone-dim)]">
          {proyecto?.nombre ?? "Este proyecto"} todavía no tiene requisitos formalizados. Aparecen cuando una persona valida un requisito y el Modelador lo formaliza.
        </p>
      )}

      {metas && bp && !vacio && (
        <>
          <div className="mono flex flex-wrap gap-5 border-b border-[var(--line)] pb-3 text-[10px]">
            {VISTAS.map(([k, t]) => (
              <button key={k} onClick={() => cambiar(k)} className={vista === k ? "text-[var(--bone)] underline decoration-[var(--c1)] underline-offset-[8px]" : "text-[var(--bone-faint)] hover:text-[var(--bone)]"}>{t}</button>
            ))}
          </div>
          {vista === "metas" && <Metas m={metas} />}
          {vista === "panorama" && <Panorama bp={bp} />}
          {vista === "grafo" && (
            <section className="space-y-3">
              <p className="mono text-[9.5px] text-[var(--bone-faint)]">
                {bp.nodos.length} nodos · {bp.aristas.length} relaciones · formas al estilo i*: actor círculo, meta redondeada, meta blanda estadio, tarea hexágono, recurso rectángulo
              </p>
              <Diagrama mermaid={bp.mermaid} plantuml={bp.plantuml} nombre={`big-picture-${proyectoId}`} />
            </section>
          )}
        </>
      )}

      {fuera.length > 0 && (
        <section className="space-y-2">
          <h3 className="mono text-[10px] text-[var(--bone-faint)]">Requisitos que no entran ({fuera.length})</h3>
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-[var(--bone-dim)]">
            {fuera.map((r) => (
              <li key={r.req_id}>
                <Link className="mono text-[10px] hover:text-[var(--c1)]" to={`/requisitos/${r.req_id}`}>{r.req_id}</Link> {MOTIVO_FUERA[r.motivo] ?? r.motivo}{r.estado && r.motivo === "en_proceso" ? ` (${infoEstado(r.estado).etiqueta.toLowerCase()})` : ""}{r.detalle ? ` (${r.detalle})` : ""}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function Metas({ m }) {
  // árbol por «contribuye_a»; las que no contribuyen a otra son raíces
  const hijos = useMemo(() => {
    const h = new Map();
    for (const x of m.metas) h.set(x.contribuye_a ?? null, [...(h.get(x.contribuye_a ?? null) ?? []), x]);
    return h;
  }, [m]);
  const ids = new Set(m.metas.map((x) => x.id));
  const raices = m.metas.filter((x) => !x.contribuye_a || !ids.has(x.contribuye_a));

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap gap-2">
        {Object.entries(TIPO_META).map(([k, t]) => (
          <span key={k} className={`rounded-lg px-3 py-1.5 ${t.clase}`}>
            <span className="block font-mono text-[20px] leading-none">{m.por_tipo[k] ?? 0}</span>
            <span className="text-[11px]">{t.etiqueta}</span>
          </span>
        ))}
      </div>

      <section className="space-y-3">
        <h2>Actores</h2>
        <ol className="grid gap-3 md:grid-cols-2">
          {m.actores.map((a) => (
            <li key={a.nombre} className="rounded-2xl border border-[var(--line)] bg-white/[0.02] p-4">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="serif text-[24px] leading-tight">{a.nombre}</span>
                {a.simbolo_lel && <span className="mono text-[9.5px] text-[var(--c1)]">LEL: {a.simbolo_lel}</span>}
                <span className="mono ml-auto text-[9.5px] text-[var(--bone-faint)]">{a.metas.length} metas</span>
              </div>
              {a.metas.length > 0 && <p className="mono mt-2 text-[10px] text-[var(--bone-dim)]">{a.metas.join(" · ")}</p>}
            </li>
          ))}
          {m.actores.length === 0 && <p className="text-sm text-[var(--bone-dim)]">Ningún actor identificado.</p>}
        </ol>
      </section>

      <section className="space-y-3">
        <h2>Modelo de metas</h2>
        <ul className="space-y-1">
          {raices.map((x) => <NodoMeta key={x.id} x={x} hijos={hijos} nivel={0} />)}
        </ul>
        {m.sin_actor.length > 0 && <p className="mono text-[9.5px] text-[var(--bone-faint)]">Sin actor: {m.sin_actor.join(", ")}</p>}
      </section>

      {m.metas_blandas_desde_vaguedad.length > 0 && (
        <section className="space-y-2">
          <h2>Vaguedad que pide una meta blanda</h2>
          <p className="max-w-2xl text-sm text-[var(--bone-dim)]">Expresiones vagas de los requisitos: un límite impreciso suele ser un atributo de calidad que conviene volver meta blanda.</p>
          <ul className="space-y-1 text-sm">
            {m.metas_blandas_desde_vaguedad.map((v) => (
              <li key={`${v.req_id}-${v.texto}`} className="flex flex-wrap items-baseline gap-2">
                <Link className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--c1)]" to={`/requisitos/${v.req_id}`}>{v.req_id}</Link>
                <span className={`rounded px-1.5 ${infoTipo("vaguedad").clase}`}>«{v.texto}»</span>
                <span className="text-[var(--bone-dim)]">{v.meta_blanda ? `ya la recoge ${v.meta_blanda}` : "ninguna meta blanda la recoge todavía"}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function NodoMeta({ x, hijos, nivel }) {
  const t = TIPO_META[x.tipo];
  return (
    <li>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-[var(--line)] py-2" style={{ paddingLeft: `${nivel * 22}px` }}>
        {nivel > 0 && <span className="text-[var(--bone-faint)]">↳</span>}
        <span className={`rounded px-1.5 text-[11px] ${t.clase}`}>{t.etiqueta}</span>
        <span className="min-w-0 flex-1 text-[15px]">{x.enunciado}</span>
        <span className="mono text-[9.5px] text-[var(--bone-faint)]">
          {x.actor && <span className="text-[var(--bone-dim)]">{x.actor} · </span>}
          {x.simbolos.length > 0 && <span>{x.simbolos.join(", ")} · </span>}
          <Link className="hover:text-[var(--c1)]" to={`/requisitos/${x.req_id}`}>{x.id}</Link>
        </span>
      </div>
      {(hijos.get(x.id) ?? []).length > 0 && (
        <ul>{hijos.get(x.id).map((h) => <NodoMeta key={h.id} x={h} hijos={hijos} nivel={nivel + 1} />)}</ul>
      )}
    </li>
  );
}

function Panorama({ bp }) {
  const p = bp.panorama;
  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <h2>Actores</h2>
        <p className="flex flex-wrap gap-2">{p.actores.map((a) => <span key={a} className="rounded-full border border-[var(--line)] px-3 py-1 text-sm">{a}</span>)}</p>
      </section>

      <section className="space-y-2">
        <h2>Quién hace qué</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="mono text-[9px] text-[var(--bone-faint)]">
              <tr><th className="py-1.5 font-normal">Actor</th><th className="py-1.5 font-normal">Acción</th><th className="py-1.5 font-normal">Sobre</th><th className="py-1.5 font-normal">Meta</th></tr>
            </thead>
            <tbody>
              {p.acciones.map((a, i) => (
                <tr key={`${a.meta}-${i}`} className="border-t border-[var(--line)] align-top">
                  <td className="py-1.5 pr-3">{a.actor ?? <span className="text-[var(--bone-faint)]">—</span>}</td>
                  <td className="py-1.5 pr-3 font-medium">{a.verbo ?? <span className="text-[var(--bone-faint)]">—</span>}</td>
                  <td className="py-1.5 pr-3">{a.objeto}</td>
                  <td className="mono py-1.5 text-[10px]"><Link className="hover:text-[var(--c1)]" to={`/requisitos/${a.req_id}`}>{a.meta}</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {p.restricciones.length > 0 && (
        <section className="space-y-2">
          <h2>Restricciones y calidad</h2>
          <ul className="space-y-1 text-sm">
            {p.restricciones.map((r, i) => (
              <li key={`${r.req_id}-${i}`} className="flex flex-wrap items-baseline gap-2">
                <span className={`rounded px-1.5 text-[11px] ${r.origen === "vaguedad" ? infoTipo("vaguedad").clase : TIPO_META.meta_blanda.clase}`}>{r.origen === "vaguedad" ? "vaguedad" : "meta blanda"}</span>
                <span>{r.texto}</span>
                <Link className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--c1)]" to={`/requisitos/${r.req_id}`}>{r.meta ?? r.req_id}</Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-2">
        <h2>Términos resueltos</h2>
        <ul className="grid gap-2 md:grid-cols-2">
          {p.terminos_resueltos.map((t) => (
            <li key={`${t.req_id}-${t.termino}`} className="rounded-xl border border-[var(--line)] p-3 text-sm">
              <p className="flex flex-wrap items-baseline gap-2">
                <span className="italic">«{t.termino}»</span>
                <span className={`rounded px-1.5 text-[11px] ${infoTipo(t.tipo_ambiguedad).clase}`}>{infoTipo(t.tipo_ambiguedad).etiqueta}</span>
                <Link className="mono ml-auto text-[10px] text-[var(--bone-faint)] hover:text-[var(--c1)]" to={`/requisitos/${t.req_id}`}>{t.req_id}</Link>
              </p>
              <p className="mt-1">{t.significado}</p>
              <p className="mono mt-1 flex flex-wrap items-center gap-2 text-[9px] text-[var(--bone-faint)]">
                {t.via && INFO_VIA[t.via] && <span className="flex items-center gap-1"><span className="punto" style={{ background: INFO_VIA[t.via].tono }} />{INFO_VIA[t.via].etiqueta}</span>}
                {t.cambio && <span>{CAMBIO[t.cambio] ?? t.cambio}</span>}
              </p>
            </li>
          ))}
        </ul>
        {bp.terminos_sin_simbolo.length > 0 && (
          <p className="text-[12px] text-[var(--bone-faint)]">
            Términos de las metas sin símbolo en el LEL: {bp.terminos_sin_simbolo.map((t) => t.termino).join(", ")}.
          </p>
        )}
      </section>

      {p.dependencias.length > 0 && (
        <section className="space-y-2">
          <h2>Dependencias entre requisitos</h2>
          <p className="text-sm text-[var(--bone-dim)]">Un requisito usa un símbolo del LEL que resolvió otro.</p>
          <ul className="mono space-y-1 text-[11px] text-[var(--bone-dim)]">
            {p.dependencias.map((d) => (
              <li key={`${d.de}-${d.a}-${d.por}`}>
                <Link className="hover:text-[var(--c1)]" to={`/requisitos/${d.de}`}>{d.de}</Link> usa «{d.por}», resuelto en <Link className="hover:text-[var(--c1)]" to={`/requisitos/${d.a}`}>{d.a}</Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-2">
        <h2>Requisitos reescritos</h2>
        <ol className="border-t border-[var(--line)]">
          {p.requisitos.map((r) => (
            <li key={r.req_id} className="flex gap-4 border-b border-[var(--line)] py-2.5">
              <Link className="mono w-12 shrink-0 text-[10px] text-[var(--bone-faint)] hover:text-[var(--c1)]" to={`/requisitos/${r.req_id}`}>{r.req_id}</Link>
              <span className="text-[15px]">{r.requisito_reescrito}</span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
