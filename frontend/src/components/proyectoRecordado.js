/* El último proyecto abierto: a dónde llevan «Analizar» y el menú de la esfera sin un proyecto en la ruta */
const CLAVE = "dudamel.proyecto";

export const proyectoRecordado = () => {
  try { return localStorage.getItem(CLAVE); } catch { return null; }
};

export const recordarProyecto = (id) => {
  try { localStorage.setItem(CLAVE, id); } catch { /* sin almacenamiento */ }
};
