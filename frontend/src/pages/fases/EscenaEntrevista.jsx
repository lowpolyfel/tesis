import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { useOrb } from "../../components/orb/useOrb";
import { isMobile } from "../../components/orb/poses";
import { cancelarEntrevista, obtenerEntrevista, obtenerProyecto } from "../../services/backend";
import { seguirEntrevista } from "../../services/eventos";
import { ORDEN_NODOS_ENTREVISTA, nodo, tintaNodo } from "../../constants/agentes";
import { TERMINALES_ENTREVISTA, estadoEntrevista } from "../../constants/fases";
import { COLUMNA_ESCENA, centroEscena, clave, crearCoreografia } from "../../escena/coreografia";
import Preparacion from "../../escena/Preparacion";
import { useEnVivo } from "../../escena/useEnVivo";
import { pasoSimple } from "../../escena/pasoSimple";
import { resumenMensaje } from "../../escena/resumenMensaje";
import { Chip, Volver } from "../../components/ui";

/*
 * La escena de la versión 2 (ADR 0024): los agentes procesan la entrevista completa.
 *
 * Primero la preparación (la esfera revisa el servidor, la base y los modelos). Luego la
 * esfera se divide en el Revisor, el Extractor, los Filtros, el Clasificador, la
 * Divergencia, el Crítico y el Modelador, y cada mensaje real de la bitácora viaja de su
 * emisor a su receptor (la misma coreografía de la versión 1). Las intenciones de un
 * término ambiguo nacen del Clasificador y se acercan o alejan según su similitud; si
 * debaten, el Crítico objeta; al final todo llega al Modelador, que escribe el léxico.
 *
 * A la derecha, cada término que va apareciendo y qué pasó con él. Al terminar, la
 * esfera se vuelve a fundir y queda el resumen con el paso siguiente: validar el léxico.
 * Con ?escena=1 se vuelve a ver una entrevista ya procesada.
 */
const RITMOS = [0.5, 1, 2, 4];

export default function EscenaEntrevista() {
  const orb = useOrb();
  const { id: pid, eid } = useParams();
  const [params] = useSearchParams();
  const [doc, setDoc] = useState(null);
  const [nombre, setNombre] = useState(null);
  const [error, setError] = useState(null);
  const [fase, setFase] = useState("carga"); // carga → preparacion → division → trabajo → fusion → resultados
  const [lateral, setLateral] = useState(() => !isMobile());
  const [cancelando, setCancelando] = useState(false);

  useEffect(() => {
    obtenerProyecto(pid).then((p) => setNombre(p.nombre)).catch(() => {});
    obtenerEntrevista(eid).then(setDoc).catch(setError);
  }, [pid, eid]);

  useEffect(() => {
    if (fase !== "carga" || !doc) return;
    const terminada = TERMINALES_ENTREVISTA.includes(doc.estado) && !doc.ocupada;
    if (terminada && params.get("escena") !== "1") setFase("resultados");
    else setFase(terminada ? "division" : "preparacion");
  }, [fase, doc, params]);

  const coreografia = useMemo(() => crearCoreografia(orb, { nodos: ORDEN_NODOS_ENTREVISTA }), [orb]);
  const vivo = useEnVivo(fase === "trabajo" || fase === "fusion" ? eid : null,
    { coreografia, ritmoInicial: 2, seguir: seguirEntrevista, pausa: null });
  const alDia = vivo.animados >= vivo.mensajes.length;

  /* mitosis inicial */
  useEffect(() => {
    if (fase !== "division") return undefined;
    orb.setPose({ x: centroEscena(), y: -0.06, s: 0.9 });
    orb.setMood("revisor");
    orb.update("core", { label: "Sistema", sub: doc?.titulo ?? "" });
    const t = setTimeout(() => { coreografia.montar(); setFase("trabajo"); }, 700);
    return () => clearTimeout(t);
  }, [fase, orb, coreografia, doc]);

  /* el estado de la entrevista, dicho debajo del sistema */
  useEffect(() => {
    if (fase === "trabajo" && vivo.estado) coreografia.estado(vivo.estado, estadoEntrevista(vivo.estado).texto.toLowerCase());
  }, [fase, vivo.estado, coreografia]);

  /* terminó y ya se vio todo: los agentes se funden */
  useEffect(() => {
    if (fase !== "trabajo" || !vivo.terminado || !alDia) return undefined;
    const t = setTimeout(() => {
      coreografia.desmontar();
      orb.setPose({ x: centroEscena(), y: -0.06, s: 0.95 });
      orb.setMood(vivo.estado === "lista" ? "success" : vivo.estado === "error" ? "error" : "idle");
      setFase("fusion");
    }, 1600);
    return () => clearTimeout(t);
  }, [fase, vivo.terminado, vivo.estado, alDia, coreografia, orb]);

  useEffect(() => {
    if (fase !== "fusion") return undefined;
    const t = setTimeout(() => {
      obtenerEntrevista(eid).then(setDoc).catch(() => {});
      setFase("resultados");
    }, 1500);
    return () => clearTimeout(t);
  }, [fase, eid]);

  useEffect(() => {
    if (fase !== "resultados") return;
    orb.setPose(isMobile() ? { x: 0, y: -0.33, s: 0.45 } : { x: -0.3, y: 0, s: 0.8 });
    orb.setMood(doc?.estado === "lista" ? "extractor" : doc?.estado === "error" ? "error" : "idle");
    orb.update("core", { label: doc?.estado === "lista" ? "Léxico propuesto" : estadoEntrevista(doc?.estado).texto, sub: null, desde: null });
  }, [fase, doc, orb]);

  useEffect(() => {
    const alCambiar = () => { coreografia.reacomodar(); setLateral(!isMobile()); };
    addEventListener("resize", alCambiar);
    return () => removeEventListener("resize", alCambiar);
  }, [coreografia]);

  const trabajando = fase === "division" || fase === "trabajo";
  useEffect(() => { orb.update("core", { desde: trabajando ? Date.now() : null }); }, [orb, trabajando]);
  useEffect(() => () => {
    coreografia.desmontar();
    orb.update("core", { label: null, sub: null, desde: null });
    orb.setMood("idle");
  }, [orb, coreografia]);

  const cancelar = async () => {
    setCancelando(true);
    try { await cancelarEntrevista(eid); } catch (e) { setError(e); }
  };

  if (error && !doc) {
    return (
      <main className="relative z-10 mx-auto max-w-xl px-6 pt-[30vh] text-center">
        <p className="serif text-3xl">No pude abrir la entrevista.</p>
        <p className="mt-3 text-sm text-[var(--bone-dim)]">{error.message}</p>
        <Link to={`/proyectos/${pid}?fase=entrevista`} className="pill ghost mt-6">Volver</Link>
      </main>
    );
  }
  if (!doc) return null;

  return (
    <main className="relative z-10 min-h-screen">
      <div className="fixed top-20 left-5 z-20 md:top-24 md:left-10">
        <Volver a={`/proyectos/${pid}?fase=entrevista`}>{nombre ?? "Proyecto"}</Volver>
      </div>
      {fase === "preparacion" && <Preparacion proyecto={pid} onListo={() => setFase("division")} />}
      {fase === "trabajo" && (
        <Columna doc={doc} vivo={vivo} lateral={lateral} cancelando={cancelando}
          onCancelar={TERMINALES_ENTREVISTA.includes(vivo.estado) ? null : cancelar} />
      )}
      {fase === "fusion" && (
        <p className="mono aparece fixed inset-x-0 bottom-[18vh] text-center text-[10px] text-[var(--bone-dim)]">Reuniendo a los agentes…</p>
      )}
      {fase === "resultados" && (
        <Resultados doc={doc} pid={pid} onVerOtraVez={() => setFase("division")} />
      )}
    </main>
  );
}

/* ---------------------------------------------------------------- */

/* Qué pasó con cada término, según los mensajes ya animados */
function terminosDe(mensajes) {
  const t = new Map();
  const poner = (termino, estado, tono) => {
    const k = clave(termino);
    t.set(k, { termino: t.get(k)?.termino ?? termino, estado, tono });
  };
  for (const m of mensajes) {
    const p = m.payload ?? {};
    if (m.tipo === "filtrado") {
      for (const x of p.terminos ?? []) {
        const [estado, tono] = {
          candidato: ["por interpretar", "#a99bff"], regional: ["regional · por interpretar", "#ffc457"],
          resuelto_por_lel: ["ya en el léxico", "#57f7a7"], descartado_por_persona: ["lo habías descartado", "#94a3b8"],
          fuera_del_limite: ["fuera del límite", "#94a3b8"], vaguedad: ["expresión vaga", "#c4b5fd"],
        }[x.decision_filtro] ?? [x.decision_filtro, "#94a3b8"];
        poner(x.termino, estado, tono);
      }
    } else if (m.tipo === "interpretaciones") {
      for (const r of p.resultados ?? []) {
        poner(r.termino, r.univoco ? "una intención" : `${r.interpretaciones.length} intenciones`, r.univoco ? "#41efff" : "#ffc457");
      }
    } else if (m.tipo === "similitud" && p.termino && m.ronda === 0) {
      poner(p.termino, p.similitud >= p.umbral ? "se parecen: sin debate" : "a debate", p.similitud >= p.umbral ? "#57f7a7" : "#ff9f6b");
    } else if (m.tipo === "consenso") {
      poner(p.termino, "acuerdo tras debatir", "#57f7a7");
    } else if (m.tipo === "arbitraje") {
      poner(p.termino, "eligió el Crítico", "#ffc457");
    } else if (m.tipo === "formalizacion" && p.alcance === "lexico") {
      for (const e of p.entradas ?? []) poner(e.termino, `al léxico: «${e.simbolo}»`, "#57f7a7");
    }
  }
  return [...t.values()];
}

function Columna({ doc, vivo, lateral, cancelando, onCancelar }) {
  const animados = vivo.mensajes.slice(0, vivo.animados);
  const actual = animados.at(-1);
  const terminos = terminosDe(animados);
  const siguienteRitmo = RITMOS[(RITMOS.indexOf(vivo.ritmo) + 1) % RITMOS.length];
  const estilo = lateral ? { width: COLUMNA_ESCENA } : undefined;
  return (
    <aside className={lateral
      ? "aparece fixed top-24 right-4 bottom-4 z-20 flex flex-col overflow-hidden rounded-2xl border border-[var(--line)] bg-[color-mix(in_oklab,var(--bg)_92%,transparent)]"
      : "aparece fixed inset-x-3 bottom-3 z-20 max-h-[42vh] overflow-y-auto rounded-2xl border border-[var(--line)] bg-[color-mix(in_oklab,var(--bg)_94%,transparent)]"}
    style={estilo}>
      <section className="border-b border-[var(--line)] px-5 py-4">
        <p className="mono text-[10px] text-[var(--bone-faint)]">
          {doc.entrevista_id} · {doc.n_turnos} turnos · <span className="text-[var(--bone-dim)]">{estadoEntrevista(vivo.estado ?? doc.estado).texto}</span>
        </p>
        <p className="serif mt-1 text-[22px] leading-tight">{doc.titulo}</p>
      </section>
      <section className="border-b border-[var(--line)] px-5 py-4">
        {actual ? (
          <p className="text-[15px] leading-snug">
            <span className="mono mr-2 text-[10px]" style={{ color: tintaNodo(actual.emisor) }}>{nodo(actual.emisor).nombre}</span>
            {pasoSimple(actual)}
          </p>
        ) : <p className="text-[15px] text-[var(--bone-dim)]">{vivo.error ? vivo.error.message : "Esperando a que la entrevista tenga turno…"}</p>}
        <p className="mono mt-3 flex items-center gap-3 text-[10px] text-[var(--bone-faint)]">
          <button onClick={() => vivo.setRitmo(siguienteRitmo)} className="hover:text-[var(--bone)]" title="Velocidad de la animación">{vivo.ritmo}×</button>
          {vivo.animados < vivo.mensajes.length && <button onClick={vivo.acelerar} className="hover:text-[var(--bone)]">saltar</button>}
          {onCancelar && <button onClick={onCancelar} disabled={cancelando} className="ml-auto hover:text-[var(--danger)]">{cancelando ? "deteniendo…" : "cancelar"}</button>}
        </p>
      </section>
      <section className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        <p className="etiqueta mb-2">Términos {terminos.length > 0 && <span className="opacity-60">{terminos.length}</span>}</p>
        {!terminos.length && <p className="text-[13px] text-[var(--bone-faint)]">Aparecerán conforme el Extractor los encuentre.</p>}
        <ul className="space-y-1.5">
          {terminos.map((t) => (
            <li key={clave(t.termino)} className="flex items-baseline justify-between gap-3 text-[13.5px]">
              <span className="truncate">{t.termino}</span>
              <span className="mono shrink-0 text-[9.5px]" style={{ color: `color-mix(in oklab, ${t.tono} var(--mezcla-tono), var(--bone))` }}>{t.estado}</span>
            </li>
          ))}
        </ul>
        <details className="plegable mt-5">
          <summary className="etiqueta py-1">Bitácora técnica</summary>
          <ol className="mt-2 space-y-1.5">
            {animados.map((m) => (
              <li key={m.secuencia} className="text-[11.5px] leading-snug text-[var(--bone-dim)]">
                <span className="mono text-[9px]" style={{ color: tintaNodo(m.emisor) }}>{m.secuencia} {nodo(m.emisor).nombre} → {nodo(m.receptor).nombre}</span>{" "}
                {resumenMensaje(m)}
              </li>
            ))}
          </ol>
        </details>
      </section>
    </aside>
  );
}

function Resultados({ doc, pid, onVerOtraVez }) {
  const r = doc.resumen;
  const lista = doc.estado === "lista";
  return (
    <section className="aparece mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 px-6 pt-[40vh] pb-12 md:mr-[8vw] md:pt-24">
      <p className="etiqueta">{doc.entrevista_id} · {doc.titulo}</p>
      {lista ? (
        <>
          <h1 className="serif text-[clamp(40px,4vw,62px)] leading-[.95]">El léxico <em>espera</em> tu validación.</h1>
          <p className="text-[15px] leading-relaxed text-[var(--bone-dim)]">
            Los agentes propusieron <b className="font-normal text-[var(--bone)]">{r?.nuevas ?? 0} términos</b> con su intención
            {r?.conocidas ? <> y sumaron citas a {r.conocidas} que el proyecto ya conocía</> : null}.
            {r?.ambiguas ? <> {r.ambiguas} admitían más de una intención{r.arbitradas ? <>; en {r.arbitradas} los agentes no se pusieron de acuerdo y eligió el Crítico</> : null}.</> : null}
            {" "}Revisa cada uno: si alguno no significa lo que quiso decir el cliente, corrígelo y el sistema lo aprenderá.
          </p>
          <div className="flex flex-wrap gap-2">
            {r?.ambiguas > 0 && <Chip tono="#ffc457">{r.ambiguas} con más de una intención</Chip>}
            {r?.regionales > 0 && <Chip tono="#ff9f6b">{r.regionales} regional{r.regionales === 1 ? "" : "es"}</Chip>}
            {doc.vaguedad?.length > 0 && <Chip tono="#c4b5fd">{doc.vaguedad.length === 1 ? "1 expresión vaga" : `${doc.vaguedad.length} expresiones vagas`}</Chip>}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Link className="pill" to={`/proyectos/${pid}?fase=lexico`}>Validar el léxico</Link>
            <button className="pill ghost" onClick={onVerOtraVez}>Ver otra vez</button>
          </div>
        </>
      ) : (
        <>
          <h1 className="serif text-[clamp(36px,3.6vw,56px)] leading-[.95]">{doc.estado === "cancelada" ? "Se canceló." : "No se pudo terminar."}</h1>
          {doc.error && <p className="text-[14px] text-[var(--danger)]">{doc.error}</p>}
          <div className="flex flex-wrap gap-3">
            <Link className="pill" to={`/proyectos/${pid}?fase=entrevista`}>Volver a la entrevista</Link>
          </div>
        </>
      )}
    </section>
  );
}
