import { useMemo, useState } from "react";
import { Link } from "react-router";
import { useApi } from "../../hooks/useApi";
import { bigPictureDeProyecto, metasDeProyecto } from "../../services/backend";
import { ESTADOS as E } from "../../constants/estados";
import { tipo as infoTipo } from "../../constants/agentes";
import Diagrama from "../../components/artefactos/Diagrama";
import { Aviso, Cargando, Plegable, Vacio } from "../../components/ui";

/*
 * El Big Picture del proyecto (ADR 0011): el grafo de actores, metas, requisitos
 * y términos del léxico, de todos los requisitos listos o solo de los elegidos.
 * El backend lo arma sin LLM desde lo formalizado. Debajo, plegados, el modelo
 * de metas y el panorama en texto.
 */
const TIPO_META = {
  meta: { etiqueta: "Meta", tono: "#57f7a7" },
  meta_blanda: { etiqueta: "Meta blanda", tono: "#ffc457" },
  tarea: { etiqueta: "Tarea", tono: "#5cc8ff" },
  recurso: { etiqueta: "Recurso", tono: "#cbd5e1" },
};

export default function Mapa({ proyectoId, requisitos, seleccion, onSeleccion }) {
  const clave = seleccion.join(",");
  const { datos: bp, error: e1 } = useApi(() => bigPictureDeProyecto(proyectoId, seleccion), [proyectoId, clave]);
  const { datos: metas, error: e2 } = useApi(() => metasDeProyecto(proyectoId, seleccion), [proyectoId, clave]);
  const listos = requisitos.filter((q) => q.estado === E.FORMALIZADO);
  const error = e1 ?? e2;

  return (
    <div className="space-y-6">
      <Eleccion listos={listos} seleccion={seleccion} onSeleccion={onSeleccion} />
      <Aviso error={error} />
      {!error && (!bp || !metas) && <Cargando>Armando el mapa…</Cargando>}
      {bp && metas && !bp.nodos.length && (
        <Vacio>{seleccion.length ? "Los requisitos elegidos todavía no están listos." : "El mapa se arma con los requisitos listos. Todavía no hay ninguno."}</Vacio>
      )}
      {bp && metas && bp.nodos.length > 0 && (
        <>
          <Diagrama mermaid={bp.mermaid} plantuml={bp.plantuml} nombre={`mapa-${proyectoId}${seleccion.length ? `-${seleccion.join("-")}` : ""}`} />
          <p className="mono text-[10px] text-[var(--bone-faint)]">
            {bp.nodos.filter((n) => n.tipo === "requisito").length} requisito{bp.nodos.filter((n) => n.tipo === "requisito").length === 1 ? "" : "s"} · {metas.metas.length} metas · {metas.actores.length} actor{metas.actores.length === 1 ? "" : "es"} · {bp.nodos.filter((n) => n.tipo === "simbolo").length} términos del léxico
          </p>
          <Plegable titulo="Modelo de metas" nota="quién persigue qué">
            <Metas m={metas} />
          </Plegable>
          <Plegable titulo="Panorama" nota="acciones, restricciones y dependencias">
            <Panorama bp={bp} />
          </Plegable>
        </>
      )}
    </div>
  );
}

/* Todos los requisitos listos o solo algunos */
function Eleccion({ listos, seleccion, onSeleccion }) {
  const [abierta, setAbierta] = useState(false);
  const [marcados, setMarcados] = useState(() => new Set(seleccion));
  const abrir = () => { setMarcados(new Set(seleccion.length ? seleccion : listos.map((q) => q.req_id))); setAbierta(true); };
  const alternar = (id) => setMarcados((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const aplicar = () => {
    const ids = listos.map((q) => q.req_id).filter((id) => marcados.has(id));
    onSeleccion(ids.length === listos.length ? [] : ids);
    setAbierta(false);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-[14px] text-[var(--bone-dim)]">
          {seleccion.length
            ? <>Mapa de <b className="font-medium text-[var(--bone)]">{seleccion.length}</b> requisito{seleccion.length === 1 ? "" : "s"}: {seleccion.join(", ")}</>
            : <>Mapa de todos los requisitos listos ({listos.length})</>}
        </p>
        <span className="ml-auto flex gap-2">
          {seleccion.length > 0 && <button className="pill ghost sm" onClick={() => onSeleccion([])}>Todos</button>}
          {listos.length > 1 && <button className="pill ghost sm" onClick={abierta ? () => setAbierta(false) : abrir}>{abierta ? "Cerrar" : "Elegir requisitos"}</button>}
        </span>
      </div>
      {abierta && (
        <div className="tarjeta space-y-3 p-4">
          <ol className="max-h-72 space-y-1 overflow-y-auto">
            {listos.map((q) => (
              <li key={q.req_id}>
                <label className="flex cursor-pointer items-start gap-3 rounded-lg px-2 py-1.5 hover:bg-white/[0.03]">
                  <input type="checkbox" className="casilla mt-0.5" checked={marcados.has(q.req_id)} onChange={() => alternar(q.req_id)} />
                  <span className="mono w-10 shrink-0 pt-0.5 text-[10px] text-[var(--bone-faint)]">{q.req_id}</span>
                  <span className="text-[14px] leading-snug">{q.texto}</span>
                </label>
              </li>
            ))}
          </ol>
          <div className="flex gap-2">
            <button className="pill sm" disabled={!marcados.size} onClick={aplicar}>Crear mapa con {marcados.size}</button>
            <button className="mono px-2 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setMarcados(new Set())}>ninguno</button>
          </div>
        </div>
      )}
    </div>
  );
}

function Metas({ m }) {
  const hijos = useMemo(() => {
    const h = new Map();
    for (const x of m.metas) h.set(x.contribuye_a ?? null, [...(h.get(x.contribuye_a ?? null) ?? []), x]);
    return h;
  }, [m]);
  const ids = new Set(m.metas.map((x) => x.id));
  const raices = m.metas.filter((x) => !x.contribuye_a || !ids.has(x.contribuye_a));
  return (
    <div className="space-y-5">
      <p className="flex flex-wrap gap-2">
        {m.actores.map((a) => (
          <span key={a.nombre} className="rounded-full border border-[var(--line)] px-3 py-1 text-[13px]" title={a.metas.join(" · ")}>
            {a.nombre} <span className="text-[var(--bone-faint)]">· {a.metas.length}</span>
          </span>
        ))}
      </p>
      <ul>{raices.map((x) => <NodoMeta key={x.id} x={x} hijos={hijos} nivel={0} />)}</ul>
    </div>
  );
}

function NodoMeta({ x, hijos, nivel }) {
  const t = TIPO_META[x.tipo];
  return (
    <li>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-[var(--line)] py-2" style={{ paddingLeft: `${nivel * 22}px` }}>
        {nivel > 0 && <span className="text-[var(--bone-faint)]">↳</span>}
        <span className="etiqueta" style={{ color: t?.tono }}>{t?.etiqueta ?? x.tipo}</span>
        <span className="min-w-0 flex-1 text-[15px]">{x.enunciado}</span>
        <span className="mono text-[9.5px] text-[var(--bone-faint)]">
          {x.actor && <span className="text-[var(--bone-dim)]">{x.actor} · </span>}
          <Link className="hover:text-[var(--bone)]" to={`/requisitos/${x.req_id}`}>{x.req_id}</Link>
        </span>
      </div>
      {(hijos.get(x.id) ?? []).length > 0 && <ul>{hijos.get(x.id).map((h) => <NodoMeta key={h.id} x={h} hijos={hijos} nivel={nivel + 1} />)}</ul>}
    </li>
  );
}

function Panorama({ bp }) {
  const p = bp.panorama;
  return (
    <div className="space-y-6 text-[14px]">
      {p.acciones.length > 0 && (
        <section className="space-y-2">
          <p className="etiqueta">Quién hace qué</p>
          <ul className="space-y-1">
            {p.acciones.map((a, i) => (
              <li key={`${a.meta}-${i}`} className="flex flex-wrap gap-x-2">
                <span className="text-[var(--bone)]">{a.actor ?? "—"}</span>
                <span className="font-medium">{a.verbo ?? "—"}</span>
                <span className="text-[var(--bone-dim)]">{a.objeto}</span>
                <Link className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" to={`/requisitos/${a.req_id}`}>{a.req_id}</Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      {p.restricciones.length > 0 && (
        <section className="space-y-2">
          <p className="etiqueta">Calidad y restricciones</p>
          <ul className="space-y-1">
            {p.restricciones.map((r, i) => (
              <li key={`${r.req_id}-${i}`} className="flex flex-wrap items-baseline gap-2">
                <span className={`rounded px-1.5 text-[11px] ${infoTipo("vaguedad").clase}`}>{r.origen === "vaguedad" ? "vago" : "meta blanda"}</span>
                {r.texto}
                <Link className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" to={`/requisitos/${r.req_id}`}>{r.req_id}</Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      {p.dependencias.length > 0 && (
        <section className="space-y-2">
          <p className="etiqueta">Dependencias</p>
          <ul className="space-y-1 text-[var(--bone-dim)]">
            {p.dependencias.map((d) => (
              <li key={`${d.de}-${d.a}-${d.por}`}>
                <Link className="enlace" to={`/requisitos/${d.de}`}>{d.de}</Link> usa «{d.por}», que se aclaró en <Link className="enlace" to={`/requisitos/${d.a}`}>{d.a}</Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
