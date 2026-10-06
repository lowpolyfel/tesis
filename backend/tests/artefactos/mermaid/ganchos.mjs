export async function resolve(especificador, contexto, siguiente) {
  if (especificador === "dompurify") return { url: new URL("./dompurify.mjs", import.meta.url).href, shortCircuit: true };
  return siguiente(especificador, contexto);
}
