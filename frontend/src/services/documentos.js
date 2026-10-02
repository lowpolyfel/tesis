/*
 * Lectura local de archivos (.txt y .pdf). Se hace en el navegador; pdfjs-dist
 * se carga solo cuando se sube un PDF.
 */
export async function leerArchivo(file) {
  const nombre = file.name.toLowerCase();
  if (nombre.endsWith(".txt")) return file.text();
  if (nombre.endsWith(".pdf")) return leerPdf(file);
  throw new Error("Formato no soportado: usa .txt o .pdf");
}

async function leerPdf(file) {
  const [pdfjs, { default: workerUrl }] = await Promise.all([
    import("pdfjs-dist"),
    import("pdfjs-dist/build/pdf.worker.min.mjs?url"),
  ]);
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
  const pdf = await pdfjs.getDocument({ data: await file.arrayBuffer() }).promise;
  const paginas = [];
  for (let n = 1; n <= pdf.numPages; n++) {
    const pagina = await pdf.getPage(n);
    const { items } = await pagina.getTextContent();
    // Reconstruye renglones: hasEOL marca el fin de línea en pdf.js
    paginas.push(items.map((it) => it.str + (it.hasEOL ? "\n" : "")).join(""));
  }
  return paginas.join("\n");
}
