import { useEffect, useState } from "react";
import { armarFicha, fichaContexto } from "../../services/backend";
import { descargar } from "../../components/artefactos/exportar";

/*
 * La ficha del contexto (ADR 0022): el contexto general ordenado por el Revisor en
 * resumen, actores, conceptos, procesos, reglas, lo que queda fuera y lo que no dice.
 * Contra ella se revisa cada requisito antes de analizarlo. Se guarda en la base en
 * JSON y en Markdown; si el contexto cambia, se avisa que hay que actualizarla.
 */
export default function FichaContexto({ proyecto }) {
  const [abierta, setAbierta] = useState(false);
  const [estado, setEstado] = useState(null); // respuesta de GET /ficha
  const [armando, setArmando] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!abierta) return undefined;
    let vivo = true;
    fichaContexto(proyecto.proyecto_id).then((r) => vivo && setEstado(r)).catch((e) => vivo && setError(e.message));
    return () => { vivo = false; };
  }, [abierta, proyecto.proyecto_id, proyecto.contexto, proyecto.nombre]);

  const armar = async () => {
    setArmando(true);
    setError(null);
    try { setEstado(await armarFicha(proyecto.proyecto_id)); } catch (e) { setError(e.message); } finally { setArmando(false); }
  };

  const f = estado?.ficha?.ficha;
  return (
    <div className="space-y-3">
      <button className="mono text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => setAbierta((x) => !x)} aria-expanded={abierta}>
        {abierta ? "▾" : "▸"} ficha del contexto
      </button>
      {abierta && (
        <div className="tarjeta aparece space-y-4 p-5">
          {!estado && !error && <p className="mono flex items-center gap-2 text-[10px] text-[var(--bone-faint)]"><span className="gira" /> buscando la ficha…</p>}
          {estado && !f && (
            <p className="text-[14px] text-[var(--bone-dim)]">
              Todavía no hay ficha. El Revisor ordena el contexto en actores, conceptos, procesos y reglas, y con ella revisa cada requisito antes de analizarlo.
            </p>
          )}
          {estado && f && !estado.al_dia && <p className="text-[13px] text-[var(--aviso)]">El contexto cambió después de armar esta ficha: actualízala.</p>}
          {f && <Ficha f={f} />}
          {error && <p className="text-[13px] text-[var(--danger)]">{error}</p>}
          {estado && (
            <div className="mono flex flex-wrap items-center gap-x-4 gap-y-2 text-[10px] text-[var(--bone-faint)]">
              <button className="pill sm" disabled={armando} onClick={armar}>{armando ? "El Revisor la está armando…" : f ? "Actualizar la ficha" : "Armar la ficha"}</button>
              {f && <button className="hover:text-[var(--bone)]" onClick={() => descargar(`contexto-${proyecto.proyecto_id}.md`, estado.ficha.markdown, "text/markdown")}>descargar .md</button>}
              {f && <button className="hover:text-[var(--bone)]" onClick={() => descargar(`contexto-${proyecto.proyecto_id}.json`, JSON.stringify(f, null, 2), "application/json")}>descargar .json</button>}
              {estado.ficha?.modelo && <span>{estado.ficha.modelo} · {estado.ficha.creada?.slice(0, 10)}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Lista({ titulo, items }) {
  if (!items?.length) return null;
  return (
    <section className="space-y-1.5">
      <p className="etiqueta">{titulo}</p>
      <ul className="space-y-1 text-[14px] leading-snug text-[var(--bone-dim)]">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </section>
  );
}

function Ficha({ f }) {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <section className="space-y-1.5 md:col-span-2">
        <p className="text-[15px] leading-relaxed text-[var(--bone)]">{f.resumen}</p>
        <p className="text-[14px] text-[var(--bone-dim)]"><span className="etiqueta mr-2">Objetivo</span>{f.objetivo}</p>
      </section>
      <Lista titulo="Actores" items={f.actores.map((a) => <><b className="font-medium text-[var(--bone)]">{a.nombre}</b>: {a.rol}</>)} />
      <Lista titulo="Conceptos del dominio" items={f.conceptos.map((c) => <><b className="font-medium text-[var(--bone)]">{c.termino}</b>: {c.significado}</>)} />
      <Lista titulo="Procesos" items={f.procesos} />
      <Lista titulo="Reglas del negocio" items={f.reglas} />
      <Lista titulo="Fuera de alcance" items={f.fuera_de_alcance} />
      <Lista titulo="Lo que el contexto no dice" items={f.vacios} />
    </div>
  );
}
