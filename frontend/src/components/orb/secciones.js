import { isMobile } from "./poses";

/*
 * Cada sección tiene su lado, su altura y su color: la esfera principal vive
 * enorme en el margen de esa sección y, al cambiar de sección, cruza la pantalla
 * hacia el otro lado (las secciones vecinas alternan de lado). El contenido va
 * al centro; la esfera ocupa el margen y se asoma por el borde.
 *
 *   lado: -1 izquierda, 1 derecha · y: altura del centro (fracción del alto)
 *   mood: tono de la esfera y del ambiente de la sección
 */
export const SECCIONES = {
  proyectos: { lado: 1, y: 0.22, mood: "idle", nombre: "Proyectos" },
  requisitos: { lado: -1, y: 0.26, mood: "clasificador", nombre: "Requisitos" },
  especificacion: { lado: 1, y: 0.14, mood: "modelador", nombre: "Especificación" },
  lexico: { lado: -1, y: 0.1, mood: "extractor", nombre: "Léxico" },
  mapa: { lado: 1, y: 0.3, mood: "critico", nombre: "Mapa" },
  requisito: { lado: 1, y: 0.2, mood: "idle", nombre: "Requisito" },
  revision: { lado: -1, y: 0.18, mood: "humano", nombre: "Revisión" },
  analizar: { lado: 1, y: 0.2, mood: "idle", nombre: "Analizar" },
  mas: { lado: 1, y: 0.28, mood: "sistema", nombre: "Más" },
  avanzado: { lado: -1, y: 0.3, mood: "sistema", nombre: "Análisis" },
};

export const seccion = (id) => SECCIONES[id] ?? SECCIONES.proyectos;

/* Ancho de la columna de contenido (ver Shell): la esfera ocupa lo que sobra */
export const ANCHO_CONTENIDO = 860;

/*
 * Pose de la esfera para una sección. En escritorio es enorme (según el alto de
 * la pantalla) y su centro queda más allá del borde: solo se asoma lo que cabe
 * en el margen, para no pasar por detrás del texto. En móvil se asoma por la
 * esquina inferior.
 */
export function poseSeccion(id, ancho = ANCHO_CONTENIDO) {
  const s = seccion(id);
  if (isMobile()) return { x: s.lado * 0.52, y: 0.5, s: 1.25, deriva: 0 };
  const escala = Math.min(2.6, Math.max(1.6, innerHeight / 350));
  const radio = 150 * escala; // las ondas más externas, con su vaivén, a esa escala
  const margen = Math.max(0, (innerWidth - ancho) / 2);
  const visible = Math.min(radio * 0.9, Math.max(130, margen - 36));
  return { x: s.lado * (0.5 + (radio - visible) / innerWidth), y: s.y, s: escala, deriva: 0.05 };
}
