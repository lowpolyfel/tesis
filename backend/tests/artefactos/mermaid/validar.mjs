// node --import ./registrar.mjs validar.mjs <mermaid.core.mjs> <archivo.mmd>...
// Sale con 0 si todos los diagramas pasan el parser de Mermaid.
import fs from "node:fs";
import { pathToFileURL } from "node:url";

const [nucleo, ...archivos] = process.argv.slice(2);
const mermaid = (await import(pathToFileURL(nucleo).href)).default;
mermaid.initialize({ startOnLoad: false });
let fallos = 0;
for (const archivo of archivos) {
  try {
    await mermaid.parse(fs.readFileSync(archivo, "utf8"));
  } catch (e) {
    fallos += 1;
    console.log(`FALLA ${archivo}: ${String(e.message ?? e)}`);
  }
}
process.exit(fallos ? 1 : 0);
