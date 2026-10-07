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
};

export const isMobile = () => window.innerWidth < 760;

export function poseFor(key) {
  const p = POSES[key] ?? POSES.welcome;
  return isMobile() ? p.m : p.d;
}
