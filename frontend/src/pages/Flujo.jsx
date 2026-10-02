import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useOrb } from "../components/orb/useOrb";
import { isMobile } from "../components/orb/poses";
import { listarProyectos, obtenerFlujo } from "../services/api";

/*
 * Flujo de conocimiento continuo, adaptado del modelo en espiral de KMoS-SSA /
 * SysM2 (Jiménez-Galina, Maldonado-Macías y Olmos-Sánchez, 2025).
 *   - la esfera es el centro: de ella parte cada ciclo
 *   - cada anillo es un ciclo (un lote analizado dentro del proyecto)
 *   - cada sector es una fase del sistema, con el agente que la realiza
 *   - en cada cruce de anillo y sector, cuánto trabajo se hizo en ese ciclo
 *   - en cada frontera, la pregunta que decide si se avanza o se retroalimenta
 */

const FASES = [
  {
    id: "elicitacion",
    nombre: "Elicitación",
    rol: "Extractor · catálogos",
    tono: "#41efff",
    desde: -90,
    chip: (m) => `${m.requisitos} req · ${m.marcados} marcas`,
    detalle: (m) => `${m.requisitos} requisitos cargados, ${m.terminos} términos extraídos, ${m.marcados} marcados como ambiguos`,
  },
  {
    id: "estructuracion",
    nombre: "Estructuración",
    rol: "Clasificador · similitud coseno",
    tono: "#a99bff",
    desde: -18,
    chip: (m) => `${m.interpretaciones} lect. · ${m.directos} dir.`,
    detalle: (m) => `${m.interpretaciones} interpretaciones candidatas, ${m.similitudes} comparaciones de similitud, ${m.directos} aceptados sin debate`,
  },
  {
    id: "enriquecimiento",
    nombre: "Enriquecimiento",
    rol: "Crítico · lecturas A y B",
    tono: "#ffc457",
    desde: 54,
    chip: (m) => `${m.debates} deb · ${m.rondas} R`,
    detalle: (m) => `${m.debates} debates, ${m.rondas} rondas, ${m.consensos} consensos, ${m.arbitrajes} arbitrajes`,
  },
  {
    id: "generacion",
    nombre: "Generación",
    rol: "Modelador",
    tono: "#57f7a7",
    desde: 126,
    chip: (m) => `${m.lel} LEL · ${m.artefactos} art.`,
    detalle: (m) => `${m.artefactos} artefactos (LEL, metas, Big Picture) para ${m.lel} requisitos`,
  },
  {
    id: "validacion",
    nombre: "Validación y decisión",
    rol: "Analista humano",
    tono: "#efe9de",
    desde: 198,
    chip: (m) => `${m.validados}✓ ${m.rechazados}✗ ${m.formalizados}◆`,
    detalle: (m) => `${m.validados} validados, ${m.rechazados} rechazados, ${m.formalizados} formalizados, ${m.reprocesos} reprocesos`,
  },
];

/* Frontera al inicio de cada fase: qué se verifica y la pregunta que decide */
const FRONTERAS = {
  elicitacion: { texto: "Retroalimentación · nuevo ciclo", pregunta: "¿Información suficiente?" },
  estructuracion: { texto: "Verificación de términos", pregunta: "¿Hay términos ambiguos?" },
  enriquecimiento: { texto: "Similitud contra umbral", pregunta: "¿Similitud ≥ umbral?" },
  generacion: { texto: "Discusión y arbitraje", pregunta: "¿Consenso?" },
  validacion: { texto: "Verificación y reflexión", pregunta: "¿Artefacto válido?" },
};

const rad = (g) => (g * Math.PI) / 180;

function useTamano() {
  const [t, setT] = useState({ w: innerWidth, h: innerHeight });
  useEffect(() => {
    const f = () => setT({ w: innerWidth, h: innerHeight });
    addEventListener("resize", f);
    return () => removeEventListener("resize", f);
  }, []);
  return t;
}

export default function Flujo() {
  const orb = useOrb();
  const [params, setParams] = useSearchParams();
  const proyecto = params.get("proyecto") ?? "";
  const [datos, setDatos] = useState(null);
  const [proyectos, setProyectos] = useState([]);
  const [foco, setFoco] = useState(null); // { fase, ciclo }
  const { w, h } = useTamano();
  const movil = isMobile();

  useEffect(() => { listarProyectos().then(setProyectos); }, []);
  useEffect(() => {
    let activo = true;
    const cargar = () => obtenerFlujo(proyecto || undefined).then((d) => activo && setDatos(d));
    cargar();
    const t = setInterval(cargar, 4000); // sigue vivo mientras los agentes trabajan
    return () => { activo = false; clearInterval(t); };
  }, [proyecto]);

  // Geometría: centro un poco a la izquierda para dejar espacio al panel
  const cx = movil ? w / 2 : w * 0.37;
  const cy = movil ? h * 0.42 : h * 0.54;
  const rMax = Math.min(movil ? w * 0.44 : w * 0.24, (movil ? h * 0.3 : h * 0.34) / 0.62);
  const r0 = movil ? 34 : 64;
  const ciclos = datos?.ciclos.slice(-6) ?? [];
  const n = Math.max(1, ciclos.length);
  const paso = (rMax - r0) / n;
  const ry = (rx) => rx * 0.62;
  const punto = (rx, g) => [cx + rx * Math.cos(rad(g)), cy + ry(rx) * Math.sin(rad(g))];

  // La esfera es el centro de la espiral
  useEffect(() => {
    orb.setPose({ x: cx / w - 0.5, y: cy / h - 0.5, s: movil ? 0.14 : 0.26 });
    orb.setMood("idle");
    orb.update("core", { label: null, sub: null });
  }, [orb, cx, cy, w, h, movil]);

  const nombreProyecto = proyectos.find((p) => p.id === proyecto)?.nombre ?? "Todos los proyectos";
  const anillos = useMemo(() => Array.from({ length: n }, (_, i) => r0 + paso * (i + 1)), [n, r0, paso]);

  return (
    <main className="relative z-10 min-h-screen">
      <svg className="fixed inset-0 z-[3] h-full w-full" viewBox={`0 0 ${w} ${h}`} aria-label="Espiral del flujo de conocimiento continuo">
        <defs>
          <marker id="flecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="rgba(239,233,222,.5)" />
          </marker>
        </defs>

        {/* Anillos = ciclos; el trazo fluye en el sentido del ciclo */}
        {anillos.map((rx, i) => (
          <g key={i}>
            <ellipse cx={cx} cy={cy} rx={rx} ry={ry(rx)} fill="none" stroke="rgba(239,233,222,.16)" strokeWidth={i === n - 1 ? 2.2 : 1.4} />
            <ellipse
              cx={cx} cy={cy} rx={rx} ry={ry(rx)} fill="none"
              stroke="var(--c1)" strokeOpacity={0.35 + (i / n) * 0.4} strokeWidth="1.2"
              strokeDasharray="2 18" className="flujo-anillo" style={{ animationDuration: `${18 + i * 6}s` }}
            />
            {ciclos[i] && (
              <text x={cx + 6} y={cy - ry(rx) - 5} className="mono" fontSize="10" fill="rgba(239,233,222,.6)">C{ciclos[i].ciclo}</text>
            )}
          </g>
        ))}

        {/* Fronteras entre fases: línea discontinua, rótulo y pregunta de decisión */}
        {FASES.map((f) => {
          const [x1, y1] = punto(r0 * 0.6, f.desde);
          const [x2, y2] = punto(rMax + (movil ? 18 : 46), f.desde);
          const fr = FRONTERAS[f.id];
          const [tx, ty] = punto(r0 + (rMax - r0) * 0.55, f.desde);
          const [dx, dy] = punto(rMax + (movil ? 30 : 74), f.desde);
          const ang = f.desde;
          const legible = ang > 90 && ang < 270 ? ang + 180 : ang;
          return (
            <g key={f.id}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(239,233,222,.32)" strokeDasharray="6 6" markerEnd="url(#flecha)" />
              {!movil && (
                <text x={tx} y={ty - 6} textAnchor="middle" fontSize="10.5" fill="#ff8f8f" fontWeight="600" transform={`rotate(${legible} ${tx} ${ty})`} className="mono">
                  {fr.texto}
                </text>
              )}
              {!movil && (
                <g transform={`translate(${dx} ${dy})`}>
                  <polygon points="0,-17 66,0 0,17 -66,0" fill="rgba(169,155,255,.12)" stroke="rgba(169,155,255,.55)" />
                  <text textAnchor="middle" y="3.5" fontSize="9.5" fill="#d9d3ff">{fr.pregunta}</text>
                </g>
              )}
            </g>
          );
        })}

        {/* Nombre de cada fase y el agente que la realiza */}
        {FASES.map((f) => {
          const medio = f.desde + 36;
          // A los lados el rótulo se aleja más para no tapar las etiquetas del anillo externo
          const lateral = Math.abs(Math.cos(rad(medio))) > 0.5;
          const [x, y] = punto(rMax + (movil ? 14 : lateral ? 82 : 34), medio);
          const izquierda = Math.cos(rad(medio)) < -0.2;
          const derecha = Math.cos(rad(medio)) > 0.2;
          const anchor = izquierda ? "end" : derecha ? "start" : "middle";
          const dyExtra = Math.sin(rad(medio)) > 0.5 ? 14 : Math.sin(rad(medio)) < -0.5 ? -18 : 0;
          return (
            <g key={f.id} transform={`translate(${x} ${y + dyExtra})`}>
              <text textAnchor={anchor} fontSize={movil ? 11 : 15} fill={f.tono} className="serif" style={{ fontFamily: "var(--serif)" }}>{f.nombre}</text>
              {!movil && <text textAnchor={anchor} y="15" fontSize="10" fill="rgba(239,233,222,.5)">{f.rol}</text>}
            </g>
          );
        })}

        {/* Lo que pasó en cada ciclo y fase */}
        {ciclos.map((c, i) =>
          FASES.map((f) => {
            const m = c[f.id];
            const [x, y] = punto(anillos[i], f.desde + 36);
            const etiqueta = f.chip(m);
            const ancho = etiqueta.length * (movil ? 4.6 : 5.9) + 14;
            const activo = foco && foco.fase === f.id && foco.ciclo === c.ciclo;
            const vacio = Object.values(m).every((v) => !v);
            return (
              <g
                key={`${c.ciclo}-${f.id}`}
                transform={`translate(${x} ${y})`}
                className="cursor-pointer"
                onMouseEnter={() => setFoco({ fase: f.id, ciclo: c.ciclo })}
                onMouseLeave={() => setFoco(null)}
                opacity={vacio ? 0.35 : 1}
              >
                <title>{`C${c.ciclo} · ${f.nombre}: ${f.detalle(m)}`}</title>
                <rect x={-ancho / 2} y={-10} width={ancho} height={20} rx={6} fill={activo ? f.tono : "rgba(13,11,10,.82)"} stroke={f.tono} strokeOpacity={activo ? 1 : 0.6} />
                <text textAnchor="middle" y={3.5} fontSize={movil ? 8 : 10} fill={activo ? "#16130f" : "rgba(239,233,222,.9)"}>{etiqueta}</text>
              </g>
            );
          })
        )}
      </svg>

      {/* Panel: interacciones y proyecto */}
      <aside className="fixed top-24 right-5 bottom-6 z-10 hidden w-[min(330px,28vw)] flex-col gap-5 overflow-y-auto md:flex">
        <div>
          <p className="mono text-[10px] text-[var(--bone-faint)]">Flujo de conocimiento continuo</p>
          <h1 className="serif mt-2 text-[42px] leading-[.95]">Cada <em>ciclo</em> aprende del anterior.</h1>
        </div>
        <select
          value={proyecto}
          onChange={(e) => setParams(e.target.value ? { proyecto: e.target.value } : {}, { replace: true })}
          className="mono w-fit rounded-full border border-[var(--line)] bg-transparent px-3 py-1.5 text-[11px] normal-case tracking-normal text-[var(--bone)] outline-none"
        >
          <option value="" className="bg-[#16130f]">Todos los proyectos</option>
          {proyectos.map((p) => <option key={p.id} value={p.id} className="bg-[#16130f]">{p.nombre}</option>)}
        </select>

        {datos && (
          <>
            <div>
              <p className="font-mono text-[46px] leading-none">{datos.interacciones}</p>
              <p className="mono mt-1 text-[9.5px] text-[var(--bone-faint)]">interacciones en {datos.ciclos.length} {datos.ciclos.length === 1 ? "ciclo" : "ciclos"} · {nombreProyecto}</p>
            </div>
            <dl className="space-y-1.5 text-sm">
              {[
                ["Extractor", "#41efff", datos.agentes.extractor, "extracciones"],
                ["Clasificador", "#a99bff", datos.agentes.clasificador, "lecturas y defensas"],
                ["Similitud", "#8f8bff", datos.total.estructuracion.similitudes, "comparaciones"],
                ["Crítico", "#ffc457", datos.agentes.critico, "rondas y arbitrajes"],
                ["Modelador", "#57f7a7", datos.agentes.modelador, "juegos de artefactos"],
                ["Analista", "#efe9de", datos.agentes.humano, "decisiones humanas"],
              ].map(([k, tono, v, d]) => (
                <div key={k} className="flex items-baseline gap-2">
                  <span className="punto" style={{ background: tono }} />
                  <dt className="w-24">{k}</dt>
                  <dd className="font-mono">{v}</dd>
                  <span className="text-[11px] text-[var(--bone-faint)]">{d}</span>
                </div>
              ))}
            </dl>
            <div className="space-y-1.5 border-t border-[var(--line)] pt-4 text-[12.5px] text-[var(--bone-dim)]">
              {FASES.map((f) => (
                <p key={f.id}><span style={{ color: f.tono }}>{f.nombre}:</span> {f.detalle(datos.total[f.id])}.</p>
              ))}
            </div>
            {foco && (
              <p className="rounded-lg border border-[var(--line)] p-3 text-[12.5px]">
                <span className="mono text-[9.5px] text-[var(--bone-faint)]">C{foco.ciclo} · {FASES.find((f) => f.id === foco.fase).nombre}</span>
                <br />
                {FASES.find((f) => f.id === foco.fase).detalle(datos.ciclos.find((c) => c.ciclo === foco.ciclo)[foco.fase])}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Link to={proyecto ? `/inicio?proyecto=${proyecto}` : "/inicio"} className="pill">Nuevo ciclo</Link>
              {proyecto && <Link to={`/proyectos/${proyecto}`} className="pill ghost">Proyecto</Link>}
            </div>
            <p className="mt-auto text-[10.5px] leading-snug text-[var(--bone-faint)]">
              Adaptado del modelo en espiral de KMoS-SSA / SysM2. Jiménez-Galina, A. M., Maldonado-Macías, A. A. y Olmos-Sánchez, K. M. (2025).
              Cada anillo es un ciclo de análisis; el ciclo más externo es el más reciente.
            </p>
          </>
        )}
      </aside>

      {movil && datos && (
        <div className="fixed inset-x-0 bottom-0 z-10 space-y-2 px-5 pb-6">
          <p className="font-mono text-[34px] leading-none">{datos.interacciones} <span className="mono text-[9.5px] text-[var(--bone-faint)]">interacciones · {datos.ciclos.length} ciclos</span></p>
          <p className="text-[12px] text-[var(--bone-dim)]">{nombreProyecto}</p>
        </div>
      )}
    </main>
  );
}
