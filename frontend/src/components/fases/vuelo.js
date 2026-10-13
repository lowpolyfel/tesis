/*
 * Las esferas en las fases de validación (ADR 0024): lo que la persona valida o corrige
 * viaja como una esfera pequeña desde la tarjeta hasta la esfera grande, que lo absorbe.
 * Validar: verde. Corregir o descartar: rosa a violeta («aprende»), y la esfera grande
 * dice qué aprendió. Mientras vuela, la esfera pasa por encima del contenido.
 */
let vuelos = 0;

export function volarALaEsfera(orb, elemento, { mood = "success", etiqueta = null, moodSeccion = null, aprendio = null } = {}) {
  if (!orb || !elemento) return;
  const r = elemento.getBoundingClientRect();
  const x = (r.left + Math.min(56, r.width / 2) - innerWidth / 2) / innerWidth;
  const y = (r.top + Math.min(32, r.height / 2) - innerHeight / 2) / innerHeight;
  const id = `vuelo:${++vuelos}`;
  orb.setElevada(true, id);
  // sin madre: nace donde está la tarjeta, no dentro de la esfera grande
  orb.divide("tarjeta", [{ id, mood, x, y, s: 0.17, label: etiqueta, sub: null }], { membrana: false });
  setTimeout(() => {
    orb.update(id, { label: null });
    orb.fuse([id], "core", { membrana: false });
  }, 520);
  setTimeout(() => {
    orb.setElevada(false, id);
    if (aprendio) {
      orb.setMood("aprende");
      orb.update("core", { label: "Aprendió", sub: aprendio });
      orb.poke(0.9);
      setTimeout(() => {
        orb.update("core", { label: null, sub: null });
        if (moodSeccion) orb.setMood(moodSeccion);
      }, 2200);
    } else {
      orb.poke(0.6);
    }
  }, 1300);
}
