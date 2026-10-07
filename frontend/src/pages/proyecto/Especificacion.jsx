import { useState } from "react";
import { Link } from "react-router";
import { useApi } from "../../hooks/useApi";
import { corregirFormalizacion, especificacionDeProyecto } from "../../services/backend";
import { CATEGORIAS_NF, TIPO_REQUISITO } from "../../constants/agentes";
import { descargar } from "../../components/artefactos/exportar";
import { useOrb } from "../../components/orb/useOrb";
import { Aviso, Cargando, Chip, Plegable, Vacio } from "../../components/ui";

/*
 * La salida del proyecto: cada requisito reescrito completo y sin ambigüedad,
 * separado en funcionales y no funcionales, con lo que el Modelador supuso a
 * partir del contexto. Todo se puede corregir aquí; cada corrección queda en la
 * traza del requisito. Se descarga como Markdown.
 */
export default function Especificacion({ proyecto, seleccion, onTodos }) {
  const pid = proyecto.proyecto_id;
  const { datos: e, error, recargar } = useApi(() => especificacionDeProyecto(pid, seleccion), [pid, seleccion.join(",")]);

  if (error) return <Aviso error={error} />;
  if (!e) return <Cargando>Armando la especificación…</Cargando>;

  const total = e.funcionales.length + e.no_funcionales.length + e.sin_clasificar.length;
  const enCamino = e.requisitos_fuera.filter((f) => f.motivo === "en_proceso").length;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-3">
        {seleccion.length > 0 ? (
          <p className="text-[14px] text-[var(--bone-dim)]">
            Solo {seleccion.length === 1 ? "el requisito elegido" : `los ${seleccion.length} requisitos elegidos`} ·{" "}
            <button className="enlace" onClick={onTodos}>ver todos</button>
          </p>
        ) : (
          <p className="text-[14px] text-[var(--bone-dim)]">
            {total ? `${total} requisito${total === 1 ? "" : "s"} listo${total === 1 ? "" : "s"}` : "Todavía no hay requisitos listos"}
            {enCamino > 0 && <span className="text-[var(--bone-faint)]"> · {enCamino} más en camino</span>}
          </p>
        )}
        {total > 0 && (
          <span className="ml-auto flex gap-2">
            <button className="pill ghost sm" onClick={() => descargar(`especificacion-${pid}.md`, markdown(proyecto, e), "text/markdown")}>Descargar .md</button>
            <Copiar texto={() => markdown(proyecto, e)} />
          </span>
        )}
      </div>

      {!total && (
        <Vacio accion={proyecto.tipo !== "evaluacion" && <Link className="pill" to={`/proyectos/${pid}/analizar`}>Analizar requisitos</Link>}>
          Aquí aparecen los requisitos reescritos, separados en funcionales y no funcionales, en cuanto los agentes terminan.
        </Vacio>
      )}

      <Grupo titulo="Funcionales" nota="lo que el sistema hace" lista={e.funcionales} onCambio={recargar} />
      <Grupo titulo="No funcionales" nota="cualidades y restricciones" lista={e.no_funcionales} onCambio={recargar} />
      {e.sin_clasificar.length > 0 && (
        <Grupo titulo="Sin clasificar" nota="se formalizaron antes de que el Modelador los clasificara; elige su tipo" lista={e.sin_clasificar} onCambio={recargar} />
      )}

      {e.glosario.length > 0 && (
        <Plegable titulo={`Glosario · ${e.glosario.length}`} nota="los términos del léxico del proyecto">
          <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
            {e.glosario.map((g) => (
              <div key={g.simbolo}>
                <dt className="serif text-[20px] leading-tight">{g.simbolo}</dt>
                <dd className="text-[14px] text-[var(--bone-dim)]">{g.nocion ?? "—"}</dd>
              </div>
            ))}
          </dl>
        </Plegable>
      )}
    </div>
  );
}

function Grupo({ titulo, nota, lista, onCambio }) {
  if (!lista.length) return null;
  return (
    <section className="space-y-3">
      <h2 className="flex items-baseline gap-3">{titulo} · {lista.length} <span className="normal-case tracking-normal text-[12px] font-normal text-[var(--bone-faint)]">{nota}</span></h2>
      <ol className="space-y-3">{lista.map((x) => <Requisito key={x.req_id} x={x} onCambio={onCambio} />)}</ol>
    </section>
  );
}

function Requisito({ x, onCambio }) {
  const orb = useOrb();
  const [editando, setEditando] = useState(false);
  const [original, setOriginal] = useState(false);
  const tipo = TIPO_REQUISITO[x.tipo_requisito];

  if (editando) return <Editor x={x} onListo={(cambio) => { setEditando(false); if (cambio) onCambio(); }} />;
  return (
    <li className="tarjeta group p-5" onPointerEnter={() => orb.poke(0.25)}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <span className="mono w-14 shrink-0 pt-1 text-[11px]" style={{ color: tipo?.tono ?? "var(--bone-faint)" }}>{x.clave}</span>
        <p className="min-w-0 flex-1 text-[16px] leading-relaxed">{x.reescrito}</p>
        <button className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setEditando(true)}>corregir</button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 pl-[4.5rem] max-sm:pl-0">
        {x.categoria && <Chip tono={TIPO_REQUISITO.no_funcional.tono}>{CATEGORIAS_NF[x.categoria] ?? x.categoria}</Chip>}
        {x.corregido && <Chip tono="#94a3b8" titulo={`Corregido el ${x.corregido}`}>corregido</Chip>}
        <Link className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" to={`/requisitos/${x.req_id}`}>{x.req_id}{x.marca ? ` · ${x.marca}` : ""}</Link>
        {x.original !== x.reescrito && (
          <button className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setOriginal((v) => !v)}>
            {original ? "ocultar original" : "ver original"}
          </button>
        )}
      </div>
      {original && <p className="mt-2 pl-[4.5rem] text-[14px] italic text-[var(--bone-faint)] max-sm:pl-0">«{x.original}»</p>}
      {x.supuestos.length > 0 && (
        <ul className="mt-3 space-y-1 pl-[4.5rem] text-[13px] text-[#f2c879] max-sm:pl-0">
          {x.supuestos.map((s, i) => <li key={i} title="El Modelador lo concretó a partir del contexto del proyecto">Supuesto: {s}</li>)}
        </ul>
      )}
    </li>
  );
}

/* Corregir el texto, el tipo, la categoría o los supuestos (uno por renglón) */
export function Editor({ x, onListo }) {
  const orb = useOrb();
  const [texto, setTexto] = useState(x.reescrito);
  const [tipo, setTipo] = useState(x.tipo_requisito ?? "funcional");
  const [categoria, setCategoria] = useState(x.categoria ?? "");
  const [supuestos, setSupuestos] = useState(x.supuestos.join("\n"));
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const guardar = async (ev) => {
    ev.preventDefault();
    setEnviando(true);
    try {
      await corregirFormalizacion(x.req_id, {
        requisito_reescrito: texto.trim(),
        tipo_requisito: tipo,
        categoria: tipo === "no_funcional" && categoria ? categoria : null,
        supuestos: supuestos.split("\n").map((s) => s.trim()).filter(Boolean),
      });
      orb.setMood("success", { revertAfter: 900 });
      onListo(true);
    } catch (err) {
      setError(err);
      setEnviando(false);
    }
  };

  return (
    <li className="tarjeta list-none p-5">
      <form onSubmit={guardar} className="space-y-4">
        <label className="block space-y-1.5">
          <span className="etiqueta">{x.clave} · requisito</span>
          <textarea autoFocus value={texto} rows={3} maxLength={2000} onChange={(e) => setTexto(e.target.value)} className="campo text-[15px]" />
        </label>
        <div className="flex flex-wrap gap-4">
          <label className="space-y-1.5">
            <span className="etiqueta block">Tipo</span>
            <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="campo w-auto">
              {Object.entries(TIPO_REQUISITO).map(([k, t]) => <option key={k} value={k}>{t.etiqueta}</option>)}
            </select>
          </label>
          {tipo === "no_funcional" && (
            <label className="space-y-1.5">
              <span className="etiqueta block">Categoría</span>
              <select value={categoria} onChange={(e) => setCategoria(e.target.value)} className="campo w-auto">
                <option value="">Sin categoría</option>
                {Object.entries(CATEGORIAS_NF).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
              </select>
            </label>
          )}
        </div>
        <label className="block space-y-1.5">
          <span className="etiqueta">Supuestos <span className="normal-case tracking-normal">(uno por renglón)</span></span>
          <textarea value={supuestos} rows={2} onChange={(e) => setSupuestos(e.target.value)} className="campo text-[13.5px]" />
        </label>
        <Aviso error={error} />
        <div className="flex gap-2">
          <button className="pill sm" disabled={!texto.trim() || enviando}>Guardar</button>
          <button type="button" className="pill ghost sm" onClick={() => onListo(false)}>Cancelar</button>
        </div>
      </form>
    </li>
  );
}

function Copiar({ texto }) {
  const [hecho, setHecho] = useState(null);
  const copiar = async () => {
    try { await navigator.clipboard.writeText(texto()); setHecho("Copiado"); } catch { setHecho("No se pudo copiar"); }
    setTimeout(() => setHecho(null), 1600);
  };
  return <button className="pill ghost sm" onClick={copiar}>{hecho ?? "Copiar"}</button>;
}

/* La especificación como documento: contexto, RF, RNF, supuestos y glosario */
export function markdown(proyecto, e) {
  const linea = (x) => {
    const cat = x.categoria ? ` _(${CATEGORIAS_NF[x.categoria] ?? x.categoria})_` : "";
    const sup = x.supuestos.map((s) => `  - Supuesto: ${s}`).join("\n");
    return `- **${x.clave}**${cat} ${x.reescrito}  \n  <sub>${x.req_id}${x.marca ? ` · ${x.marca}` : ""} · original: «${x.original}»</sub>${sup ? `\n${sup}` : ""}`;
  };
  const partes = [`# Especificación de requisitos · ${proyecto.nombre}`];
  if (proyecto.contexto) partes.push(`## Contexto\n\n${proyecto.contexto}`);
  if (e.funcionales.length) partes.push(`## Requisitos funcionales\n\n${e.funcionales.map(linea).join("\n")}`);
  if (e.no_funcionales.length) partes.push(`## Requisitos no funcionales\n\n${e.no_funcionales.map(linea).join("\n")}`);
  if (e.sin_clasificar.length) partes.push(`## Sin clasificar\n\n${e.sin_clasificar.map(linea).join("\n")}`);
  if (e.glosario.length) partes.push(`## Glosario\n\n${e.glosario.map((g) => `- **${g.simbolo}** (${g.tipo}): ${g.nocion ?? "—"}`).join("\n")}`);
  partes.push(`<sub>Generado por Dudamel el ${new Date().toLocaleDateString("es-MX")}.</sub>`);
  return `${partes.join("\n\n")}\n`;
}
