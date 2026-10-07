/*
 * Estado mutable que el motor de las esferas lee en cada cuadro. Las
 * páginas lo cambian sin provocar renders de React.
 *
 * Hay siempre una esfera principal ("core"). Puede dividirse (mitosis) en
 * otras esferas —los agentes— y volver a fusionarlas.
 *
 * Cada esfera: { id, mood, target: { x, y, s, deriva }, label, sub, active, dim, onClick }
 *   x, y:    desplazamiento desde el centro como fracción del viewport
 *   s:       escala (1 = esfera de 218 px)
 *   deriva:  amplitud (fracción del alto) de un vaivén lento a lo largo del borde
 *   onClick: la esfera se puede tocar (la principal abre el menú)
 */
export function createOrbController() {
  const bodies = new Map();
  const listeners = new Set();
  // elevada: las esferas pasan por encima del contenido (menú de la esfera)
  const state = { bodies, ambient: "idle", shy: false, membranaHasta: 0, elevada: false };
  const membrana = (ms = 1500) => { state.membranaHasta = performance.now() + ms; };
  const emit = () => listeners.forEach((fn) => fn());
  let moodTimer;

  bodies.set("core", { id: "core", mood: "idle", target: { x: 0, y: 0, s: 0 }, kick: 0 });
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
    setMood(mood, { revertAfter } = {}) {
      clearTimeout(moodTimer);
      const c = core();
      if (mood !== c.mood) {
        if (mood === "success") c.kick += 1.6;
        if (mood === "error") c.kick -= 0.7; // se encoge un instante, como un respingo
      }
      c.mood = mood;
      state.ambient = mood;
      if (revertAfter) moodTimer = setTimeout(() => { c.mood = "idle"; state.ambient = "idle"; }, revertAfter);
    },
    setAmbient(mood) {
      state.ambient = mood;
    },
    setShy(shy) {
      state.shy = shy;
    },
    setElevada(elevada) {
      if (state.elevada === elevada) return;
      state.elevada = elevada;
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
      Object.assign(b, rest);
      if (x != null || y != null || s != null) {
        b.target = { ...b.target, x: x ?? b.target.x, y: y ?? b.target.y, s: s ?? b.target.s };
      }
      if ("label" in patch || "sub" in patch || "onClick" in patch) emit();
    },

    /* Lo llama el motor cuando una esfera terminó de fusionarse */
    _remove(id) {
      bodies.delete(id);
      emit();
    },
  };
  return api;
}
