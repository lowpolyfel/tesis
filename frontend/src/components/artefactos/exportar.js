/* Descargas y servidor de PlantUML para los artefactos que arma el backend */

/* Codificación de PlantUML para su servidor (deflate + base64 propio) */
const ALFABETO = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_";

export async function urlPlantUML(codigo, formato = "svg") {
  const flujo = new Blob([codigo]).stream().pipeThrough(new CompressionStream("deflate-raw"));
  const bytes = new Uint8Array(await new Response(flujo).arrayBuffer());
  let out = "";
  for (let i = 0; i < bytes.length; i += 3) {
    const [b1, b2 = 0, b3 = 0] = [bytes[i], bytes[i + 1], bytes[i + 2]];
    out += ALFABETO[b1 >> 2] + ALFABETO[((b1 & 3) << 4) | (b2 >> 4)] + ALFABETO[((b2 & 15) << 2) | (b3 >> 6)] + ALFABETO[b3 & 63];
  }
  return `https://www.plantuml.com/plantuml/${formato}/${out}`;
}

export function descargar(nombre, contenido, tipo) {
  const blob = contenido instanceof Blob ? contenido : new Blob([contenido], { type: tipo });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nombre;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/* PNG a partir del SVG (escala 2 para que se lea en la tesis) */
export async function svgAPng(svg, fondo = "#ffffff") {
  const img = new Image();
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  await new Promise((ok, mal) => { img.onload = ok; img.onerror = mal; img.src = url; });
  const doc = new DOMParser().parseFromString(svg, "image/svg+xml").documentElement;
  const vb = (doc.getAttribute("viewBox") ?? `0 0 ${img.width} ${img.height}`).split(/\s+/).map(Number);
  const [w, h] = [vb[2] || img.width, vb[3] || img.height];
  const canvas = document.createElement("canvas");
  canvas.width = w * 2;
  canvas.height = h * 2;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = fondo;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  URL.revokeObjectURL(url);
  return new Promise((ok) => canvas.toBlob(ok, "image/png"));
}
