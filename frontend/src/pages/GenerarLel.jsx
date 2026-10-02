import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useOrb, usePoseEsfera } from "../components/orb/useOrb";
import { useLote } from "../hooks/useLote";
import { formalizarRequisito, validarArtefactos } from "../services/api";
import { ESTADOS as E } from "../constants/estados";
import { TIPOS_LEL } from "../constants/agentes";

/*
 * Generar LEL. El Modelador (la esfera, en verde) redacta una entrada por
 * requisito. La persona puede editar cada una antes de aprobar; aprobar
 * valida los artefactos y los incorpora al léxico acumulado.
 */
const POSE = { d: { x: -0.31, y: 0, s: 0.72 }, m: { x: 0, y: -0.36, s: 0.38 } };
const REDACCION_MS = 1700;

const artefactosDe = (r) => r.artefactos?.validados ?? r.artefactos?.borrador ?? r.artefactos?.propuesta;

export default function GenerarLel() {
  const orb = useOrb();
  const [params] = useSearchParams();
  const ids = useMemo(() => (params.get("ids") ?? "").split(",").filter(Boolean), [params]);
  const { lista, recargar } = useLote(ids);
  const [listo, setListo] = useState(false);
  const [edicion, setEdicion] = useState({}); // id -> lel editada
  const [abierta, setAbierta] = useState(null);
  const [aprobando, setAprobando] = useState(false);
  const [aviso, setAviso] = useState(null);

  usePoseEsfera(POSE, []);

  useEffect(() => {
    orb.setMood("modelador");
    orb.update("core", { label: "Modelador", sub: "redactando el léxico…", active: true });
    const t = setTimeout(() => setListo(true), REDACCION_MS);
    return () => {
      clearTimeout(t);
      orb.update("core", { label: null, sub: null, active: false });
      orb.setMood("idle");
    };
  }, [orb]);

  const entradas = (lista ?? []).filter((r) => r.artefactos);
  const aprobables = entradas.filter((r) => r.estado === E.PENDIENTE_VALIDACION || r.estado === E.VALIDADO);

  useEffect(() => {
    if (listo && lista) orb.update("core", { sub: `${entradas.length} ${entradas.length === 1 ? "entrada" : "entradas"}`, active: false });
  }, [listo, lista, entradas.length, orb]);

  const lelDe = (r) => edicion[r.id] ?? artefactosDe(r).lel;

  const aprobarTodo = async () => {
    setAprobando(true);
    orb.setMood("thinking");
    for (const r of aprobables) {
      if (r.estado === E.PENDIENTE_VALIDACION) {
        const editado = Boolean(edicion[r.id]);
        await validarArtefactos(r.id, { ...artefactosDe(r), lel: lelDe(r) }, { editado, comentario: editado ? "Editado al generar el LEL" : "" });
      }
      await formalizarRequisito(r.id);
      orb.poke(0.7);
    }
    orb.setMood("success");
    setAviso(`${aprobables.length} ${aprobables.length === 1 ? "entrada incorporada" : "entradas incorporadas"} al léxico.`);
    setAprobando(false);
    setEdicion({});
    recargar();
  };

  return (
    <main className="relative z-10 mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-5 px-6 pt-[30vh] pb-16 md:mr-[7vw] md:pt-28">
      <p className="mono sube text-[10px] text-[var(--bone-faint)]">Léxico Extendido del Lenguaje</p>
      <h1 className="serif sube text-[clamp(44px,4.6vw,72px)] leading-[.95]" style={{ "--i": 1 }}>
        {listo ? <>Tu <em>léxico</em>.</> : <>Redactando<em>…</em></>}
      </h1>

      {listo && lista && (
        <>
          <p className="sube text-sm text-[var(--bone-dim)]" style={{ "--i": 2 }}>
            Una entrada por requisito. Edita lo que no te convenza: tu versión y la del agente se mezclan antes de aprobar.
          </p>
          <ol className="space-y-3">
            {entradas.map((r, i) => (
              <Entrada
                key={r.id}
                i={i}
                r={r}
                lel={lelDe(r)}
                editada={Boolean(edicion[r.id])}
                abierta={abierta === r.id}
                onAbrir={() => setAbierta(abierta === r.id ? null : r.id)}
                onCambio={(lel) => setEdicion((e) => ({ ...e, [r.id]: lel }))}
                onRestaurar={() => setEdicion(({ [r.id]: _, ...resto }) => resto)}
              />
            ))}
          </ol>
          <div className="sube flex flex-wrap items-center gap-3 pt-2" style={{ "--i": 4 + entradas.length }}>
            {aprobables.length > 0 && (
              <button className="pill" disabled={aprobando} onClick={aprobarTodo}>
                {aprobando ? "Incorporando…" : `Aprobar e incorporar ${aprobables.length}`}
              </button>
            )}
            <Link to="/lel" className="pill ghost">Ver léxico completo</Link>
            <Link to={`/big-picture?ids=${ids.join(",")}`} className="mono px-2 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]">Generar Big Picture →</Link>
          </div>
          {aviso && <p className="text-sm text-[#8ff5c0]">{aviso}</p>}
        </>
      )}
    </main>
  );
}

const ESTADO_ENTRADA = {
  [E.PENDIENTE_VALIDACION]: "por aprobar",
  [E.VALIDADO]: "aprobada",
  [E.FORMALIZADO]: "en el léxico",
  [E.RECHAZADO]: "rechazada",
};

function Entrada({ i, r, lel, editada, abierta, onAbrir, onCambio, onRestaurar }) {
  const editable = r.estado === E.PENDIENTE_VALIDACION;
  const set = (k) => (v) => onCambio({ ...lel, [k]: v });
  const lineas = (arr) => arr.join("\n");
  const deLineas = (t) => t.split("\n");

  return (
    <li className="sube rounded-2xl border border-[var(--line)] bg-white/[0.025] p-5 backdrop-blur-sm" style={{ "--i": 3 + i }}>
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {abierta && editable ? (
          <input value={lel.simbolo} onChange={(e) => set("simbolo")(e.target.value)} className="linea serif min-w-0 flex-1 text-[28px]" />
        ) : (
          <h2 className="serif text-[28px] leading-tight">{lel.simbolo}</h2>
        )}
        {abierta && editable ? (
          <select value={lel.tipo} onChange={(e) => set("tipo")(e.target.value)} className="mono rounded border border-[var(--line)] bg-transparent px-2 py-1 text-[10px]">
            {TIPOS_LEL.map((t) => <option key={t} className="bg-[#16130f]">{t}</option>)}
          </select>
        ) : (
          <span className="mono text-[10px] text-[var(--c1)]">{lel.tipo}</span>
        )}
        <span className="mono ml-auto text-[9.5px] text-[var(--bone-faint)]">
          {editada && <span className="mr-2 text-[var(--c1)]">editada ·</span>}
          {ESTADO_ENTRADA[r.estado] ?? r.estado}
        </span>
      </header>
      {lel.sinonimos?.length > 0 && !abierta && <p className="mt-1 text-xs text-[var(--bone-faint)]">también: {lel.sinonimos.join(", ")}</p>}

      <div className="mt-3 grid gap-4 text-sm sm:grid-cols-2">
        {[["nocion", "Noción"], ["impacto", "Impacto"]].map(([k, titulo]) => (
          <div key={k}>
            <p className="mono mb-1 text-[9.5px] text-[var(--bone-faint)]">{titulo}</p>
            {abierta && editable ? (
              <textarea
                value={lineas(lel[k])}
                onChange={(e) => set(k)(deLineas(e.target.value))}
                rows={Math.max(3, lel[k].length + 1)}
                className="w-full resize-y rounded-lg border border-[var(--line)] bg-transparent p-2 text-sm leading-relaxed outline-none focus:border-[var(--c1)]"
              />
            ) : (
              <ul className="space-y-1 leading-relaxed text-[var(--bone-dim)]">
                {lel[k].filter(Boolean).map((x, j) => <li key={j}>{x}</li>)}
              </ul>
            )}
          </div>
        ))}
      </div>

      <footer className="mono mt-4 flex flex-wrap items-center gap-4 text-[9.5px] text-[var(--bone-faint)]">
        <Link to={`/requisitos/${r.id}`} className="hover:text-[var(--bone)]">{r.id} · ver traza</Link>
        {editable && <button onClick={onAbrir} className="hover:text-[var(--bone)]">{abierta ? "listo" : "editar"}</button>}
        {editable && editada && <button onClick={onRestaurar} className="hover:text-[var(--bone)]">volver a la del agente</button>}
        {editable && <Link to={`/requisitos/${r.id}/validacion`} className="hover:text-[var(--bone)]">metas y big picture →</Link>}
      </footer>
    </li>
  );
}
