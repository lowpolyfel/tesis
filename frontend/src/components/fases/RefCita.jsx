import { useEffect, useState } from "react";
import { entrevistasDeProyecto, obtenerEntrevista } from "../../services/backend";

/*
 * Las citas de la entrevista («E01:T3») que respaldan una meta o un requisito. Al tocarlas se
 * ve lo que se dijo en ese turno. `useCitas` reúne los turnos de las entrevistas listas.
 */
export function useCitas(proyectoId) {
  const [turnos, setTurnos] = useState({});
  useEffect(() => {
    let vivo = true;
    entrevistasDeProyecto(proyectoId)
      .then((ls) => Promise.all(ls.filter((e) => e.estado === "lista").map((e) => obtenerEntrevista(e.entrevista_id))))
      .then((docs) => {
        if (!vivo) return;
        const m = {};
        for (const d of docs) for (const t of d.turnos) m[`${d.entrevista_id}:T${t.n}`] = { hablante: t.hablante, texto: t.texto };
        setTurnos(m);
      })
      .catch(() => {});
    return () => { vivo = false; };
  }, [proyectoId]);
  return turnos;
}

export default function Citas({ refs, turnos }) {
  const [abierta, setAbierta] = useState(null);
  if (!refs?.length) return null;
  const t = abierta ? turnos[abierta] : null;
  return (
    <div className="space-y-1.5">
      <span className="flex flex-wrap items-center gap-1.5">
        <span className="etiqueta">Entrevista</span>
        {refs.map((r) => (
          <button key={r} type="button" onClick={() => setAbierta((x) => (x === r ? null : r))}
            title={turnos[r] ? `${turnos[r].hablante ? `${turnos[r].hablante}: ` : ""}${turnos[r].texto}` : r}
            className={`mono rounded-full border px-2 py-0.5 text-[9.5px] ${abierta === r ? "border-[var(--c1)] text-[var(--bone)]" : "border-[var(--line)] text-[var(--bone-faint)] hover:text-[var(--bone)]"}`}>
            {r}
          </button>
        ))}
      </span>
      {t && (
        <p className="text-[13px] leading-relaxed text-[var(--bone-dim)]">
          {t.hablante && <b className="font-medium text-[var(--bone)]">{t.hablante}: </b>}«{t.texto}»
        </p>
      )}
    </div>
  );
}
