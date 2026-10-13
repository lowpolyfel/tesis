import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useApi } from "../../hooks/useApi";
import {
  borrarEntrevista, cancelarEntrevista, entrevistasDeProyecto, obtenerEntrevista, reprocesarEntrevista,
} from "../../services/backend";
import { estadoEntrevista } from "../../constants/fases";
import { useOrb } from "../../components/orb/useOrb";
import { Aviso, Cargando, Chip, Confirmar, Plegable, Vacio } from "../../components/ui";

/*
 * Fase 1 (ADR 0024): las entrevistas del proyecto. Cada una entra a la cola y los agentes
 * proponen su LEL; aquí se ve en qué va, lo que anotó el Revisor (participantes,
 * problemas, necesidades, reglas) y sus turnos. Se puede ver a los agentes trabajar,
 * cancelar, volver a procesar lo que falló y borrar.
 */
const SONDEO_MS = 2000;

export default function Entrevistas({ proyectoId, onCambio }) {
  const { datos: lista, error, recargar } = useApi(() => entrevistasDeProyecto(proyectoId), [proyectoId]);
  const trabajando = (lista ?? []).some((e) => e.ocupada || estadoEntrevista(e.estado).trabajando);

  useEffect(() => {
    if (!trabajando) return undefined;
    const t = setInterval(() => { recargar(); onCambio?.(); }, SONDEO_MS);
    return () => clearInterval(t);
  }, [trabajando, recargar, onCambio]);

  if (error) return <Aviso error={error} />;
  if (!lista) return <Cargando>Cargando las entrevistas…</Cargando>;
  if (!lista.length) {
    return (
      <Vacio accion={<Link className="pill" to={`/proyectos/${proyectoId}/entrevista`}>Subir la entrevista</Link>}>
        Empieza por la entrevista con el cliente: pega el texto o sube el PDF. Los agentes encontrarán cada término del dominio y su intención.
      </Vacio>
    );
  }
  const cambio = () => { recargar(); onCambio?.(); };
  return (
    <ol className="space-y-4">
      {[...lista].reverse().map((e) => <Entrevista key={e.entrevista_id} e={e} proyectoId={proyectoId} onCambio={cambio} />)}
    </ol>
  );
}

function Entrevista({ e, proyectoId, onCambio }) {
  const orb = useOrb();
  const [borrando, setBorrando] = useState(false);
  const [error, setError] = useState(null);
  const s = estadoEntrevista(e.estado);
  const trabajando = e.ocupada || s.trabajando;
  const r = e.resumen;
  const accion = (fn) => async () => {
    setError(null);
    try { await fn(); orb.poke(0.5); onCambio(); } catch (x) { setError(x); }
  };

  return (
    <li className="tarjeta space-y-4 p-5" onPointerEnter={() => orb.poke(0.2)}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="mono text-[10px] text-[var(--bone-faint)]">
            {e.entrevista_id} · {e.n_turnos} turnos{e.hablantes?.length ? ` · ${e.hablantes.length} hablantes` : ""}
            {e.origen?.archivo ? ` · ${e.origen.archivo}` : ""}
          </p>
          <p className="serif mt-1 text-[24px] leading-tight">{e.titulo}</p>
        </div>
        <Chip tono={s.tono}>{trabajando && <span className="gira -ml-0.5 h-2.5 w-2.5" />}{s.texto}</Chip>
      </div>

      {r && (
        <p className="flex flex-wrap gap-x-5 gap-y-1 text-[13.5px] text-[var(--bone-dim)]">
          <span><b className="font-normal text-[var(--bone)]">{r.nuevas}</b> términos nuevos</span>
          {r.conocidas > 0 && <span><b className="font-normal text-[var(--bone)]">{r.conocidas}</b> ya conocidos</span>}
          {r.ambiguas > 0 && <span><b className="font-normal text-[#ffc457]">{r.ambiguas}</b> con más de una intención</span>}
          {r.debatidas > 0 && <span>{r.debatidas} debatido{r.debatidas === 1 ? "" : "s"}</span>}
          {r.arbitradas > 0 && <span>{r.arbitradas} por arbitraje</span>}
          {r.regionales > 0 && <span>{r.regionales} regional{r.regionales === 1 ? "" : "es"}</span>}
        </p>
      )}
      {e.error && <p className="text-[13.5px] text-[var(--danger)]">{e.error}</p>}
      <Aviso error={error} />

      <div className="flex flex-wrap items-center gap-2">
        <Link className={trabajando ? "pill sm" : "pill ghost sm"} to={`/proyectos/${proyectoId}/entrevistas/${e.entrevista_id}${trabajando ? "" : "?escena=1"}`}>
          {trabajando ? "Ver a los agentes" : "Ver otra vez a los agentes"}
        </Link>
        {trabajando && <button className="pill ghost sm" onClick={accion(() => cancelarEntrevista(e.entrevista_id))}>Cancelar</button>}
        {["error", "cancelada"].includes(e.estado) && !e.ocupada && (
          <button className="pill sm" onClick={accion(() => reprocesarEntrevista(e.entrevista_id))}>Volver a procesar</button>
        )}
        {!trabajando && <button className="mono ml-auto px-1 text-[10px] text-[var(--bone-faint)] hover:text-[var(--danger)]" onClick={() => setBorrando(true)}>borrar</button>}
      </div>
      {borrando && (
        <Confirmar
          pregunta={`¿Borrar la entrevista «${e.titulo}»?`}
          detalle="Sus citas salen del léxico. Los términos que solo ella proponía y nadie validó se borran; los validados se quedan."
          accion="Borrar entrevista"
          onCancelar={() => setBorrando(false)}
          onConfirmar={async () => { await borrarEntrevista(e.entrevista_id); setBorrando(false); onCambio(); }}
        />
      )}
      <Detalles e={e} />
    </li>
  );
}

/* Lo que anotó el Revisor y los turnos: se piden al abrir */
function Detalles({ e }) {
  const [abierto, setAbierto] = useState(false);
  const [doc, setDoc] = useState(null);
  useEffect(() => {
    if (abierto && !doc) obtenerEntrevista(e.entrevista_id).then(setDoc).catch(() => {});
  }, [abierto, doc, e.entrevista_id]);
  const f = e.ficha;
  return (
    <details className="plegable" onToggle={(ev) => setAbierto(ev.currentTarget.open)}>
      <summary className="flex items-center gap-3 py-1">
        <span className="flecha text-[var(--bone-faint)]" aria-hidden="true">▸</span>
        <span className="etiqueta text-[var(--bone-dim)]">Lo que se dijo</span>
        {f && <span className="text-[12px] text-[var(--bone-faint)]">{f.necesidades?.length ?? 0} necesidades · {f.problemas?.length ?? 0} problemas · {f.reglas?.length ?? 0} reglas</span>}
      </summary>
      <div className="space-y-5 pt-4 text-[14px]">
        {f?.participantes?.length > 0 && (
          <Bloque titulo="Participantes">
            {f.participantes.map((p, i) => <li key={i}><b className="font-normal text-[var(--bone)]">{p.nombre}</b> — {p.rol}</li>)}
          </Bloque>
        )}
        {f?.objetivo && <Bloque titulo="Objetivo"><li>{f.objetivo}</li></Bloque>}
        {["necesidades", "problemas", "reglas"].map((c) => f?.[c]?.length > 0 && (
          <Bloque key={c} titulo={c[0].toUpperCase() + c.slice(1)}>
            {f[c].map((h, i) => (
              <li key={i}>{h.texto} {h.turnos?.length > 0 && <span className="mono text-[9.5px] text-[var(--bone-faint)]">{h.turnos.map((n) => `T${n}`).join(" ")}</span>}</li>
            ))}
          </Bloque>
        ))}
        {e.vaguedad?.length > 0 && (
          <Bloque titulo="Expresiones vagas">
            {e.vaguedad.map((v, i) => <li key={i}>«{v.expresion}» <span className="mono text-[9.5px] text-[var(--bone-faint)]">{v.turnos.map((n) => `T${n}`).join(" ")}</span></li>)}
          </Bloque>
        )}
        {f?.avisos?.length > 0 && <p className="text-[12.5px] text-[var(--aviso)]">{f.avisos.join(" ")}</p>}
        {e.advertencias?.length > 0 && <p className="text-[12.5px] text-[var(--bone-faint)]">{e.advertencias.join(" ")}</p>}
        <Plegable titulo="Turnos" nota={`${e.n_turnos}`}>
          {!doc ? <Cargando>Cargando los turnos…</Cargando> : (
            <ol className="max-h-[420px] space-y-2 overflow-y-auto pr-2">
              {doc.turnos.map((t) => (
                <li key={t.n} className="grid grid-cols-[3.2rem_1fr] gap-2 text-[13.5px] leading-relaxed">
                  <span className="mono pt-0.5 text-[9.5px] text-[var(--bone-faint)]">T{t.n}</span>
                  <span>{t.hablante && <b className="font-medium text-[var(--bone)]">{t.hablante}: </b>}<span className="text-[var(--bone-dim)]">{t.texto}</span></span>
                </li>
              ))}
            </ol>
          )}
        </Plegable>
      </div>
    </details>
  );
}

function Bloque({ titulo, children }) {
  return (
    <div>
      <p className="etiqueta">{titulo}</p>
      <ul className="mt-1.5 space-y-1 text-[var(--bone-dim)]">{children}</ul>
    </div>
  );
}
