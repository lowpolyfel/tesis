/*
 * Estado mutable que el motor del orbe lee en cada cuadro.
 * Las páginas lo cambian sin provocar renders de React.
 *  - pose: posición como fracción del viewport desde el centro (x, y) y escala (s)
 *  - mood: clave de MOODS
 *  - shy:  el orbe aparta la mirada (p. ej. al escribir la contraseña)
 */
export function createOrbController() {
  const state = {
    mood: "idle",
    pose: { x: 0, y: 0, s: 0 },
    shy: false,
    kick: 0,
  };
  let moodTimer;

  return {
    state,
    setPose(pose) {
      state.pose = { ...state.pose, ...pose };
    },
    setMood(mood, { revertAfter } = {}) {
      clearTimeout(moodTimer);
      if (mood !== state.mood) {
        if (mood === "success") state.kick += 1.6;
        if (mood === "error") state.kick -= 0.7; // se encoge un instante, como un respingo
      }
      state.mood = mood;
      if (revertAfter) moodTimer = setTimeout(() => (state.mood = "idle"), revertAfter);
    },
    setShy(shy) {
      state.shy = shy;
    },
    poke(amount = 0.6) {
      state.kick += amount;
    },
  };
}
