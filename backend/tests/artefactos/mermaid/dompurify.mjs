// Sustituto de DOMPurify para validar con el parser de Mermaid en Node, sin DOM.
const purify = { addHook() {}, removeHook() {}, removeHooks() {}, removeAllHooks() {}, sanitize: (s) => s,
  setConfig() {}, clearConfig() {}, isSupported: true };
export default purify;
