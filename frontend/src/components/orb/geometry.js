/* Ondas: solo armónicos enteros, la onda cierra sin costura */
export const HARMONICS = [
  { k: 2, w: 1.0, rate: 0.42, turb: false },
  { k: 3, w: 0.72, rate: -0.58, turb: false },
  { k: 4, w: 0.42, rate: 0.77, turb: false },
  { k: 5, w: 0.22, rate: -0.95, turb: false },
  { k: 6, w: 0.32, rate: 1.7, turb: true },
  { k: 8, w: 0.18, rate: -2.3, turb: true },
];

export const BLOBS = [
  { r: 112, ampK: 1.3, seed: 0.5, speedK: 0.9 },
  { r: 117, ampK: 1.6, seed: 2.4, speedK: 1.05 },
  { r: 122, ampK: 1.9, seed: 5.2, speedK: 1.2 },
];
export const RINGS = [
  { r: 110, ampK: 1.0, seed: 0.0, speedK: 1.0, width: 4.2, opacity: 0.95, grad: "A" },
  { r: 116, ampK: 1.25, seed: 1.7, speedK: 1.12, width: 3, opacity: 0.6, grad: "B" },
  { r: 123, ampK: 1.5, seed: 3.1, speedK: 1.25, width: 2.1, opacity: 0.36, grad: "A" },
  { r: 131, ampK: 1.8, seed: 4.6, speedK: 1.38, width: 1.5, opacity: 0.22, grad: "B", soft: true },
];
export const SHAPES = [...BLOBS, ...RINGS];

export const AMP_PX = 4.2;
export const N = 64;
const TAU = Math.PI * 2;
export const COS = Array.from({ length: N }, (_, i) => Math.cos((i / N) * TAU));
export const SIN = Array.from({ length: N }, (_, i) => Math.sin((i / N) * TAU));
export const ANG = Array.from({ length: N }, (_, i) => (i / N) * TAU);

/* Contorno cerrado suavizado con Catmull-Rom → Bézier, sin picos */
export function smoothClosedPath(xs, ys) {
  let d = `M${xs[0].toFixed(2)},${ys[0].toFixed(2)}`;
  for (let i = 0; i < N; i++) {
    const i0 = (i - 1 + N) % N, i2 = (i + 1) % N, i3 = (i + 2) % N;
    const c1x = xs[i] + (xs[i2] - xs[i0]) / 6;
    const c1y = ys[i] + (ys[i2] - ys[i0]) / 6;
    const c2x = xs[i2] - (xs[i3] - xs[i]) / 6;
    const c2y = ys[i2] - (ys[i3] - ys[i]) / 6;
    d += `C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} ${xs[i2].toFixed(2)},${ys[i2].toFixed(2)}`;
  }
  return d + "Z";
}
