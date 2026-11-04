/*
 * Errores del modelo dichos para una persona. El backend reintenta solo los 503 (Gemini
 * saturado) y los 429 (cuota agotada) y, si siguen, deja el mensaje del proveedor
 * («Google Gemini respondió 503 tras 5 reintento(s): The model is overloaded… (UNAVAILABLE)»).
 * Aquí ese texto técnico, a veces con el JSON de Google, se cambia por una frase que dice
 * qué pasó y qué hacer; los demás errores pasan tal cual.
 */
const SATURADO = /\b503\b|UNAVAILABLE|overloaded|sobrecargad/i;
const CUOTA = /\b429\b|RESOURCE_EXHAUSTED|quota|cuota/i;

export const ETAPA = {
  cargada: "la carga de la entrevista",
  leida: "la lectura de la entrevista",
  extraida: "la extracción de términos",
  interpretada: "la interpretación de los términos",
  en_debate: "el debate entre agentes",
  arbitrada: "el arbitraje",
  modelada: "la escritura del léxico",
};

/** {tipo: "saturado"|"cuota"|null, titulo, texto, tecnico} */
export function explicarError(texto) {
  const tecnico = String(texto ?? "");
  if (SATURADO.test(tecnico)) {
    return {
      tipo: "saturado", tecnico,
      titulo: "Gemini está saturado en este momento",
      texto: "Google respondió que el modelo está sobrecargado (error 503). El sistema lo reintentó varias veces con "
        + "espera creciente y no alcanzó. No es un error tuyo: espera unos minutos y vuelve a intentarlo. "
        + "Lo que ya se hizo quedó guardado.",
    };
  }
  if (CUOTA.test(tecnico)) {
    return {
      tipo: "cuota", tecnico,
      titulo: "Se agotó la cuota de Gemini por ahora",
      texto: "Google respondió que se acabó la cuota gratuita de la clave (error 429). Espera un rato a que se renueve "
        + "o pon tu propia clave en Configuración. Lo que ya se hizo quedó guardado.",
    };
  }
  return { tipo: null, titulo: null, texto: tecnico, tecnico };
}

/** El texto que se muestra: legible si es un 503/429, el original si no. */
export function errorLegible(texto) {
  const e = explicarError(texto);
  return e.tipo ? `${e.titulo}. ${e.texto}` : e.texto;
}
