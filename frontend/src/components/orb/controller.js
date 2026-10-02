/*
 * Estado mutable que el motor de las esferas lee en cada cuadro. Las
 * páginas lo cambian sin provocar renders de React.
 *
 * Hay siempre una esfera principal ("core"). Puede dividirse (mitosis) en
 * otras esferas —los agentes— y volver a fusionarlas.
 *
 * Cada esfera: { id, mood, target: { x, y, s }, label, sub, active, dim }
 *   x, y: desplazamiento desde el centro como fracción del viewport
 *   s:    escala (1 = esfera de 218 px)
 */
export function createOrbController() {
  const bodies = new Map();
  const listeners = new Set();
  const state = { bodies, ambient: "idle", shy: false, membranaHasta: 0 };
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
      core().target = { ...core().target, ...pose };
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
    poke(amount = 0.6, id = "core") {
      const b = bodies.get(id);
      if (b) b.kick += amount;
    },

    /* ---- varias esferas ---- */
    has: (id) => bodies.has(id) && !bodies.get(id).fuseInto,

    /* Una esfera se divide: las hijas nacen dentro de ella y se separan */
    divide(parentId, children) {
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
      if (parent) parent.kick += 0.9;
      membrana();
      emit();
    },

    /* Las esferas vuelven a entrar en `intoId` y desaparecen */
    fuse(ids, intoId) {
      for (const id of ids) {
        const b = bodies.get(id);
        if (b && id !== intoId) b.fuseInto = intoId;
      }
      membrana(1200);
    },

    update(id, patch) {
      const b = bodies.get(id);
      if (!b) return;
      const { x, y, s, ...rest } = patch;
      Object.assign(b, rest);
      if (x != null || y != null || s != null) {
        b.target = { x: x ?? b.target.x, y: y ?? b.target.y, s: s ?? b.target.s };
      }
      if ("label" in patch || "sub" in patch) emit();
    },

    /* Lo llama el motor cuando una esfera terminó de fusionarse */
    _remove(id) {
      bodies.delete(id);
      emit();
    },
  };
  return api;
}
