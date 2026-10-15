/*
 * Estado mutable que el motor de las esferas lee en cada cuadro. Las
 * páginas lo cambian sin provocar renders de React.
 *
 * Hay siempre una esfera principal ("core"). Puede dividirse (mitosis) en
 * otras esferas —los agentes— y volver a fusionarlas.
 *
 * Cada esfera: { id, mood, target: { x, y, s, deriva }, label, sub, desde (ms: muestra el tiempo transcurrido), active, dim, onClick }
 *   x, y:    desplazamiento desde el centro como fracción del viewport
 *   s:       escala (1 = esfera de 218 px)
 *   deriva:  amplitud (fracción del alto) de un vaivén lento a lo largo del borde
 *   onClick: la esfera se puede tocar (la principal abre el menú)
 *
 * setMood(mood, { revertAfter, ambiente = true }): tono de la esfera principal. Con
 *   `ambiente: false` solo cambia la esfera; el fondo y la niebla se quedan como están
 *   (vistas previas al pasar el cursor: el fondo de toda la página no parpadea).
 *   `revertAfter` (ms) la regresa a "idle".
 * update(id, patch): los rótulos (label, sub, desde, onClick) solo provocan un render de
 *   React si de verdad cambiaron; cada cambio sube `rev` de esa esfera.
 */
// Lo único de una esfera que dibuja React
const VISIBLES = ["label", "sub", "desde", "onClick"];

export function createOrbController() {
  const elevadores = new Set();
  const bodies = new Map();
  const listeners = new Set();
  // elevada: las esferas pasan por encima del contenido (menú de la esfera)
  const state = { bodies, ambient: "idle", shy: false, membranaHasta: 0, elevada: false };
  const membrana = (ms = 1500) => { state.membranaHasta = performance.now() + ms; };
  const emit = () => listeners.forEach((fn) => fn());
  // el regreso de la esfera y el del ambiente van aparte: una vista previa (ambiente: false)
  // no cancela el regreso pendiente del fondo
  let moodTimer, ambienteTimer;

  // rev: sube cada vez que cambia algo que React dibuja (rótulos, cronómetro, si se puede tocar)
  bodies.set("core", { id: "core", mood: "idle", target: { x: 0, y: 0, s: 0 }, kick: 0, rev: 0 });
  const core = () => bodies.get("core");

  const api = {
    state,

    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },

    /* ---- esfera principal ---- */
    setPose(pose) {
      core().target = { ...core().target, deriva: 0, ...pose }; // sin deriva salvo que la pose la pida
    },
    setMood(mood, { revertAfter, ambiente = true } = {}) {
      clearTimeout(moodTimer);
      if (ambiente) clearTimeout(ambienteTimer);
      const c = core();
      if (mood !== c.mood) {
        if (mood === "success") c.kick += 1.6;
        if (mood === "error") c.kick -= 0.7; // se encoge un instante, como un respingo
      }
      c.mood = mood;
      if (ambiente) state.ambient = mood;
      if (revertAfter) {
        moodTimer = setTimeout(() => { c.mood = "idle"; }, revertAfter);
        if (ambiente) ambienteTimer = setTimeout(() => { state.ambient = "idle"; }, revertAfter);
      }
    },
    setAmbient(mood) {
      clearTimeout(ambienteTimer);
      state.ambient = mood;
    },
    setShy(shy) {
      state.shy = shy;
    },
    // la esfera pasa por encima del contenido mientras alguien la necesite al frente (el menú, una
    // pantalla de carga): cada quien la sube y la baja con su nombre, y una bajada tardía de uno
    // no se lleva la de otro
    setElevada(elevada, quien = "general") {
      if (elevada) elevadores.add(quien); else elevadores.delete(quien);
      if (state.elevada === elevadores.size > 0) return;
      state.elevada = elevadores.size > 0;
      emit();
    },
    mood: () => core().mood,
    poke(amount = 0.6, id = "core") {
      const b = bodies.get(id);
      if (b) b.kick += amount;
    },

    /* ---- varias esferas ---- */
    has: (id) => bodies.has(id) && !bodies.get(id).fuseInto,

    /* Una esfera se divide: las hijas nacen dentro de ella y se separan.
       `membrana: false` evita el velo de pantalla completa (partículas de mensaje). */
    divide(parentId, children, { membrana: conMembrana = true } = {}) {
      const parent = bodies.get(parentId);
      for (const ch of children) {
        const prev = bodies.get(ch.id);
        bodies.set(ch.id, {
          kick: 0,
          ...prev,
          ...ch,
          fuseInto: null,
          spawnFrom: prev && !prev.fuseInto ? null : parentId,
          target: { x: ch.x, y: ch.y, s: ch.s },
          rev: (prev?.rev ?? 0) + 1,
        });
      }
      if (parent) parent.kick += conMembrana ? 0.9 : 0.25;
      if (conMembrana) membrana();
      emit();
    },

    /* Las esferas vuelven a entrar en `intoId` y desaparecen */
    fuse(ids, intoId, { membrana: conMembrana = true } = {}) {
      for (const id of ids) {
        const b = bodies.get(id);
        if (b && id !== intoId) b.fuseInto = intoId;
      }
      if (conMembrana) membrana(1200);
    },

    /* Quita esferas al instante, sin animación (al cambiar de escena) */
    clear(ids) {
      for (const id of ids) if (id !== "core") bodies.delete(id);
      emit();
    },

    update(id, patch) {
      const b = bodies.get(id);
      if (!b) return;
      const { x, y, s, ...rest } = patch;
      // lo demás (ánimo, active, dim…) lo lee el motor en cada cuadro, sin pasar por React
      const cambio = VISIBLES.some((k) => k in rest && rest[k] !== b[k]);
      Object.assign(b, rest);
      if (x != null || y != null || s != null) {
        b.target = { ...b.target, x: x ?? b.target.x, y: y ?? b.target.y, s: s ?? b.target.s };
      }
      if (cambio) {
        b.rev = (b.rev ?? 0) + 1;
        emit();
      }
    },

    /* Lo llama el motor cuando una esfera terminó de fusionarse */
    _remove(id) {
      bodies.delete(id);
      emit();
    },
  };
  return api;
}
