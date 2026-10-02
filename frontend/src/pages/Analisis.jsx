import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useOrb } from "../components/orb/useOrb";
import { isMobile } from "../components/orb/poses";
import { seguirLote } from "../services/polling";
import { ESTADOS as E, VIAS_RESOLUCION as V, INFO_ESTADO, estaEnProceso } from "../constants/estados";
import { AGENTES } from "../constants/agentes";
import TextoMarcado from "../components/TextoMarcado";

/*
 * Analizar, paso 3. La esfera hace mitosis: se divide en los cuatro agentes
 * y el trabajo se ve en ellos.
 *   - el agente en turno crece y agita sus ondas; los demás se atenúan
 *   - si las lecturas divergen, el Clasificador se divide en Lectura A y B,
 *     que se acercan conforme sube la similitud en cada ronda
 *   - consenso: A y B se funden de vuelta; arbitraje: el Crítico las absorbe
 *   - al terminar, los agentes se funden en una sola esfera y aparecen los resultados
 */

const ORDEN = ["extractor", "clasificador", "critico", "modelador"];
const MOOD = { extractor: "extractor", clasificador: "clasificador", critico: "critico", modelador: "modelador" };

const geo = () => {
  const m = isMobile();
  return {
    fila: m ? -0.12 : -0.1,
    x: m ? [-0.36, -0.12, 0.12, 0.36] : [-0.3, -0.1, 0.1, 0.3],
    s: m ? 0.2 : 0.32,
    sActivo: m ? 0.28 : 0.44,
    par: m ? 0.12 : 0.17,
    sPar: m ? 0.16 : 0.25,
  };
};

const VIA = {
  [V.DIRECTO]: { texto: "directo", tono: "#57f7a7" },
  [V.CONSENSO]: { texto: "consenso", tono: "#a99bff" },
  [V.ARBITRAJE]: { texto: "arbitraje", tono: "#ffc457" },
};

/* Quién trabaja en cada estado del requisito en foco */
const TURNO = {
  [E.CARGADO]: "extractor",
  [E.EXTRAIDO]: "clasificador",
  [E.INTERPRETADO]: "clasificador",
  [E.EN_DEBATE]: "critico",
  [E.ACEPTADO_DIRECTO]: "modelador",
  [E.CONSENSO]: "modelador",
  [E.ARBITRADO]: "modelador",
};

function subtitulo(agente, r) {
  const t = r.traza;
  switch (agente) {
    case "extractor":
      return t.extraccion ? `${t.extraccion.terminos.length} términos · ${t.extraccion.marcados.length} marcados` : "leyendo el requisito…";
    case "clasificador":
      if (t.clasificacion) return t.clasificacion.enDisputa.length ? `2 lecturas de ${t.clasificacion.enDisputa.map((x) => `«${x}»`).join(" y ")}` : "2 lecturas, sin disputa";
      return t.extraccion ? "buscando otras lecturas…" : "en espera";
    case "critico":
      if (t.debate) {
        if (t.debate.resultado === "consenso") return `consenso en la ronda ${t.debate.rondas.length}`;
        if (t.debate.resultado === "agotado") return t.debate.arbitraje ? `arbitró: lectura ${t.debate.arbitraje.eleccion}` : "arbitrando…";
        const n = t.debate.rondas.length;
        return n < t.debate.maxRondas ? `conduciendo la ronda ${n + 1} de ${t.debate.maxRondas}` : "arbitrando…";
      }
      if (t.divergencia?.decision === "directo") return "sin debate";
      return "en espera";
    case "modelador":
      if (t.artefactos) return "LEL, metas y Big Picture listos";
      if (t.resolucion) return "generando artefactos…";
      return "en espera";
    default:
      return "";
  }
}

export default function Analisis() {
  const orb = useOrb();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const ids = useMemo(() => (params.get("ids") ?? "").split(",").filter(Boolean), [params]);
  const [lista, setLista] = useState(null);
  const [fase, setFase] = useState("division"); // division → trabajo → fusion → resultados
  const arranco = useRef(false);
  const rondasPrevias = useRef(0);

  useEffect(() => {
    if (!ids.length) navigate("/inicio", { replace: true });
  }, [ids, navigate]);

  useEffect(() => seguirLote(ids, setLista), [ids]);

  const terminado = lista && lista.every((r) => !estaEnProceso(r.estado));
  const foco = lista?.find((r) => estaEnProceso(r.estado)) ?? null;
  const indiceFoco = foco ? lista.indexOf(foco) : -1;

  /* ---- 1. mitosis inicial (o directo a resultados si ya estaba todo listo) ---- */
  const cargado = Boolean(lista);
  const terminadoRef = useRef(false);
  terminadoRef.current = Boolean(terminado);
  useEffect(() => {
    if (!cargado || fase !== "division") return;
    if (terminadoRef.current && !arranco.current) {
      orb.setPose(isMobile() ? { x: 0, y: -0.33, s: 0.45 } : { x: -0.3, y: 0, s: 0.8 });
      setFase("resultados");
      return;
    }
    arranco.current = true;
    orb.setPose({ x: 0, y: -0.06, s: 0.9 });
    orb.setMood("idle");
    orb.update("core", { label: "Dividiendo en agentes", sub: `${ids.length} ${ids.length === 1 ? "requisito" : "requisitos"}` });
    const t = setTimeout(() => {
      const g = geo();
      orb.update("core", { label: null, sub: null });
      orb.setPose({ x: 0, y: g.fila, s: 0 });
      orb.divide(
        "core",
        ORDEN.map((a, i) => ({
          id: a,
          mood: MOOD[a],
          x: g.x[i],
          y: g.fila,
          s: g.s,
          label: AGENTES[a].nombre,
          sub: "en espera",
        }))
      );
      setFase("trabajo");
    }, 650);
    return () => clearTimeout(t);
  }, [cargado, fase, orb, ids.length]);

  /* ---- 2. coreografía del requisito en foco ---- */
  useEffect(() => {
    if (fase !== "trabajo" || !foco) return;
    const g = geo();
    const turno = TURNO[foco.estado];
    ORDEN.forEach((a, i) => {
      orb.update(a, {
        active: a === turno,
        dim: Boolean(turno) && a !== turno,
        x: g.x[i],
        y: g.fila,
        s: a === turno ? g.sActivo : g.s,
        sub: subtitulo(a, foco),
      });
    });
    if (turno) orb.setAmbient(MOOD[turno]);

    // Lecturas A y B: nacen del Clasificador cuando hay debate
    const debate = foco.traza.debate;
    const enDebate = foco.estado === E.EN_DEBATE;
    if (enDebate && !orb.has("lecA")) {
      const lect = foco.traza.clasificacion.interpretaciones;
      const resumen = (k) => lect[k].lecturas.map((l) => `«${l.termino}» = ${l.significado}`).join(" · ");
      orb.divide("clasificador", [
        { id: "lecA", mood: "lecturaA", x: g.x[2] - 0.2, y: g.par, s: g.sPar, label: "Lectura A", sub: resumen("A") },
        { id: "lecB", mood: "lecturaB", x: g.x[2] + 0.2, y: g.par, s: g.sPar, label: "Lectura B", sub: resumen("B") },
      ]);
      rondasPrevias.current = 0;
    }
    if (enDebate && orb.has("lecA")) {
      // Se acercan conforme convergen
      const sim = debate?.rondas.at(-1)?.similitudCierre ?? foco.traza.divergencia.similitud;
      const gap = 0.05 + (1 - sim) * 0.26;
      orb.update("lecA", { x: g.x[2] - gap, active: true });
      orb.update("lecB", { x: g.x[2] + gap, active: true });
      const n = debate?.rondas.length ?? 0;
      if (n > rondasPrevias.current) {
        rondasPrevias.current = n;
        orb.poke(0.8, "lecA");
        orb.poke(0.8, "lecB");
        orb.poke(0.6, "critico");
      }
    }
    if (!enDebate && orb.has("lecA")) {
      const destino = foco.estado === E.ARBITRADO ? "critico" : "clasificador";
      orb.fuse(["lecA", "lecB"], destino);
    }
  }, [fase, foco, orb]);

  /* ---- 3. todo listo: los agentes se funden en una sola esfera ---- */
  useEffect(() => {
    if (fase !== "trabajo" || !terminado) return;
    orb.fuse(["lecA", "lecB", ...ORDEN], "core");
    orb.setPose({ x: 0, y: -0.06, s: 0.95 });
    orb.setMood("success");
    setFase("fusion");
  }, [fase, terminado, orb]);

  useEffect(() => {
    if (fase !== "fusion") return;
    const t = setTimeout(() => {
      orb.setPose(isMobile() ? { x: 0, y: -0.33, s: 0.45 } : { x: -0.3, y: 0, s: 0.8 });
      setFase("resultados");
    }, 1600);
    return () => clearTimeout(t);
  }, [fase, orb]);

  /* Al salir, la esfera vuelve a ser una */
  useEffect(() => () => {
    orb.fuse(["lecA", "lecB", ...ORDEN], "core");
    orb.update("core", { label: null, sub: null });
    orb.setMood("idle");
  }, [orb]);

  useEffect(() => {
    if (fase === "resultados" && lista) {
      orb.update("core", { label: "Análisis completo", sub: null });
      orb.setMood("idle");
    }
  }, [fase, lista, orb]);

  if (!lista) return null;

  return (
    <main className="relative z-10 min-h-screen">
      {(fase === "trabajo" || fase === "division") && foco && <Foco r={foco} i={indiceFoco} total={lista.length} />}
      {fase === "trabajo" && foco && <Lectura r={foco} />}
      {fase === "trabajo" && <Lote lista={lista} foco={foco} />}
      {fase === "fusion" && (
        <p className="mono sube fixed inset-x-0 bottom-[18vh] text-center text-[10px] text-[var(--bone-dim)]">Reuniendo a los agentes…</p>
      )}
      {fase === "resultados" && <Resultados lista={lista} ids={ids} />}
    </main>
  );
}

/* ---------------------------------------------------------------- */

function Foco({ r, i, total }) {
  // Requisitos largos bajan de tamaño para no invadir a los agentes
  const largo = r.texto.length > 110;
  return (
    <section key={r.id} className="pointer-events-none fixed inset-x-0 top-[12vh] z-10 px-6 text-center">
      <p className="mono sube text-[10px] text-[var(--bone-faint)]">
        Requisito {i + 1} de {total} · {r.id} · <span className="text-[var(--bone-dim)]">{INFO_ESTADO[r.estado].etiqueta}</span>
      </p>
      <p
        className={`serif sube mx-auto mt-3 line-clamp-3 max-w-4xl leading-tight ${largo ? "text-[clamp(18px,1.8vw,24px)]" : "text-[clamp(22px,2.4vw,34px)]"}`}
        style={{ "--i": 1 }}
      >
        «<TextoMarcado texto={r.texto} marcados={r.traza.extraccion?.marcados ?? []} />»
      </p>
    </section>
  );
}

/* Similitud entre las lecturas, entre el Crítico y el par A/B */
function Lectura({ r }) {
  const d = r.traza.divergencia;
  if (!d) return null;
  const debate = r.traza.debate;
  const ultima = debate?.rondas.at(-1);
  const sim = ultima?.similitudCierre ?? d.similitud;
  const arriba = sim >= d.umbral;
  const nota = ultima?.intervenciones.find((x) => x.postura === "moderador")?.argumento;
  const g = geo();
  const top = `calc(50% + ${((g.fila + g.par) / 2 + 0.06) * 100}vh)`;
  return (
    <div key={`${r.id}-${debate?.rondas.length ?? 0}`} className="pointer-events-none fixed z-10 w-[min(440px,90vw)] -translate-x-1/2 -translate-y-1/2 text-center" style={{ left: `calc(50% + ${g.x[2] * 100}vw)`, top }}>
      <p className="sube font-mono text-[28px] leading-none" style={{ color: arriba ? "#57f7a7" : "#ffc457" }}>
        {sim.toFixed(2)}
        <span className="ml-2 text-[13px] text-[var(--bone-faint)]">{arriba ? "≥" : "<"} {d.umbral.toFixed(2)}</span>
      </p>
      <p className="mono sube mt-1.5 text-[9.5px] text-[var(--bone-faint)]" style={{ "--i": 1 }}>
        {!debate && (arriba ? "similitud por arriba del umbral · sin debate" : "similitud por debajo del umbral · debate")}
        {debate && (ultima ? `similitud al cerrar la ronda ${ultima.numero}` : "similitud inicial · empieza el debate")}
      </p>
      {nota && <p className="sube mx-auto mt-2 max-w-sm text-[12px] leading-snug text-[var(--bone-dim)] italic" style={{ "--i": 2 }}>{nota}</p>}
    </div>
  );
}

/*
 * Progreso del lote: una marca por requisito, siempre en una sola línea por
 * muchos que sean. La lista completa se abre a demanda.
 */
function Lote({ lista, foco }) {
  const [abierta, setAbierta] = useState(false);
  const listos = lista.filter((r) => !estaEnProceso(r.estado)).length;
  return (
    <div className="fixed inset-x-0 bottom-[3vh] z-10 mx-auto flex max-w-3xl flex-col items-center gap-3 px-6">
      {abierta && (
        <ol className="sube max-h-[30vh] w-full overflow-y-auto rounded-2xl border border-[var(--line)] bg-[color-mix(in_oklab,var(--bg)_86%,transparent)] p-3 backdrop-blur-xl">
          {lista.map((r) => {
            const actual = r.id === foco?.id;
            const listo = !estaEnProceso(r.estado);
            const via = VIA[r.via];
            return (
              <li key={r.id} className={`flex items-center gap-4 py-1 text-[12.5px] ${actual ? "" : listo ? "opacity-60" : "opacity-35"}`}>
                <span className="mono w-16 shrink-0 text-[9.5px] text-[var(--bone-faint)]">{r.id}</span>
                <span className="min-w-0 flex-1 truncate">{r.texto}</span>
                <span className="mono flex w-32 shrink-0 items-center justify-end gap-2 text-[9.5px]">
                  {actual && <><span className="gira" />{INFO_ESTADO[r.estado].etiqueta}</>}
                  {listo && via && <><span className="punto" style={{ background: via.tono }} />{via.texto}</>}
                  {!listo && !actual && "en cola"}
                </span>
              </li>
            );
          })}
        </ol>
      )}
      <button onClick={() => setAbierta((x) => !x)} className="flex max-w-full flex-col items-center gap-2" title="Ver la lista de requisitos">
        <span className="flex max-w-full flex-wrap justify-center gap-1.5">
          {lista.map((r) => {
            const actual = r.id === foco?.id;
            const via = VIA[r.via];
            return (
              <span
                key={r.id}
                title={`${r.id} · ${r.texto}`}
                className={`h-1.5 rounded-full transition-all duration-500 ${actual ? "w-6" : "w-1.5"}`}
                style={{ background: actual ? "var(--c1)" : via ? via.tono : "rgba(239,233,222,.18)" }}
              />
            );
          })}
        </span>
        <span className="mono text-[9.5px] text-[var(--bone-faint)] hover:text-[var(--bone)]">
          {listos} de {lista.length} listos · {abierta ? "ocultar lista" : "ver lista"}
        </span>
      </button>
    </div>
  );
}

function Resultados({ lista, ids }) {
  const navigate = useNavigate();
  const cuenta = (v) => lista.filter((r) => r.via === v).length;
  const q = ids.join(",");
  return (
    <section className="mx-auto flex min-h-screen max-w-2xl flex-col gap-5 px-6 pt-[36vh] pb-14 md:mr-[7vw] md:pt-28">
      <p className="mono sube text-[10px] text-[var(--bone-faint)]">Análisis completo</p>
      <h1 className="serif sube text-[clamp(44px,4.6vw,72px)] leading-[.95]" style={{ "--i": 1 }}>
        Listo. <em>{lista.length}</em> {lista.length === 1 ? "requisito" : "requisitos"}.
      </h1>
      <p className="sube text-sm text-[var(--bone-dim)]" style={{ "--i": 2 }}>
        {cuenta(V.DIRECTO)} sin debate · {cuenta(V.CONSENSO)} por consenso · {cuenta(V.ARBITRAJE)} por arbitraje del Crítico.
      </p>

      {/* Lo siguiente, siempre a la vista aunque la lista sea larga */}
      <div className="sube sticky top-20 z-10 -mx-3 flex flex-wrap items-center gap-3 rounded-full px-3 py-2 backdrop-blur-xl" style={{ "--i": 3 }}>
        <button className="pill" onClick={() => navigate(`/lel/generar?ids=${q}`)}>Generar LEL</button>
        <button className="pill ghost" onClick={() => navigate(`/big-picture?ids=${q}`)}>Big Picture</button>
        <button className="pill ghost" onClick={() => navigate(`/big-picture?ids=${q}&vista=modelo`)}>Modelo UML</button>
        {lista[0]?.proyectoId && (
          <Link to={`/proyectos/${lista[0].proyectoId}`} className="mono px-2 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]">Ver el proyecto</Link>
        )}
      </div>

      <p className="mono text-[9.5px] text-[var(--bone-faint)]">Toca un requisito para ver cómo lo decidieron los agentes</p>
      <ol className="border-t border-[var(--line)]">
        {lista.map((r, i) => {
          const via = VIA[r.via];
          return (
            <li key={r.id} className="sube" style={{ "--i": 4 + Math.min(i, 8) }}>
              <Link to={`/requisitos/${r.id}`} className="group flex items-baseline gap-4 border-b border-[var(--line)] py-3 transition-colors hover:bg-white/[0.025]">
                <span className="mono w-16 shrink-0 text-[9.5px] text-[var(--bone-faint)]">{r.id}</span>
                <span className="min-w-0 flex-1 text-[15px] leading-relaxed">
                  <TextoMarcado texto={r.texto} marcados={r.traza.extraccion?.marcados ?? []} />
                </span>
                <span className="mono flex w-28 shrink-0 items-center justify-end gap-2 text-[9.5px] text-[var(--bone-dim)]">
                  {via && <span className="punto" style={{ background: via.tono }} />}
                  {via?.texto ?? INFO_ESTADO[r.estado].etiqueta}
                  {r.similitud != null && <span className="text-[var(--bone-faint)]">{r.similitud.toFixed(2)}</span>}
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
      <Link to="/inicio" className="mono self-start text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]">Analizar otro documento</Link>
    </section>
  );
}

export { VIA };
