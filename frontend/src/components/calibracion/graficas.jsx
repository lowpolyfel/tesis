import { useId, useLayoutEffect, useRef, useState } from "react";

/*
 * Las gráficas de la calibración (ADR 0026), con un solo sistema visual: el mismo marco
 * (ejes, rejilla, línea del umbral configurado, leyenda), la misma paleta validada para
 * daltonismo (.viz en dudamel.css) y el mismo significado del color en todas:
 *   naranja = ambiguo / a debate · azul = no ambiguo / directo · aqua = F1 · gris = sin etiqueta.
 * Son SVG propios (sin bibliotecas): se descargan como SVG con sus colores ya resueltos, y el
 * paquete para Overleaf dibuja las mismas figuras en pgfplots.
 * Ninguna se anima; al pasar el cursor se lee el valor exacto.
 */
const ANCHO_INICIAL = 640; // ancho inicial, hasta medir el real: el SVG se dibuja a su tamaño, sin escalar el texto
const M = { arriba: 18, derecha: 104, abajo: 44, izquierda: 52 };
const fmt = (x, d = 3) => (x == null ? "—" : Number(x).toFixed(d));
const lineal = (d0, d1, r0, r1) => (x) => r0 + ((x - d0) / (d1 - d0 || 1)) * (r1 - r0);

function marcas(min, max, paso) {
  const n = Math.round((max - min) / paso);
  return Array.from({ length: n + 1 }, (_, i) => +(min + i * paso).toFixed(6));
}

/* Descarga el SVG con los colores y fuentes resueltos (fuera de la página no hay variables CSS) */
function descargarSvg(svg, nombre) {
  const copia = svg.cloneNode(true);
  const orig = [svg, ...svg.querySelectorAll("*")], dest = [copia, ...copia.querySelectorAll("*")];
  orig.forEach((el, i) => {
    const cs = getComputedStyle(el);
    const d = dest[i];
    ["fill", "stroke", "stroke-width", "stroke-dasharray", "opacity", "font-family", "font-size", "font-weight"].forEach((p) => {
      const v = cs.getPropertyValue(p);
      if (v && v !== "none" || p === "fill" || p === "stroke") d.style.setProperty(p, v);
    });
  });
  copia.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const url = URL.createObjectURL(new Blob([copia.outerHTML], { type: "image/svg+xml" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: `${nombre}.svg` });
  a.click();
  URL.revokeObjectURL(url);
}

/* Marco común: ejes con su rejilla, títulos de eje, leyenda y botón de descarga */
function Marco({ titulo, descripcion, nombre, alto = 300, x, y, leyenda = [], izquierda = M.izquierda, children }) {
  const svg = useRef(null);
  const caja = useRef(null);
  const [ancho, setAncho] = useState(ANCHO_INICIAL);
  // Mide el ancho disponible: 1 unidad del SVG = 1 px, así el texto mide lo mismo en todas las gráficas
  useLayoutEffect(() => {
    const el = caja.current;
    if (!el) return undefined;
    const medir = () => setAncho(Math.max(320, Math.round(el.clientWidth)));
    medir();
    const ro = new ResizeObserver(medir);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const M_ = { ...M, izquierda };
  const sx = lineal(x.min, x.max, M_.izquierda, ancho - M.derecha);
  const sy = lineal(y.min, y.max, alto - M.abajo, M.arriba);
  return (
    <figure className="viz tarjeta space-y-3 p-4">
      <div ref={caja} className="w-full" aria-hidden="true" />
      <figcaption className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="text-[14px] text-[var(--bone)]">{titulo}</span>
        {leyenda.length > 1 && (
          <span className="flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-[var(--bone-dim)]">
            {leyenda.map((l) => (
              <span key={l.texto} className="flex items-center gap-1.5">
                <svg width="18" height="10" aria-hidden="true"><line x1="1" x2="17" y1="5" y2="5" stroke={l.color} strokeWidth="2.5" strokeDasharray={l.trazo} /></svg>
                {l.texto}
              </span>
            ))}
          </span>
        )}
        <button className="mono ml-auto text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]" onClick={() => descargarSvg(svg.current, nombre)}>
          SVG ↓
        </button>
      </figcaption>
      <svg ref={svg} viewBox={`0 0 ${ancho} ${alto}`} width={ancho} height={alto} className="block max-w-full" role="img" aria-label={descripcion}>
        {(y.marcas ?? []).map((t) => (
          <g key={`y${t}`}>
            <line x1={M_.izquierda} x2={ancho - M.derecha} y1={sy(t)} y2={sy(t)} stroke="var(--viz-reja)" />
            <text x={M_.izquierda - 8} y={sy(t)} textAnchor="end" dominantBaseline="middle">{y.formato ? y.formato(t) : t}</text>
          </g>
        ))}
        {x.marcas.map((t) => (
          <g key={`x${t}`}>
            {x.reja !== false && <line x1={sx(t)} x2={sx(t)} y1={M.arriba} y2={alto - M.abajo} stroke="var(--viz-reja)" />}
            <text x={sx(t)} y={alto - M.abajo + 16} textAnchor="middle">{x.formato ? x.formato(t) : t}</text>
          </g>
        ))}
        <line x1={M_.izquierda} x2={ancho - M.derecha} y1={alto - M.abajo} y2={alto - M.abajo} stroke="var(--viz-eje)" />
        <line x1={M_.izquierda} x2={M_.izquierda} y1={M.arriba} y2={alto - M.abajo} stroke="var(--viz-eje)" />
        <text x={(M_.izquierda + ancho - M.derecha) / 2} y={alto - 6} textAnchor="middle">{x.titulo}</text>
        {y.titulo && <text transform={`translate(13 ${(M.arriba + alto - M.abajo) / 2}) rotate(-90)`} textAnchor="middle">{y.titulo}</text>}
        {children({ sx, sy, alto, ancho })}
      </svg>
    </figure>
  );
}

function LineaUmbral({ sx, sy, u, y0, y1 }) {
  return (
    <g>
      <line x1={sx(u)} x2={sx(u)} y1={sy(y0)} y2={sy(y1)} stroke="var(--bone-dim)" strokeWidth="1.2" strokeDasharray="5 4" />
      <text x={sx(u) + 5} y={sy(y1) + 10} className="viz-titulo" style={{ fontSize: 10.5 }}>umbral {u}</text>
    </g>
  );
}

/* Segmentos de una serie: un null corta la línea (p. ej. sin debates no hay precisión) */
function tramos(puntos) {
  const salida = [];
  let actual = [];
  for (const p of puntos) {
    if (p.y == null) { if (actual.length) salida.push(actual); actual = []; } else actual.push(p);
  }
  if (actual.length) salida.push(actual);
  return salida;
}

function Serie({ puntos, sx, sy, color, trazo, marca = "circulo" }) {
  return (
    <g>
      {tramos(puntos).map((t, i) => (
        <polyline key={i} points={t.map((p) => `${sx(p.x)},${sy(p.y)}`).join(" ")} fill="none" stroke={color} strokeWidth="2"
          strokeDasharray={trazo} strokeLinejoin="round" />
      ))}
      {puntos.filter((p) => p.y != null).map((p) => (marca === "cuadro"
        ? <rect key={p.x} x={sx(p.x) - 3.5} y={sy(p.y) - 3.5} width="7" height="7" rx="1.5" fill={color} stroke="var(--bg)" strokeWidth="1.5" />
        : <circle key={p.x} cx={sx(p.x)} cy={sy(p.y)} r="4" fill={color} stroke="var(--bg)" strokeWidth="1.5" />))}
    </g>
  );
}

/* Guía vertical y recuadro con los valores del umbral más cercano al cursor */
function Lector({ sx, alto, xs, filas, ancho = 150, total }) {
  const [i, setI] = useState(null);
  const paso = xs.length > 1 ? sx(xs[1]) - sx(xs[0]) : 40;
  const f = i == null ? null : filas(i);
  const x = i == null ? 0 : sx(xs[i]);
  const izquierda = x + ancho + 12 > total - 8;
  return (
    <g>
      {i != null && (
        <g pointerEvents="none">
          <line x1={x} x2={x} y1={M.arriba} y2={alto - M.abajo} stroke="var(--viz-eje)" />
          <g transform={`translate(${izquierda ? x - ancho - 8 : x + 8} ${M.arriba + 4})`}>
            <rect width={ancho} height={18 + f.length * 16} rx="6" fill="var(--bg)" stroke="var(--line)" />
            <text x="10" y="15" className="viz-titulo">umbral {xs[i]}</text>
            {f.map((r, k) => (
              <g key={r.texto} transform={`translate(10 ${31 + k * 16})`}>
                {r.color && <rect y="-8" width="9" height="9" rx="2" fill={r.color} />}
                <text x={r.color ? 15 : 0}>{r.texto}: <tspan className="viz-titulo">{r.valor}</tspan></text>
              </g>
            ))}
          </g>
        </g>
      )}
      {xs.map((u, k) => (
        <rect key={u} x={sx(u) - paso / 2} y={M.arriba} width={paso} height={alto - M.abajo - M.arriba} fill="transparent"
          onPointerEnter={() => setI(k)} onPointerLeave={() => setI(null)} />
      ))}
    </g>
  );
}

/* ---------------------------------------------------------------- figuras */

/* 1. Distribución: cada término es un punto en su fila (la clase del ground truth) */
export function GraficaDistribucion({ valores, umbral }) {
  const [sobre, setSobre] = useState(null);
  const clases = [
    { id: true, nombre: "Ambiguo", color: "var(--viz-naranja)" },
    { id: false, nombre: "No ambiguo", color: "var(--viz-azul)" },
    ...(valores.some((v) => v.ambiguo == null) ? [{ id: null, nombre: "Sin etiqueta", color: "var(--viz-gris)" }] : []),
  ];
  const min = Math.min(0, ...valores.map((v) => v.similitud));
  const alto = 70 + clases.length * 58;
  const fila = (c) => clases.findIndex((k) => k.id === c);
  const ordenados = [...valores].sort((a, b) => a.similitud - b.similitud);
  return (
    <Marco titulo="Similitud inicial por clase del ground truth" nombre="distribucion" alto={alto}
      descripcion="Cada término es un punto: su similitud inicial en el eje horizontal y su clase en la fila; la línea discontinua es el umbral configurado."
      x={{ min, max: 1, marcas: marcas(Math.floor(min * 10) / 10, 1, 0.1), titulo: "Similitud inicial (coseno mínimo entre paráfrasis)" }}
      y={{ min: clases.length - 0.5, max: -0.5 }} izquierda={96}>
      {({ sx, sy, ancho }) => (
        <g>
          {clases.map((c, k) => (
            <text key={c.nombre} x={96 - 10} y={sy(k)} textAnchor="end" dominantBaseline="middle" className="viz-titulo">{c.nombre}</text>
          ))}
          {ordenados.map((v, i) => {
            const k = fila(v.ambiguo ?? null);
            const c = clases[k];
            const y = sy(k) + (((i * 7) % 9) - 4) * 3.2;
            const activo = sobre === i;
            return (
              <g key={`${v.entrevista_id}:${v.termino}`} onPointerEnter={() => setSobre(i)} onPointerLeave={() => setSobre(null)}>
                <circle cx={sx(v.similitud)} cy={y} r="11" fill="transparent" />
                <circle cx={sx(v.similitud)} cy={y} r={activo ? 6 : 4.5} fill={c.color} stroke="var(--bg)" strokeWidth="1.5" />
                <title>{`${v.termino} (${v.entrevista_id}) · ${fmt(v.similitud)} · ${c.nombre.toLowerCase()} · ${v.decision_real === "en_debate" ? "fue a debate" : "aceptado directo"}`}</title>
              </g>
            );
          })}
          <LineaUmbral sx={sx} sy={sy} u={umbral} y0={clases.length - 0.5} y1={-0.5} />
          {sobre != null && (() => {
            const v = ordenados[sobre];
            return (
              <text x={ancho - M.derecha} y={M.arriba} textAnchor="end" className="viz-titulo">
                «{v.termino}» · {fmt(v.similitud)}
              </text>
            );
          })()}
        </g>
      )}
    </Marco>
  );
}

const SERIES_METRICAS = [
  { clave: "precision", texto: "Precisión", color: "var(--viz-azul)", marca: "cuadro" },
  { clave: "exhaustividad", texto: "Exhaustividad", color: "var(--viz-naranja)", trazo: "6 4" },
  { clave: "f1", texto: "F1", color: "var(--viz-aqua)", trazo: "2 3" },
];

/* 2. Precisión, exhaustividad y F1 en cada umbral; en el configurado, su intervalo bootstrap */
export function GraficaMetricas({ porUmbral, umbral, confianza, parametros }) {
  const xs = porUmbral.map((f) => f.umbral);
  const medidas = confianza?.medidas ?? {};
  return (
    <Marco titulo="Precisión, exhaustividad y F1 por umbral" nombre="metricas"
      descripcion="Cómo cambian la precisión, la exhaustividad y el F1 de «a debate» contra «ambiguo» al mover el umbral; en el umbral configurado, el intervalo de confianza al 95 %."
      leyenda={SERIES_METRICAS}
      x={{ min: parametros.desde, max: parametros.hasta, marcas: marcas(parametros.desde, parametros.hasta, 0.1 > parametros.hasta - parametros.desde ? parametros.paso : 0.05).filter((_, i, a) => a.length < 12 || i % 2 === 0), titulo: "Umbral" }}
      y={{ min: 0, max: 1, marcas: [0, 0.25, 0.5, 0.75, 1], titulo: "Valor" }}>
      {({ sx, sy, alto, ancho }) => (
        <g>
          {SERIES_METRICAS.map((s) => (
            <Serie key={s.clave} puntos={porUmbral.map((f) => ({ x: f.umbral, y: f[s.clave] }))} sx={sx} sy={sy} color={s.color} trazo={s.trazo} marca={s.marca} />
          ))}
          {/* intervalos en el umbral configurado, un poco separados para que no se tapen */}
          {SERIES_METRICAS.map((s, k) => {
            const ic = medidas[s.clave];
            if (!ic || ic.bajo == null) return null;
            const x = sx(umbral) + (k - 1) * 7;
            return (
              <g key={`ic-${s.clave}`}>
                <line x1={x} x2={x} y1={sy(ic.bajo)} y2={sy(ic.alto)} stroke={s.color} strokeWidth="2" />
                <line x1={x - 4} x2={x + 4} y1={sy(ic.bajo)} y2={sy(ic.bajo)} stroke={s.color} strokeWidth="2" />
                <line x1={x - 4} x2={x + 4} y1={sy(ic.alto)} y2={sy(ic.alto)} stroke={s.color} strokeWidth="2" />
              </g>
            );
          })}
          {/* rótulo directo al final de cada serie */}
          {SERIES_METRICAS.map((s) => {
            const ultimo = [...porUmbral].reverse().find((f) => f[s.clave] != null);
            return ultimo ? <text key={`r-${s.clave}`} x={sx(ultimo.umbral) + 8} y={sy(ultimo[s.clave])} dominantBaseline="middle">{s.texto}</text> : null;
          })}
          <LineaUmbral sx={sx} sy={sy} u={umbral} y0={0} y1={1} />
          <Lector sx={sx} alto={alto} total={ancho} xs={xs} filas={(i) => SERIES_METRICAS.map((s) => ({ texto: s.texto, color: s.color, valor: fmt(porUmbral[i][s.clave]) }))} />
        </g>
      )}
    </Marco>
  );
}

/* 3. Curva ROC: cuánto separa la similitud los casos, sin elegir umbral */
export function GraficaRoc({ roc, auc, ic }) {
  const id = useId();
  return (
    <Marco titulo={`Curva ROC · AUC ${fmt(auc)}${ic?.bajo != null ? ` [${fmt(ic.bajo)}, ${fmt(ic.alto)}]` : ""}`} nombre="roc" alto={360}
      descripcion="Tasa de ambiguos que van a debate contra tasa de no ambiguos que van a debate al mover el umbral; la diagonal es el azar."
      x={{ min: 0, max: 1, marcas: [0, 0.25, 0.5, 0.75, 1], titulo: "Tasa de falsos positivos (no ambiguos a debate)" }}
      y={{ min: 0, max: 1, marcas: [0, 0.25, 0.5, 0.75, 1], titulo: "Tasa de verdaderos positivos" }}>
      {({ sx, sy }) => (
        <g>
          <line x1={sx(0)} y1={sy(0)} x2={sx(1)} y2={sy(1)} stroke="var(--viz-gris)" strokeDasharray="2 4" />
          <text x={sx(0.62)} y={sy(0.55)} transform={`rotate(-27 ${sx(0.62)} ${sy(0.55)})`}>azar</text>
          <clipPath id={`${id}area`}><rect x={sx(0)} y={sy(1)} width={sx(1) - sx(0)} height={sy(0) - sy(1)} /></clipPath>
          <polygon clipPath={`url(#${id}area)`} points={`${sx(0)},${sy(0)} ${roc.map((p) => `${sx(p.fpr)},${sy(p.tpr)}`).join(" ")} ${sx(1)},${sy(0)}`}
            fill="var(--viz-azul)" opacity=".1" />
          <polyline points={roc.map((p) => `${sx(p.fpr)},${sy(p.tpr)}`).join(" ")} fill="none" stroke="var(--viz-azul)" strokeWidth="2" strokeLinejoin="round" />
          {roc.map((p, i) => (
            <g key={i}>
              <circle cx={sx(p.fpr)} cy={sy(p.tpr)} r="3.5" fill="var(--viz-azul)" stroke="var(--bg)" strokeWidth="1.5" />
              <circle cx={sx(p.fpr)} cy={sy(p.tpr)} r="9" fill="transparent">
                <title>{`${p.hasta != null ? `a debate hasta similitud ${fmt(p.hasta)}` : i ? "todo a debate" : "nada a debate"} · FPR ${fmt(p.fpr, 2)} · TPR ${fmt(p.tpr, 2)}`}</title>
              </circle>
            </g>
          ))}
        </g>
      )}
    </Marco>
  );
}

/* 4. Términos a debate y aceptados directo con cada umbral */
export function GraficaDebates({ rejilla, umbral, n, parametros }) {
  const xs = rejilla.map((f) => f.umbral);
  const tope = Math.max(1, n);
  const paso = tope <= 10 ? 1 : tope <= 40 ? 5 : 10;
  const series = [
    { clave: "debates", texto: "A debate", color: "var(--viz-naranja)" },
    { clave: "directos", texto: "Aceptados directo", color: "var(--viz-azul)", trazo: "6 4", marca: "cuadro" },
  ];
  return (
    <Marco titulo="Términos a debate y aceptados directo por umbral" nombre="debates" leyenda={series}
      descripcion="Con cada umbral de la rejilla, cuántos términos irían a debate y cuántos se aceptarían directo."
      x={{ min: parametros.desde, max: parametros.hasta, marcas: marcas(parametros.desde, parametros.hasta, 0.05).filter((_, i, a) => a.length < 12 || i % 2 === 0), titulo: "Umbral" }}
      y={{ min: 0, max: tope, marcas: marcas(0, Math.ceil(tope / paso) * paso, paso).filter((t) => t <= tope), titulo: "Términos" }}>
      {({ sx, sy, alto, ancho }) => (
        <g>
          {series.map((s) => <Serie key={s.clave} puntos={rejilla.map((f) => ({ x: f.umbral, y: f[s.clave] }))} sx={sx} sy={sy} color={s.color} trazo={s.trazo} marca={s.marca} />)}
          {series.map((s) => {
            const u = rejilla.at(-1);
            return u ? <text key={`r-${s.clave}`} x={sx(u.umbral) + 8} y={sy(u[s.clave])} dominantBaseline="middle">{s.texto}</text> : null;
          })}
          <LineaUmbral sx={sx} sy={sy} u={umbral} y0={0} y1={tope} />
          <Lector sx={sx} alto={alto} total={ancho} xs={xs} filas={(i) => series.map((s) => ({ texto: s.texto, color: s.color, valor: rejilla[i][s.clave] }))} />
        </g>
      )}
    </Marco>
  );
}

/* 5. Prueba de modelos (ADR 0027): por modelo, la exhaustividad (naranja: ambiguos marcados como
 * ambiguos), las falsas alarmas (azul: inequívocos marcados como ambiguos; solo con controles) y
 * la aprobación de la persona revisora (aqua), cada una con su intervalo de Wilson al 95 %. */
const SERIES_MODELOS = [
  { clave: "deteccion", texto: "Exhaustividad", color: "var(--viz-naranja)", dy: -10 },
  { clave: "falsas_alarmas", texto: "Falsas alarmas", color: "var(--viz-azul)", marca: "rombo", dy: 0 },
  { clave: "aprobacion", texto: "Aprobación (revisión)", color: "var(--viz-aqua)", marca: "cuadro", dy: 10 },
];

export function GraficaModelos({ modelos, nombres }) {
  const [sobre, setSobre] = useState(null);
  const series = SERIES_MODELOS.filter((s) => modelos.some((m) => m[s.clave]?.valor != null) || s.clave === "deteccion");
  const corto = (t) => (t.length > 30 ? `${t.slice(0, 29)}…` : t);
  const izquierda = Math.min(230, Math.max(96, 16 + 6.4 * Math.max(...modelos.map((m) => corto(nombres(m)).length))));
  const pct = (x) => (x == null ? "—" : `${Math.round(x * 100)} %`);
  return (
    <Marco titulo="Exhaustividad, falsas alarmas y aprobación por modelo" nombre="modelos" alto={74 + modelos.length * 56}
      leyenda={series.length > 1 ? series : []}
      descripcion="Por modelo, la proporción de ambiguos que marcó como ambiguos, la de inequívocos que marcó como ambiguos y la que la persona revisora aprobó, con su intervalo de confianza al 95 %."
      x={{ min: 0, max: 1, marcas: [0, 0.25, 0.5, 0.75, 1], formato: pct, titulo: "Proporción · intervalo de Wilson al 95 %" }}
      y={{ min: modelos.length - 0.5, max: -0.5 }} izquierda={izquierda}>
      {({ sx, sy, ancho }) => (
        <g>
          {modelos.map((m, k) => (
            <text key={m.id} x={izquierda - 10} y={sy(k)} textAnchor="end" dominantBaseline="middle" className="viz-titulo">
              {corto(nombres(m))}<title>{nombres(m)}</title>
            </text>
          ))}
          {modelos.map((m, k) => series.map((s) => {
            const v = m[s.clave];
            if (v?.valor == null) return null;
            const y = sy(k) + s.dy;
            const clave = `${m.id}-${s.clave}`;
            return (
              <g key={clave} onPointerEnter={() => setSobre(clave)} onPointerLeave={() => setSobre(null)}>
                <line x1={sx(v.bajo)} x2={sx(v.alto)} y1={y} y2={y} stroke={s.color} strokeWidth="2" />
                <line x1={sx(v.bajo)} x2={sx(v.bajo)} y1={y - 4} y2={y + 4} stroke={s.color} strokeWidth="2" />
                <line x1={sx(v.alto)} x2={sx(v.alto)} y1={y - 4} y2={y + 4} stroke={s.color} strokeWidth="2" />
                {s.marca === "cuadro" && <rect x={sx(v.valor) - 4} y={y - 4} width="8" height="8" rx="1.5" fill={s.color} stroke="var(--bg)" strokeWidth="1.5" />}
                {s.marca === "rombo" && <rect x={sx(v.valor) - 4} y={y - 4} width="8" height="8" rx="1" fill={s.color} stroke="var(--bg)" strokeWidth="1.5"
                  transform={`rotate(45 ${sx(v.valor)} ${y})`} />}
                {!s.marca && <circle cx={sx(v.valor)} cy={y} r="4.5" fill={s.color} stroke="var(--bg)" strokeWidth="1.5" />}
                <rect x={sx(v.bajo) - 6} y={y - 7} width={Math.max(12, sx(v.alto) - sx(v.bajo) + 12)} height="14" fill="transparent" />
                <title>{`${nombres(m)} · ${s.texto.toLowerCase()} ${pct(v.valor)} (${v.exitos}/${v.n}) · IC 95 % ${pct(v.bajo)}–${pct(v.alto)}`}</title>
              </g>
            );
          }))}
          {sobre && (() => {
            const [mid, clave] = sobre.split("-");
            const m = modelos.find((x) => x.id === mid);
            const v = m[clave];
            return (
              <text x={ancho - M.derecha} y={M.arriba - 4} textAnchor="end" className="viz-titulo">
                {corto(nombres(m))} · {pct(v.valor)} ({v.exitos}/{v.n}) · [{pct(v.bajo)}, {pct(v.alto)}]
              </text>
            );
          })()}
        </g>
      )}
    </Marco>
  );
}
