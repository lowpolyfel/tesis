/*
 * Las ondas de cada esfera (tres manchas y cuatro anillos) y cómo se dibujan en su lienzo.
 * Este archivo también es el worker que las dibuja fuera del hilo principal (ver el final):
 * sin aceleración gráfica, un lienzo que cambia en cada cuadro se copia entero en el hilo
 * que lo dibuja, y con la esfera de sección eso frenaba toda la página.
 */

/* Ondas: solo armónicos enteros, la onda cierra sin costura */
const HARMONICS = [
  { k: 2, w: 1.0, rate: 0.42, turb: false },
  { k: 3, w: 0.72, rate: -0.58, turb: false },
  { k: 4, w: 0.42, rate: 0.77, turb: false },
  { k: 5, w: 0.22, rate: -0.95, turb: false },
  { k: 6, w: 0.32, rate: 1.7, turb: true },
  { k: 8, w: 0.18, rate: -2.3, turb: true },
];

const BLOBS = [
  { r: 112, ampK: 1.3, seed: 0.5, speedK: 0.9 },
  { r: 117, ampK: 1.6, seed: 2.4, speedK: 1.05 },
  { r: 122, ampK: 1.9, seed: 5.2, speedK: 1.2 },
];
const RINGS = [
  { r: 110, ampK: 1.0, seed: 0.0, speedK: 1.0, width: 4.2, opacity: 0.95, grad: "A" },
  { r: 116, ampK: 1.25, seed: 1.7, speedK: 1.12, width: 3, opacity: 0.6, grad: "B" },
  { r: 123, ampK: 1.5, seed: 3.1, speedK: 1.25, width: 2.1, opacity: 0.36, grad: "A" },
  { r: 131, ampK: 1.8, seed: 4.6, speedK: 1.38, width: 1.5, opacity: 0.22, grad: "B", soft: true },
];
const SHAPES = [...BLOBS, ...RINGS];
const ALFA_ANILLO = RINGS.map((r) => (r.soft ? r.opacity * 0.7 : r.opacity));

export const AMP_PX = 4.2;
const N = 64;
const TAU = Math.PI * 2;
const COS = Array.from({ length: N }, (_, i) => Math.cos((i / N) * TAU));
const SIN = Array.from({ length: N }, (_, i) => Math.sin((i / N) * TAU));
const ANG = Array.from({ length: N }, (_, i) => (i / N) * TAU);

// Lienzo de las ondas: más grande que la caja de 400 de la esfera, porque las ondas se
// salen de ella con la amplitud, el rebote y la respiración (orb.css lo centra)
export const LIENZO = 520;
const MARGEN = (LIENZO - 400) / 2;

/* Fases de partida de cada onda: cada esfera ondula distinto */
export const fasesIniciales = () => SHAPES.map((s) => HARMONICS.map((_, j) => s.seed * (j + 1.3) + Math.random() * 6));

const xs = new Float64Array(N), ys = new Float64Array(N);
const caja = new Float64Array(4); // x0, y0, x1, y1 de las ondas que se están trazando
const vaciarCaja = () => { caja[0] = caja[1] = Infinity; caja[2] = caja[3] = -Infinity; };

/* Puntos de una onda (radio con armónicos que avanzan con `fase`); agranda la caja */
function contorno(fases, si, p) {
  const shape = SHAPES[si], ph = fases[si];
  const amp = p.ampPx * shape.ampK, base = shape.r * p.radScale, avance = p.fase * shape.speedK;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < N; i++) {
    let r = base;
    for (let h = 0; h < HARMONICS.length; h++) {
      const H = HARMONICS[h];
      const w = H.turb ? H.w * p.turb : H.w;
      if (w > 0.001) r += Math.sin(ANG[i] * H.k + ph[h] + avance * H.rate) * amp * w;
    }
    const x = p.cx + COS[i] * r, y = p.cy + SIN[i] * r;
    xs[i] = x;
    ys[i] = y;
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }
  caja[0] = Math.min(caja[0], x0); caja[1] = Math.min(caja[1], y0);
  caja[2] = Math.max(caja[2], x1); caja[3] = Math.max(caja[3], y1);
}

/* Contorno cerrado suavizado con Catmull-Rom → Bézier, sin picos. Directo en el lienzo:
   armar la cadena de un <path> (toFixed) era la mayor parte del costo de las ondas */
function trazarContorno(ctx) {
  ctx.moveTo(xs[0], ys[0]);
  for (let i = 0; i < N; i++) {
    const i0 = (i - 1 + N) % N, i2 = (i + 1) % N, i3 = (i + 2) % N;
    ctx.bezierCurveTo(
      xs[i] + (xs[i2] - xs[i0]) / 6, ys[i] + (ys[i2] - ys[i0]) / 6,
      xs[i2] - (xs[i3] - xs[i]) / 6, ys[i2] - (ys[i3] - ys[i]) / 6,
      xs[i2], ys[i2],
    );
  }
  ctx.closePath();
}

/* Como el linearGradient de SVG (en la caja de la figura, girado sobre su centro): una
   línea por el centro, del largo de la caja, girada `giro` */
function degradado(ctx, giro, a, b, c) {
  const mx = (caja[0] + caja[2]) / 2, my = (caja[1] + caja[3]) / 2;
  const r = (caja[2] - caja[0] + caja[3] - caja[1]) / 4;
  const dx = Math.cos(giro) * r, dy = Math.sin(giro) * r;
  const g = ctx.createLinearGradient(mx - dx, my - dy, mx + dx, my + dy);
  g.addColorStop(0, a);
  if (c) { g.addColorStop(0.5, b); g.addColorStop(1, c); } else g.addColorStop(1, b);
  return g;
}

/*
 * Un cuadro de las ondas, en coordenadas de la caja de 400 de la esfera.
 *   p: { lado (px del búfer), fase (avance acumulado de las ondas), radScale, ampPx, turb,
 *        cx, cy (centro), giro (rad, de los degradados), c1, c2 }
 */
export function dibujarOndas(lienzo, ctx, fases, p) {
  if (lienzo.width !== p.lado) {
    lienzo.width = p.lado; // también borra el lienzo y su estado
    lienzo.height = p.lado;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  } else {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, p.lado, p.lado);
  }
  const k = p.lado / LIENZO;
  ctx.setTransform(k, 0, 0, k, MARGEN * k, MARGEN * k);

  // Manchas: la unión de los tres contornos llenada una sola vez, con la opacidad que antes
  // tenía su grupo SVG (donde se enciman no se suman)
  ctx.beginPath();
  vaciarCaja();
  for (let si = 0; si < BLOBS.length; si++) {
    contorno(fases, si, p);
    trazarContorno(ctx);
  }
  ctx.globalAlpha = 0.3;
  ctx.fillStyle = degradado(ctx, p.giro, p.c1, p.c2);
  ctx.fill();

  // Anillos: degradado A (c1 → c2 → c1) o B (c2 → c1 → c2)
  for (let ri = 0; ri < RINGS.length; ri++) {
    ctx.beginPath();
    vaciarCaja();
    contorno(fases, BLOBS.length + ri, p);
    trazarContorno(ctx);
    ctx.globalAlpha = ALFA_ANILLO[ri];
    ctx.strokeStyle = RINGS[ri].grad === "A" ? degradado(ctx, p.giro, p.c1, p.c2, p.c1) : degradado(ctx, p.giro, p.c2, p.c1, p.c2);
    ctx.lineWidth = RINGS[ri].width;
    ctx.stroke();
  }
}

/*
 * Como worker: OrbField le pasa cada lienzo una vez ({ alta, lienzo } con OffscreenCanvas),
 * en cada cuadro lo que cambió ({ cuadro: [p + clave] }) y al desmontar la esfera { baja }.
 * Dibuja una vez por cuadro de pantalla con lo último que llegó: si se atrasa, se salta
 * cuadros en vez de acumular mensajes (la fase llega acumulada, no se pierde avance).
 */
if (typeof WorkerGlobalScope !== "undefined" && self instanceof WorkerGlobalScope) {
  const lienzos = new Map(); // clave -> { lienzo, ctx, fases, p }
  let pendiente = false;
  const pintar = () => {
    pendiente = false;
    for (const l of lienzos.values()) {
      if (!l.p) continue;
      dibujarOndas(l.lienzo, l.ctx, l.fases, l.p);
      l.p = null;
    }
  };
  self.onmessage = ({ data }) => {
    if (data.alta) {
      lienzos.set(data.alta, { lienzo: data.lienzo, ctx: data.lienzo.getContext("2d"), fases: fasesIniciales(), p: null });
    } else if (data.baja) {
      lienzos.delete(data.baja);
    } else {
      for (const p of data.cuadro) {
        const l = lienzos.get(p.clave);
        if (l) l.p = p;
      }
      if (pendiente) return;
      pendiente = true;
      if (self.requestAnimationFrame) self.requestAnimationFrame(pintar);
      else setTimeout(pintar, 0);
    }
  };
}
