import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { useOrb } from "../components/orb/useOrb";
import { isMobile } from "../components/orb/poses";
import { flujoDeProyecto } from "../services/backend";
import ElegirProyecto, { useProyectoElegido } from "../components/ElegirProyecto";
import { nodo } from "../constants/agentes";

/*
 * Flujo de conocimiento continuo, adaptado del modelo en espiral de KMoS-SSA /
 * SysM2 (Jiménez-Galina, Maldonado-Macías y Olmos-Sánchez, 2025).
 *   - la esfera es el centro: de ella parte cada ciclo
 *   - cada anillo es un ciclo (un lote cargado al proyecto); el más externo es el más reciente
 *   - cada sector es una de las cinco fases (CONTEXTO §5), con los agentes que la realizan
 *   - un punto por fase en cada anillo: su tamaño es cuántos mensajes produjo esa fase
 *   - el ciclo elegido muestra sus números; los demás solo sus puntos
 * Las cifras vienen de GET /proyectos/{id}/flujo (app/analisis/proyecto.py):
 * mensajes sin repetidos y requisitos que pasaron por cada estado. El flujo
 * cuenta mensajes por tipo: el Crítico emite un mensaje `objecion` por término
 * y ronda aunque no objete nada, así que esa cifra son evaluaciones del
 * Crítico, no objeciones.
 */

const tipo = (c, t) => c.mensajes_por_tipo?.[t] ?? 0;
const fase = (c, n) => c.fases.find((f) => f.fase === n) ?? { mensajes: 0, requisitos_que_pasaron: 0 };

const FASES = [
  {
    id: "enriquecimiento", n: 1, nombre: "Enriquecimiento", rol: "Extractor · filtros", tono: "#41efff", desde: -90,
    cifra: (c) => c.requisitos, unidad: "req",
    detalle: (c) => `${c.requisitos} requisitos; ${fase(c, 1).requisitos_que_pasaron} extraídos; ${tipo(c, "extraccion")} extracciones y ${tipo(c, "filtrado")} filtrados (vaguedad, regionalismos, alcance, anáfora, LEL)`,
  },
  {
    id: "generacion", n: 2, nombre: "Generación", rol: "Clasificador", tono: "#a99bff", desde: -18,
    cifra: (c) => fase(c, 2).requisitos_que_pasaron, unidad: "req",
    detalle: (c) => `${fase(c, 2).requisitos_que_pasaron} requisitos pasaron por el Clasificador (${tipo(c, "interpretaciones")} mensajes; incluye los que no tuvieron términos ambiguos)`,
  },
  {
    id: "discusion", n: 3, nombre: "Discusión", rol: "Similitud · Crítico · Clasificador", tono: "#ffc457", desde: 54,
    cifra: (c) => c.rondas_totales, unidad: "R",
    detalle: (c) => `${c.directos} aceptados directo, ${c.debates} con debate, ${c.rondas_totales} rondas, ${tipo(c, "objecion")} evaluaciones del Crítico, ${c.consensos} consensos, ${c.arbitrajes} arbitrajes`,
  },
  {
    id: "validacion", n: 4, nombre: "Validación", rol: "Humano · especialista del dominio", tono: "#efe9de", desde: 126,
    cifra: (c) => c.validados, unidad: "✓",
    detalle: (c) => `${fase(c, 4).requisitos_que_pasaron} llegaron a validación; ${c.validados} aprobados, ${c.rechazados} rechazados`,
  },
  {
    id: "cierre", n: 5, nombre: "Cierre", rol: "Modelador", tono: "#57f7a7", desde: 198,
    cifra: (c) => c.lel_nuevas, unidad: "LEL",
    detalle: (c) => `${c.formalizados} formalizados; ${c.lel_nuevas} entradas nuevas del LEL que el ciclo siguiente ya no debate`,
  },
];
for (const f of FASES) f.peso = (c) => fase(c, f.n).mensajes;

/* Pregunta de decisión al cruzar hacia cada fase, y el nombre de esa frontera */
const FRONTERAS = {
  enriquecimiento: { pregunta: "¿Suficiente?", nombre: "Retroalimentación: nuevo ciclo con el LEL enriquecido" },
  generacion: { pregunta: "¿Ambiguo?", nombre: "Verificación de términos (unívocos no se debaten)" },
  discusion: { pregunta: "¿Sim ≥ umbral?", nombre: "Similitud contra umbral" },
  validacion: { pregunta: "¿Resuelto?", nombre: "Aceptación directa, consenso o arbitraje" },
  cierre: { pregunta: "¿Válido?", nombre: "Verificación y reflexión" },
};

const MAX_ANILLOS = 7;
const rad = (g) => (g * Math.PI) / 180;
const SONDEO_MS = 4000;
const ORDEN_EMISORES = ["extractor", "filtros", "clasificador", "divergencia", "critico", "humano", "modelador"];

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
  const { proyectoId, proyecto, proyectos, elegir } = useProyectoElegido();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const [elegido, setElegido] = useState(null); // número de ciclo
  const area = useRef(null);
  const caja = useCaja(area);
  const movil = isMobile();

  useEffect(() => {
    if (!proyectoId) return undefined;
    let activo = true;
    setElegido(null);
    setDatos(null);
    const cargar = () => flujoDeProyecto(proyectoId)
      .then((d) => { if (activo) { setDatos(d); setError(null); } })
      .catch((e) => activo && setError(e));
    cargar();
    const t = setInterval(cargar, SONDEO_MS); // sigue vivo mientras los agentes trabajan
    return () => { activo = false; clearInterval(t); };
  }, [proyectoId]);

  // La esfera se coloca exactamente en el centro de la espiral; en móvil la
  // página se desplaza y la esfera (fija en la ventana) la sigue
  useEffect(() => {
    if (!caja) return undefined;
    const colocar = () => {
      const r = area.current?.getBoundingClientRect();
      if (r) orb.setPose({ x: (r.left + r.width / 2) / innerWidth - 0.5, y: (r.top + r.height / 2) / innerHeight - 0.5, s: movil ? 0.13 : 0.22 });
    };
    colocar();
    addEventListener("scroll", colocar, { passive: true });
    return () => removeEventListener("scroll", colocar);
  }, [orb, caja, movil]);
  useEffect(() => {
    orb.setMood("idle");
    orb.update("core", { label: null, sub: null });
  }, [orb]);

  const ciclos = datos?.ciclos.slice(-MAX_ANILLOS) ?? [];
  const actual = ciclos.find((c) => c.ciclo === elegido) ?? ciclos.at(-1);
  const maxPeso = Math.max(1, ...ciclos.flatMap((c) => FASES.map((f) => f.peso(c))));
  const total = datos?.total;
  const interacciones = total ? Object.values(total.mensajes_por_agente).reduce((a, b) => a + b, 0) : 0;

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
        <ElegirProyecto proyectoId={proyectoId} proyectos={proyectos} onCambio={elegir} />
        {error && <p className="text-sm text-[var(--danger)]">{error.message}</p>}

        {total && total.requisitos === 0 && (
          <p className="text-sm text-[var(--bone-dim)]">Este proyecto aún no tiene requisitos. Cada carga de requisitos abre un ciclo nuevo.</p>
        )}

        {total && total.requisitos > 0 && (
          <>
            <div>
              <p className="font-mono text-[44px] leading-none">{interacciones}</p>
              <p className="mono mt-1.5 text-[9.5px] text-[var(--bone-faint)]">
                mensajes · {datos.ciclos.length} {datos.ciclos.length === 1 ? "ciclo" : "ciclos"} · {total.requisitos} requisitos · {proyecto?.nombre ?? proyectoId}
              </p>
            </div>

            <dl className="grid grid-cols-[auto_auto_1fr] items-baseline gap-x-3 gap-y-1.5 text-sm">
              {ORDEN_EMISORES.map((k) => (
                <div key={k} className="contents">
                  <dt className="flex items-center gap-2"><span className="punto" style={{ background: nodo(k).tono }} />{nodo(k).nombre}</dt>
                  <dd className="text-right font-mono">{total.mensajes_por_agente[k] ?? 0}</dd>
                  <span className="truncate text-[11px] text-[var(--bone-faint)]" title={nodo(k).rol}>{nodo(k).rol}</span>
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
                      <span style={{ color: f.tono }}>{f.n}. {f.nombre}</span>
                      <span className="text-[var(--bone-dim)]"> — {f.detalle(actual)}</span>
                    </li>
                  ))}
                </ul>
                {actual.duracion_s != null && (
                  <p className="mono mt-3 text-[9.5px] text-[var(--bone-faint)]">duración {formatoDuracion(actual.duracion_s)} (incluye la espera de la validación humana)</p>
                )}
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
          </>
        )}

        {proyectoId && (
          <div className="flex flex-wrap gap-2">
            {/* un proyecto de evaluación solo lo llena la evaluación del corpus */}
            {proyecto?.tipo !== "evaluacion" && <Link to={`/proyectos/${proyectoId}/analizar`} className="pill">Nuevo ciclo</Link>}
            <Link to={`/proyectos/${proyectoId}`} className="pill ghost">Proyecto</Link>
          </div>
        )}
        <p className="text-[10.5px] leading-snug text-[var(--bone-faint)]">
          Adaptado del modelo en espiral de KMoS-SSA / SysM2. Jiménez-Galina, A. M., Maldonado-Macías, A. A. y Olmos-Sánchez, K. M. (2025).
        </p>
      </aside>
    </main>
  );
}

function formatoDuracion(s) {
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${Math.round(s / 60)} min`;
  return `${(s / 3600).toFixed(1)} h`;
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
          const peso = f.peso(c);
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
              <title>{`C${c.ciclo} · ${f.nombre}: ${f.detalle(c)}`}</title>
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
            {f.cifra(actual)} {f.unidad}
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
