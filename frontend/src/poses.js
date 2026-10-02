/*
 * Dónde vive el orbe en cada pantalla.
 * x, y: desplazamiento desde el centro como fracción del viewport; s: escala.
 * En móvil el orbe sube y deja la mitad inferior al contenido, pero sigue
 * cambiando de lado para no quedarse quieto.
 */
const POSES = {
  loading:   { d: { x: 0, y: 0, s: 0 },          m: { x: 0, y: 0, s: 0 } },
  bloom:     { d: { x: 0, y: 0, s: 1.25 },       m: { x: 0, y: 0, s: 0.85 } },
  welcome:   { d: { x: 0, y: -0.09, s: 1.15 },    m: { x: 0, y: -0.08, s: 0.85 } },
  landing:   { d: { x: 0.22, y: 0.01, s: 1.05 }, m: { x: 0.14, y: -0.27, s: 0.66 } },
  login:     { d: { x: -0.23, y: 0.03, s: 0.88 },m: { x: -0.16, y: -0.29, s: 0.58 } },
  register1: { d: { x: 0.24, y: -0.07, s: 0.82 },m: { x: 0.16, y: -0.29, s: 0.58 } },
  register2: { d: { x: -0.24, y: 0.08, s: 0.82 },m: { x: -0.16, y: -0.29, s: 0.58 } },
  register3: { d: { x: 0.25, y: 0.1, s: 0.86 },  m: { x: 0.16, y: -0.29, s: 0.58 } },
  home:      { d: { x: 0, y: -0.16, s: 0.82 },   m: { x: 0, y: -0.26, s: 0.64 } },
};

export const isMobile = () => window.innerWidth < 760;

export function poseFor(key) {
  const p = POSES[key] ?? POSES.welcome;
  return isMobile() ? p.m : p.d;
}
