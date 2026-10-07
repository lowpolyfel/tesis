import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useOrb } from "../components/orb/useOrb";
import { isMobile } from "../components/orb/poses";
import { flujoDeProyecto } from "../services/backend";
import ElegirProyecto, { useProyectoElegido } from "../components/ElegirProyecto";
import { nodo } from "../constants/agentes";
import { Plegable } from "../components/ui";

/*
 * Flujo de conocimiento continuo, adaptado del modelo en espiral de KMoS-SSA /
 * SysM2 (Jiménez-Galina, Maldonado-Macías y Olmos-Sánchez, 2025).
 *   - una esfera al centro: de ella parte cada ciclo (la esfera de la app se
 *     queda en el margen, como en las demás secciones)
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

/* Ancho de la ventana bajo el que la espiral usa su lienzo compacto */
function useMovil() {
  const [movil, setMovil] = useState(isMobile());
  useEffect(() => {
    const f = () => setMovil(isMobile());
    addEventListener("resize", f);
    return () => removeEventListener("resize", f);
  }, []);
  return movil;
}

export default function Flujo() {
  const orb = useOrb();
  const { proyectoId, proyecto, proyectos, elegir } = useProyectoElegido();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const [elegido, setElegido] = useState(null); // número de ciclo
  const movil = useMovil();

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

  const ciclos = datos?.ciclos.slice(-MAX_ANILLOS) ?? [];
  const actual = ciclos.find((c) => c.ciclo === elegido) ?? ciclos.at(-1);
  const maxPeso = Math.max(1, ...ciclos.flatMap((c) => FASES.map((f) => f.peso(c))));
  const total = datos?.total;
  const interacciones = total ? Object.values(total.mensajes_por_agente).reduce((a, b) => a + b, 0) : 0;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end gap-x-6 gap-y-4">
        <div className="min-w-0 flex-1">
          <p className="etiqueta mb-2">Flujo KMoS-SSA</p>
          <h1 className="serif">Cada <em>ciclo</em> aprende del anterior.</h1>
        </div>
        <ElegirProyecto proyectoId={proyectoId} proyectos={proyectos} onCambio={elegir} />
      </header>
      {error && <p className="text-sm text-[var(--danger)]">{error.message}</p>}
      {proyectoId && !datos && !error && <p className="mono text-[10.5px] text-[var(--bone-dim)]"><span className="gira" /> Cargando el flujo…</p>}
      {total && total.requisitos === 0 && (
        <p className="tarjeta px-5 py-4 text-[14.5px] text-[var(--bone-dim)]">Este proyecto aún no tiene requisitos. Cada carga de requisitos abre un ciclo nuevo.</p>
      )}

      {total && total.requisitos > 0 && (
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section className="tarjeta overflow-hidden p-2 sm:p-4">
            <Espiral
              ciclos={ciclos}
              actual={actual}
              maxPeso={maxPeso}
              movil={movil}
              onElegir={(c) => { setElegido(c); orb.poke(0.5); }}
            />
            <p className="px-2 pb-1 text-center text-[12px] text-[var(--bone-faint)]">
              Cada anillo es un ciclo (afuera, el más reciente); cada punto, los mensajes de una fase. Toca un anillo para ver su ciclo.
            </p>
          </section>

          <aside className="space-y-5">
            <div>
              <p className="font-mono text-[40px] leading-none">{interacciones}</p>
              <p className="mono mt-1.5 text-[9.5px] text-[var(--bone-faint)]">
                mensajes · {datos.ciclos.length} {datos.ciclos.length === 1 ? "ciclo" : "ciclos"} · {total.requisitos} requisitos
              </p>
            </div>

            {ciclos.length > 0 && (
              <section className="tarjeta p-4">
                <div className="mb-3 flex flex-wrap items-center gap-1.5">
                  <span className="etiqueta mr-1">Ciclo</span>
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
                <ul className="space-y-2 text-[13px] leading-snug">
                  {FASES.map((f) => (
                    <li key={f.id}>
                      <span style={{ color: f.tono }}>{f.n}. {f.nombre}</span>
                      <span className="text-[var(--bone-dim)]"> — {f.detalle(actual)}</span>
                    </li>
                  ))}
                </ul>
                {actual.duracion_s != null && (
                  <p className="mono mt-3 text-[9.5px] text-[var(--bone-faint)]">duración {formatoDuracion(actual.duracion_s)}</p>
                )}
              </section>
            )}

            <Plegable titulo="Mensajes por agente">
              <dl className="grid grid-cols-[auto_auto] items-baseline gap-x-4 gap-y-1.5 text-[13.5px]">
                {ORDEN_EMISORES.map((k) => (
                  <div key={k} className="contents">
                    <dt className="flex items-center gap-2" title={nodo(k).rol}><span className="punto" style={{ background: nodo(k).tono }} />{nodo(k).nombre}</dt>
                    <dd className="text-right font-mono">{total.mensajes_por_agente[k] ?? 0}</dd>
                  </div>
                ))}
              </dl>
            </Plegable>

            <Plegable titulo="Fronteras y decisiones">
              <ul className="space-y-1.5 text-[12.5px] text-[var(--bone-dim)]">
                {FASES.map((f) => (
                  <li key={f.id}><span className="text-[#d9d3ff]">{FRONTERAS[f.id].pregunta}</span> {FRONTERAS[f.id].nombre} → {f.nombre}</li>
                ))}
              </ul>
            </Plegable>

            <div className="flex flex-wrap gap-2">
              {/* un proyecto de evaluación solo lo llena la evaluación del corpus */}
              {proyecto?.tipo !== "evaluacion" && <Link to={`/proyectos/${proyectoId}/analizar`} className="pill sm">Nuevo ciclo</Link>}
              <Link to={`/proyectos/${proyectoId}`} className="pill ghost sm">Proyecto</Link>
            </div>
            <p className="text-[11px] leading-snug text-[var(--bone-faint)]">
              Adaptado del modelo en espiral de KMoS-SSA / SysM2. Jiménez-Galina, A. M., Maldonado-Macías, A. A. y Olmos-Sánchez, K. M. (2025).
            </p>
          </aside>
        </div>
      )}
    </div>
  );
}

function formatoDuracion(s) {
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${Math.round(s / 60)} min`;
  return `${(s / 3600).toFixed(1)} h`;
}

/* ---------------------------------------------------------------- */

/*
 * La espiral en un lienzo de proporciones fijas (viewBox): se escala con su
 * tarjeta sin deformarse ni cortar rótulos. Los rótulos de las fases (nombre y
 * cifra del ciclo elegido) van fuera del anillo externo; las preguntas de cada
 * frontera, sobre el anillo externo. Al centro, la esfera: de ella parte cada ciclo.
 */
const LIENZO = {
  amplio: { w: 760, h: 420, rMax: 225, r0: 48, achatado: 0.62, rotulo: 34, letra: 17, cifra: 12, preguntas: true },
  compacto: { w: 420, h: 340, rMax: 128, r0: 28, achatado: 0.76, rotulo: 18, letra: 14, cifra: 11, preguntas: false },
};

function Espiral({ ciclos, actual, maxPeso, movil, onElegir }) {
  const L = movil ? LIENZO.compacto : LIENZO.amplio;
  const cx = L.w / 2, cy = L.h / 2;
  const n = Math.max(1, ciclos.length);
  const paso = (L.rMax - L.r0) / n;
  const radio = (i) => L.r0 + paso * (i + 1);
  const ry = (rx) => rx * L.achatado;
  const punto = (rx, g) => [cx + rx * Math.cos(rad(g)), cy + ry(rx) * Math.sin(rad(g))];
  const iActual = ciclos.indexOf(actual);

  return (
    <svg className="block h-auto w-full" viewBox={`0 0 ${L.w} ${L.h}`} role="img" aria-label="Espiral del flujo de conocimiento continuo">
      <defs>
        <radialGradient id="flujoEsfera" cx="38%" cy="32%" r="70%">
          <stop offset="0" stopColor="#fffaf0" />
          <stop offset=".55" stopColor="#e6dccb" />
          <stop offset="1" stopColor="#b9a98f" />
        </radialGradient>
        <radialGradient id="flujoHalo">
          <stop offset="0" stopColor="var(--c1)" stopOpacity=".45" />
          <stop offset="1" stopColor="var(--c1)" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Fronteras entre fases */}
      {FASES.map((f) => {
        const [x1, y1] = punto(L.r0 * 0.8, f.desde);
        const [x2, y2] = punto(L.rMax + 16, f.desde);
        return <line key={f.id} x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(239,233,222,.16)" strokeDasharray="4 6" />;
      })}

      {/* Anillos = ciclos */}
      {ciclos.map((c, i) => {
        const rx = radio(i);
        const sel = i === iActual;
        const [tx, ty] = punto(rx, -90); // bajo la línea del anillo: arriba va la pregunta de la frontera
        return (
          <g key={c.ciclo} className="cursor-pointer" onClick={() => onElegir(c.ciclo)}>
            <ellipse cx={cx} cy={cy} rx={rx} ry={ry(rx)} fill="none" stroke="transparent" strokeWidth="14" />
            <ellipse cx={cx} cy={cy} rx={rx} ry={ry(rx)} fill="none" stroke={sel ? "rgba(239,233,222,.55)" : "rgba(239,233,222,.14)"} strokeWidth={sel ? 1.8 : 1} />
            <text x={tx + 6} y={ty + 16} fontSize="10" fill={sel ? "#efe9de" : "rgba(239,233,222,.4)"} style={{ fontFamily: "var(--mono)" }}>
              C{c.ciclo}
            </text>
          </g>
        );
      })}

      {/* Actividad: un punto por fase en cada anillo; su tamaño, los mensajes de la fase */}
      {ciclos.map((c, i) =>
        FASES.map((f) => {
          const [x, y] = punto(radio(i), f.desde + 36);
          const peso = f.peso(c);
          const r = peso ? 3 + Math.sqrt(peso / maxPeso) * Math.min(9, paso * 0.32) : 2.5;
          const sel = i === iActual;
          return (
            <circle key={`${c.ciclo}-${f.id}`} cx={x} cy={y} r={r}
              fill={peso ? f.tono : "transparent"} fillOpacity={sel ? 0.95 : 0.3}
              stroke={f.tono} strokeOpacity={peso ? 0 : 0.5}
              className="cursor-pointer" onClick={() => onElegir(c.ciclo)}>
              <title>{`C${c.ciclo} · ${f.nombre}: ${f.detalle(c)}`}</title>
            </circle>
          );
        })
      )}

      {/* La esfera al centro */}
      <circle cx={cx} cy={cy} r={L.r0 * 1.15} fill="url(#flujoHalo)" />
      <circle cx={cx} cy={cy} r={L.r0 * 0.62} fill="url(#flujoEsfera)" />

      {/* Fase: nombre y cifra del ciclo elegido, fuera del anillo externo */}
      {FASES.map((f) => {
        const medio = f.desde + 36;
        const cos = Math.cos(rad(medio)), sin = Math.sin(rad(medio));
        const [x, y] = punto(L.rMax + L.rotulo, medio);
        const anchor = cos < -0.3 ? "end" : cos > 0.3 ? "start" : "middle";
        const dy = sin > 0.5 ? 12 : sin < -0.5 ? -14 : -2;
        return (
          <g key={f.id} transform={`translate(${x} ${y + dy})`}>
            <text textAnchor={anchor} fontSize={L.letra} fill={f.tono} style={{ fontFamily: "var(--serif)" }}>{f.nombre}</text>
            {actual && (
              <text textAnchor={anchor} y={L.cifra + 5} fontSize={L.cifra} fill="rgba(239,233,222,.6)" style={{ fontFamily: "var(--mono)" }}>
                {f.cifra(actual)} {f.unidad}
              </text>
            )}
          </g>
        );
      })}

      {/* Pregunta de decisión en cada frontera, sobre el anillo externo */}
      {L.preguntas && FASES.map((f) => {
        const [x, y] = punto(L.rMax + 16, f.desde);
        const pregunta = FRONTERAS[f.id].pregunta;
        const ancho = pregunta.length * 5.6 + 24;
        return (
          <g key={f.id} transform={`translate(${x} ${y})`}>
            <title>{FRONTERAS[f.id].nombre}</title>
            <polygon points={`0,-11 ${ancho / 2},0 0,11 ${-ancho / 2},0`} fill="#14111f" stroke="rgba(169,155,255,.55)" />
            <text textAnchor="middle" y="3.2" fontSize="9" fill="#d9d3ff">{pregunta}</text>
          </g>
        );
      })}
    </svg>
  );
}
