import { useState } from "react";
import { Link } from "react-router";
import { useApi } from "../../hooks/useApi";
import { corregirLel, obtenerLel } from "../../services/backend";
import { INFO_VIA } from "../../constants/estados";
import { TIPOS_LEL } from "../../constants/agentes";
import { useOrb } from "../../components/orb/useOrb";
import { Aviso, Cargando, Chip, Vacio } from "../../components/ui";

/*
 * El léxico del proyecto (LEL): cada término que tenía más de un significado,
 * con el significado acordado. Es la memoria del proyecto: un término que ya
 * está aquí no se vuelve a debatir. Cada entrada se puede corregir.
 */
const sinAcentos = (s) => s.normalize("NFD").replace(/\p{Mn}/gu, "").toLowerCase();

export default function Lexico({ proyectoId }) {
  const { datos: lel, error, recargar } = useApi(() => obtenerLel(proyectoId), [proyectoId]);
  const [q, setQ] = useState("");

  if (error) return <Aviso error={error} />;
  if (!lel) return <Cargando>Cargando el léxico…</Cargando>;
  if (!lel.length) {
    return <Vacio>El léxico se llena solo: cada vez que los agentes aclaran una palabra con varios significados, queda aquí.</Vacio>;
  }
  const filtro = sinAcentos(q.trim());
  const orden = [...lel]
    .filter((e) => !filtro || sinAcentos(`${e.simbolo} ${e.termino}`).includes(filtro))
    .sort((a, b) => a.simbolo.localeCompare(b.simbolo, "es"));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-[14px] text-[var(--bone-dim)]">{lel.length} término{lel.length === 1 ? "" : "s"}</p>
        {lel.length > 6 && (
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar…" aria-label="Buscar en el léxico"
            className="campo ml-auto w-56 py-2 text-[14px]" />
        )}
      </div>
      <ol className="grid gap-4 md:grid-cols-2">
        {orden.map((e) => <EntradaLel key={`${e.req_id}-${e.termino}`} e={e} editable onCambio={recargar} />)}
      </ol>
      {!orden.length && <p className="text-[14px] text-[var(--bone-faint)]">Nada coincide con «{q}».</p>}
    </div>
  );
}

/* Una entrada del LEL; `editable` agrega «corregir». `conProyecto`: algo más en la línea de datos */
export function EntradaLel({ e, editable = false, onCambio, conProyecto = null }) {
  const orb = useOrb();
  const [editando, setEditando] = useState(false);
  const via = INFO_VIA[e.via];

  if (editando) return <EditorLel e={e} onListo={(cambio) => { setEditando(false); if (cambio) onCambio?.(); }} />;
  return (
    <li className="tarjeta flex flex-col p-5" onPointerEnter={() => orb.poke(0.25)}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="serif text-[26px] leading-tight">{e.simbolo}</span>
        <span className="etiqueta">{e.tipo}</span>
        {editable && <button className="mono ml-auto text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setEditando(true)}>corregir</button>}
      </div>
      <div className="mt-3 space-y-3 text-[14.5px] leading-relaxed">
        <div>
          <p className="etiqueta" title="Noción (LEL)">Qué es</p>
          <ul className="mt-1 space-y-1 text-[var(--bone-dim)]">{e.nocion.map((x, j) => <li key={j}>{x}</li>)}</ul>
        </div>
        <div>
          <p className="etiqueta" title="Impacto (LEL)">Qué implica</p>
          <ul className="mt-1 space-y-1 text-[var(--bone-dim)]">{e.impacto.map((x, j) => <li key={j}>{x}</li>)}</ul>
        </div>
      </div>
      <p className="mono mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-4 text-[9.5px] text-[var(--bone-faint)]">
        {e.termino !== e.simbolo && <span className="normal-case tracking-normal">de «{e.termino}»</span>}
        {via && <span title={via.etiqueta}>{via.simple}</span>}
        {e.corregida && <Chip tono="#94a3b8">corregido</Chip>}
        <Link to={`/requisitos/${e.req_id}`} className="hover:text-[var(--bone)]">{e.req_id} →</Link>
        {conProyecto}
      </p>
    </li>
  );
}

function EditorLel({ e, onListo }) {
  const orb = useOrb();
  const [simbolo, setSimbolo] = useState(e.simbolo);
  const [tipo, setTipo] = useState(e.tipo);
  const [nocion, setNocion] = useState(e.nocion.join("\n"));
  const [impacto, setImpacto] = useState(e.impacto.join("\n"));
  const [error, setError] = useState(null);
  const lineas = (t) => t.split("\n").map((s) => s.trim()).filter(Boolean);

  const guardar = async (ev) => {
    ev.preventDefault();
    try {
      await corregirLel(e.req_id, e.termino, { simbolo: simbolo.trim(), tipo, nocion: lineas(nocion), impacto: lineas(impacto) });
      orb.setMood("success", { revertAfter: 900 });
      onListo(true);
    } catch (err) {
      setError(err);
    }
  };

  return (
    <li className="tarjeta p-5 md:col-span-2">
      <form onSubmit={guardar} className="space-y-4">
        <div className="flex flex-wrap gap-4">
          <label className="min-w-48 flex-1 space-y-1.5">
            <span className="etiqueta block">Término</span>
            <input autoFocus value={simbolo} maxLength={120} onChange={(ev) => setSimbolo(ev.target.value)} className="campo text-[15px]" />
          </label>
          <label className="space-y-1.5">
            <span className="etiqueta block">Tipo</span>
            <select value={tipo} onChange={(ev) => setTipo(ev.target.value)} className="campo w-auto">
              {TIPOS_LEL.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
        </div>
        <label className="block space-y-1.5">
          <span className="etiqueta">Qué es <span className="normal-case tracking-normal">(una idea por renglón)</span></span>
          <textarea value={nocion} rows={3} onChange={(ev) => setNocion(ev.target.value)} className="campo text-[14px]" />
        </label>
        <label className="block space-y-1.5">
          <span className="etiqueta">Qué implica <span className="normal-case tracking-normal">(una idea por renglón)</span></span>
          <textarea value={impacto} rows={3} onChange={(ev) => setImpacto(ev.target.value)} className="campo text-[14px]" />
        </label>
        <p className="text-[12px] text-[var(--bone-faint)]">Los requisitos que analices después usarán esta versión.</p>
        <Aviso error={error} />
        <div className="flex gap-2">
          <button className="pill sm" disabled={!simbolo.trim() || !lineas(nocion).length || !lineas(impacto).length}>Guardar</button>
          <button type="button" className="pill ghost sm" onClick={() => onListo(false)}>Cancelar</button>
        </div>
      </form>
    </li>
  );
}
