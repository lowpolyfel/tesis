import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useOrb } from "../components/orb/useOrb";
import { isMobile } from "../components/orb/poses";
import { listarProyectos, obtenerFlujo } from "../services/api";

/*
 * Flujo de conocimiento continuo, adaptado del modelo en espiral de KMoS-SSA /
 * SysM2 (Jiménez-Galina, Maldonado-Macías y Olmos-Sánchez, 2025).
 *   - la esfera es el centro: de ella parte cada ciclo
 *   - cada anillo es un ciclo (un lote analizado); el más externo es el más reciente
 *   - cada sector es una fase, con el agente que la realiza
 *   - un punto por fase en cada anillo: su tamaño es cuánto trabajo hubo
 *   - el ciclo elegido muestra sus números; los demás solo sus puntos
 * Así la figura no se satura por muchos ciclos que haya.
 */

const FASES = [
  {
    id: "elicitacion", nombre: "Elicitación", rol: "Extractor", tono: "#41efff", desde: -90,
    peso: (m) => m.requisitos + m.marcados,
    cifra: (m) => m.requisitos, unidad: "req",
    chip: (m) => `${m.requisitos} req · ${m.marcados} marcas`,
    detalle: (m) => `${m.requisitos} requisitos, ${m.terminos} términos extraídos, ${m.marcados} ambiguos`,
  },
  {
    id: "estructuracion", nombre: "Estructuración", rol: "Clasificador · similitud", tono: "#a99bff", desde: -18,
    peso: (m) => m.interpretaciones,
    cifra: (m) => m.interpretaciones, unidad: "lect",
    chip: (m) => `${m.interpretaciones} lecturas`,
    detalle: (m) => `${m.interpretaciones} interpretaciones, ${m.similitudes} comparaciones, ${m.directos} sin debate`,
  },
  {
    id: "enriquecimiento", nombre: "Enriquecimiento", rol: "Crítico · lecturas A y B", tono: "#ffc457", desde: 54,
    peso: (m) => m.debates + m.rondas,
    cifra: (m) => m.rondas, unidad: "R",
    chip: (m) => `${m.debates} debates · ${m.rondas} R`,
    detalle: (m) => `${m.debates} debates, ${m.rondas} rondas, ${m.consensos} consensos, ${m.arbitrajes} arbitrajes`,
  },
  {
    id: "generacion", nombre: "Generación", rol: "Modelador", tono: "#57f7a7", desde: 126,
    peso: (m) => m.lel,
    cifra: (m) => m.lel, unidad: "LEL",
    chip: (m) => `${m.lel} LEL`,
    detalle: (m) => `${m.artefactos} artefactos (LEL, metas y Big Picture) de ${m.lel} requisitos`,
  },
  {
    id: "validacion", nombre: "Validación", rol: "Analista humano", tono: "#efe9de", desde: 198,
    peso: (m) => m.validados + m.rechazados + m.formalizados,
    cifra: (m) => m.validados, unidad: "✓",
    chip: (m) => `${m.validados} ✓ · ${m.rechazados} ✗`,
    detalle: (m) => `${m.validados} validados, ${m.rechazados} rechazados, ${m.formalizados} formalizados, ${m.reprocesos} reprocesos`,
  },
];

/* Pregunta de decisión al cruzar hacia cada fase, y el nombre de esa frontera */
const FRONTERAS = {
  elicitacion: { pregunta: "¿Suficiente?", nombre: "Retroalimentación: nuevo ciclo" },
  estructuracion: { pregunta: "¿Ambiguo?", nombre: "Verificación de términos" },
  enriquecimiento: { pregunta: "¿Sim ≥ umbral?", nombre: "Similitud contra umbral" },
  generacion: { pregunta: "¿Consenso?", nombre: "Discusión y arbitraje" },
  validacion: { pregunta: "¿Válido?", nombre: "Verificación y reflexión" },
};

const MAX_ANILLOS = 7;
const rad = (g) => (g * Math.PI) / 180;

/* Caja del área de la espiral en coordenadas de pantalla */
function useCaja(ref) {
  const [caja, setCaja] = useState(null);
  useLayoutEffect(() => {
    const medir = () => {
      const r = ref.current?.getBoundingClientRect();
      if (r) setCaja({ x: r.left, y: r.top, w: r.width, h: r.height });
    };
    medir();
    const ro = new ResizeObserver(medir);
    ro.observe(ref.current);
    addEventListener("resize", medir);
    return () => { ro.disconnect(); removeEventListener("resize", medir); };
  }, [ref]);
  return caja;
}

export default function Flujo() {
  const orb = useOrb();
  const [params, setParams] = useSearchParams();
  const proyecto = params.get("proyecto") ?? "";
  const [datos, setDatos] = useState(null);
  const [proyectos, setProyectos] = useState([]);
  const [elegido, setElegido] = useState(null); // número de ciclo
  const area = useRef(null);
  const caja = useCaja(area);
  const movil = isMobile();

  useEffect(() => { listarProyectos().then(setProyectos); }, []);
  useEffect(() => {
    let activo = true;
    setElegido(null);
    const cargar = () => obtenerFlujo(proyecto || undefined).then((d) => activo && setDatos(d));
    cargar();
    const t = setInterval(cargar, 4000); // sigue vivo mientras los agentes trabajan
    return () => { activo = false; clearInterval(t); };
  }, [proyecto]);

  // La esfera se coloca exactamente en el centro de la espiral
  useEffect(() => {
    if (!caja) return;
    const cx = caja.x + caja.w / 2, cy = caja.y + caja.h / 2;
    orb.setPose({ x: cx / innerWidth - 0.5, y: cy / innerHeight - 0.5, s: movil ? 0.13 : 0.22 });
    orb.setMood("idle");
    orb.update("core", { label: null, sub: null });
  }, [orb, caja, movil]);

  const ciclos = datos?.ciclos.slice(-MAX_ANILLOS) ?? [];
  const actual = ciclos.find((c) => c.ciclo === elegido) ?? ciclos.at(-1);
  const nombreProyecto = proyectos.find((p) => p.id === proyecto)?.nombre ?? "Todos los proyectos";
  const maxPeso = Math.max(1, ...ciclos.flatMap((c) => FASES.map((f) => f.peso(c[f.id]))));

  return (
    <main className="relative z-10 flex min-h-screen flex-col gap-6 px-5 pt-24 pb-8 md:h-screen md:flex-row md:overflow-hidden md:px-10">
      {/* --- Espiral --- */}
      <div ref={area} className="relative h-[62vh] min-h-[360px] md:h-auto md:min-h-0 md:flex-1">
        {caja && datos && (
          <Espiral
            w={caja.w}
            h={caja.h}
            ciclos={ciclos}
            actual={actual}
            maxPeso={maxPeso}
            movil={movil}
            onElegir={(c) => { setElegido(c); orb.poke(0.5); }}
          />
        )}
      </div>

      {/* --- Panel --- */}
      <aside className="flex w-full shrink-0 flex-col gap-5 md:w-[340px] md:overflow-y-auto md:pr-1">
        <div>
          <p className="mono text-[10px] text-[var(--bone-faint)]">Flujo de conocimiento continuo</p>
          <h1 className="serif mt-2 text-[38px] leading-[.95]">Cada <em>ciclo</em> aprende del anterior.</h1>
        </div>
        <select
          value={proyecto}
          onChange={(e) => setParams(e.target.value ? { proyecto: e.target.value } : {}, { replace: true })}
          className="w-fit rounded-full border border-[var(--line)] bg-transparent px-3 py-1.5 text-[12px] text-[var(--bone)] outline-none"
        >
          <option value="" className="bg-[#16130f]">Todos los proyectos</option>
          {proyectos.map((p) => <option key={p.id} value={p.id} className="bg-[#16130f]">{p.nombre}</option>)}
        </select>

        {datos && (
          <>
            <div>
              <p className="font-mono text-[44px] leading-none">{datos.interacciones}</p>
              <p className="mono mt-1.5 text-[9.5px] text-[var(--bone-faint)]">interacciones · {datos.ciclos.length} {datos.ciclos.length === 1 ? "ciclo" : "ciclos"} · {nombreProyecto}</p>
            </div>

            <dl className="grid grid-cols-[auto_auto_1fr] items-baseline gap-x-3 gap-y-1.5 text-sm">
              {[
                ["Extractor", "#41efff", datos.agentes.extractor, "extracciones"],
                ["Clasificador", "#a99bff", datos.agentes.clasificador, "lecturas y defensas"],
                ["Similitud", "#8f8bff", datos.total.estructuracion.similitudes, "comparaciones"],
                ["Crítico", "#ffc457", datos.agentes.critico, "rondas y arbitrajes"],
                ["Modelador", "#57f7a7", datos.agentes.modelador, "artefactos"],
                ["Analista", "#efe9de", datos.agentes.humano, "decisiones"],
              ].map(([k, tono, v, d]) => (
                <div key={k} className="contents">
                  <dt className="flex items-center gap-2"><span className="punto" style={{ background: tono }} />{k}</dt>
                  <dd className="text-right font-mono">{v}</dd>
                  <span className="text-[11px] text-[var(--bone-faint)]">{d}</span>
                </div>
              ))}
            </dl>

            {ciclos.length > 0 && (
              <section className="rounded-2xl border border-[var(--line)] p-4">
                <div className="mb-3 flex flex-wrap items-center gap-1.5">
                  <span className="mono mr-1 text-[9.5px] text-[var(--bone-faint)]">Ciclo</span>
                  {ciclos.map((c) => (
                    <button
                      key={c.ciclo}
                      onClick={() => setElegido(c.ciclo)}
                      className={`mono rounded-full px-2.5 py-1 text-[10px] ${c.ciclo === actual.ciclo ? "bg-[var(--bone)] text-[#16130f]" : "text-[var(--bone-dim)] ring-1 ring-[var(--line)] hover:text-[var(--bone)]"}`}
                    >
                      C{c.ciclo}
                    </button>
                  ))}
                </div>
                <ul className="space-y-2 text-[12.5px] leading-snug">
                  {FASES.map((f) => (
                    <li key={f.id}>
                      <span style={{ color: f.tono }}>{f.nombre}</span>
                      <span className="text-[var(--bone-dim)]"> — {f.detalle(actual[f.id])}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="space-y-1.5 text-[11.5px] text-[var(--bone-faint)]">
              <p className="mono text-[9.5px]">Fronteras y decisiones</p>
              {FASES.map((f) => (
                <p key={f.id}>
                  <span className="text-[#d9d3ff]">{FRONTERAS[f.id].pregunta}</span> {FRONTERAS[f.id].nombre} → {f.nombre}
                </p>
              ))}
            </section>

            <div className="flex flex-wrap gap-2">
              <Link to={proyecto ? `/inicio?proyecto=${proyecto}` : "/inicio"} className="pill">Nuevo ciclo</Link>
              {proyecto && <Link to={`/proyectos/${proyecto}`} className="pill ghost">Proyecto</Link>}
            </div>
            <p className="text-[10.5px] leading-snug text-[var(--bone-faint)]">
              Adaptado del modelo en espiral de KMoS-SSA / SysM2. Jiménez-Galina, A. M., Maldonado-Macías, A. A. y Olmos-Sánchez, K. M. (2025).
            </p>
          </>
        )}
      </aside>
    </main>
  );
}

/* ---------------------------------------------------------------- */

function Espiral({ w, h, ciclos, actual, maxPeso, movil, onElegir }) {
  const cx = w / 2, cy = h / 2;
  // Márgenes reservados para rótulos: nada se sale ni toca el panel
  const margenX = movil ? 70 : 175, margenY = movil ? 52 : 74;
  const rMax = Math.max(80, Math.min(w / 2 - margenX, (h / 2 - margenY) / 0.62));
  const r0 = movil ? 34 : 54;
  const n = Math.max(1, ciclos.length);
  const paso = (rMax - r0) / n;
  const radio = (i) => r0 + paso * (i + 1);
  const ry = (rx) => rx * 0.62;
  const punto = (rx, g) => [cx + rx * Math.cos(rad(g)), cy + ry(rx) * Math.sin(rad(g))];

  return (
    <svg className="absolute inset-0 h-full w-full" viewBox={`0 0 ${w} ${h}`} aria-label="Espiral del flujo de conocimiento continuo">
      <defs>
        <marker id="flujoFlecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="rgba(239,233,222,.45)" />
        </marker>
      </defs>

      {/* Fronteras entre fases */}
      {FASES.map((f) => {
        const [x1, y1] = punto(r0 * 0.7, f.desde);
        const [x2, y2] = punto(rMax + 16, f.desde);
        return <line key={f.id} x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(239,233,222,.22)" strokeDasharray="5 6" markerEnd="url(#flujoFlecha)" />;
      })}

      {/* Anillos = ciclos */}
      {ciclos.map((c, i) => {
        const rx = radio(i);
        const sel = c.ciclo === actual?.ciclo;
        return (
          <g key={c.ciclo} className="cursor-pointer" onClick={() => onElegir(c.ciclo)}>
            <ellipse cx={cx} cy={cy} rx={rx} ry={ry(rx)} fill="none" stroke="transparent" strokeWidth="14" />
            <ellipse cx={cx} cy={cy} rx={rx} ry={ry(rx)} fill="none" stroke={sel ? "rgba(239,233,222,.5)" : "rgba(239,233,222,.13)"} strokeWidth={sel ? 1.8 : 1.1} />
            <ellipse
              cx={cx} cy={cy} rx={rx} ry={ry(rx)} fill="none" stroke="var(--c1)" strokeOpacity={sel ? 0.8 : 0.25} strokeWidth="1.2"
              strokeDasharray="2 16" className="flujo-anillo" style={{ animationDuration: `${16 + i * 5}s` }}
            />
            <text x={punto(rx, -80)[0] + 4} y={punto(rx, -80)[1] - 3} fontSize="9.5" fill={sel ? "#efe9de" : "rgba(239,233,222,.4)"} style={{ fontFamily: "var(--mono)" }}>
              C{c.ciclo}
            </text>
          </g>
        );
      })}

      {/* Actividad: un punto por fase en cada anillo */}
      {ciclos.map((c, i) =>
        FASES.map((f) => {
          const [x, y] = punto(radio(i), f.desde + 36);
          const peso = f.peso(c[f.id]);
          const r = peso ? 3 + Math.sqrt(peso / maxPeso) * (movil ? 6 : 9) : 2;
          const sel = c.ciclo === actual?.ciclo;
          return (
            <circle
              key={`${c.ciclo}-${f.id}`}
              cx={x} cy={y} r={r}
              fill={peso ? f.tono : "transparent"}
              fillOpacity={sel ? 0.95 : 0.35}
              stroke={f.tono}
              strokeOpacity={peso ? 0 : 0.5}
              className="cursor-pointer"
              onClick={() => onElegir(c.ciclo)}
            >
              <title>{`C${c.ciclo} · ${f.nombre}: ${f.detalle(c[f.id])}`}</title>
            </circle>
          );
        })
      )}

      {/* Cifra del ciclo elegido junto a cada punto, hacia el centro (el detalle está en el panel) */}
      {actual && FASES.map((f) => {
        const i = ciclos.indexOf(actual);
        const medio = f.desde + 36;
        const [x, y] = punto(radio(i) - (movil ? 16 : 24), medio);
        return (
          <text key={f.id} x={x} y={y + 3.5} textAnchor="middle" fontSize={movil ? 9 : 11} fill={f.tono} className="pointer-events-none" style={{ fontFamily: "var(--mono)" }}>
            {f.cifra(actual[f.id])} {f.unidad}
          </text>
        );
      })}

      {/* Nombre de cada fase, fuera del anillo externo */}
      {FASES.map((f) => {
        const medio = f.desde + 36;
        const cos = Math.cos(rad(medio)), sin = Math.sin(rad(medio));
        const [x, y] = punto(rMax + (movil ? 14 : 40), medio);
        const anchor = cos < -0.3 ? "end" : cos > 0.3 ? "start" : "middle";
        const dy = sin > 0.5 ? 16 : sin < -0.5 ? -8 : 4;
        return (
          <g key={f.id} transform={`translate(${x} ${y + dy})`}>
            <text textAnchor={anchor} fontSize={movil ? 12 : 16} fill={f.tono} style={{ fontFamily: "var(--serif)" }}>{f.nombre}</text>
            {!movil && <text textAnchor={anchor} y="15" fontSize="10" fill="rgba(239,233,222,.45)">{f.rol}</text>}
          </g>
        );
      })}

      {/* Pregunta de decisión en cada frontera, sobre el anillo externo */}
      {!movil && FASES.map((f) => {
        const [x, y] = punto(rMax + 16, f.desde);
        const pregunta = FRONTERAS[f.id].pregunta;
        const ancho = pregunta.length * 5.4 + 26;
        return (
          <g key={f.id} transform={`translate(${x} ${y})`}>
            <title>{FRONTERAS[f.id].nombre}</title>
            <polygon points={`0,-12 ${ancho / 2},0 0,12 ${-ancho / 2},0`} fill="#14111f" stroke="rgba(169,155,255,.6)" />
            <text textAnchor="middle" y="3.2" fontSize="9" fill="#d9d3ff">{pregunta}</text>
          </g>
        );
      })}
    </svg>
  );
}
