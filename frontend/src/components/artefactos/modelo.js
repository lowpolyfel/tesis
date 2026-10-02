/*
 * Modelo conceptual (diagrama de clases UML) a partir de los artefactos:
 *   - sujetos del LEL y actores del Big Picture  → clases «actor»
 *   - objetos (LEL y acciones del Big Picture)    → clases «entidad»
 *   - estados del LEL                             → atributo de la entidad que nombran
 *   - acción actor → verbo → objeto               → asociación con nombre
 *   - restricciones y términos resueltos          → notas
 * Se exporta como Mermaid (classDiagram) y como PlantUML.
 */

export const artefactosDe = (r) => r.artefactos?.validados ?? r.artefactos?.borrador ?? r.artefactos?.propuesta;

const norm = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
const titulo = (s) => String(s).trim().replace(/^\p{L}/u, (c) => c.toUpperCase());
// Restricción legible: {tipo: "desempeño", metrica: "tiempo de respuesta", maximo: "2 s"} → "desempeño: tiempo de respuesta ≤ 2 s"
const texto = (x) => {
  if (typeof x === "string") return x;
  const { tipo, metrica, maximo, minimo, valor, ...resto } = x;
  const cuerpo = [metrica, maximo && `≤ ${maximo}`, minimo && `≥ ${minimo}`, valor, ...Object.values(resto)].filter(Boolean).join(" ");
  return tipo ? `${tipo}: ${cuerpo}` : cuerpo;
};

export function construirModelo(lista) {
  const clases = new Map();
  const relaciones = new Map();
  let n = 0;

  const clase = (nombre, tipo) => {
    const k = norm(nombre);
    if (!clases.has(k)) clases.set(k, { id: `C${++n}`, nombre: titulo(nombre), tipo, atributos: new Set(), notas: [], requisitos: new Set() });
    const c = clases.get(k);
    if (tipo === "actor") c.tipo = "actor"; // un actor gana sobre entidad
    return c;
  };

  for (const r of lista) {
    const a = artefactosDe(r);
    if (!a) continue;
    const bp = a.bigPicture ?? {};
    const lel = a.lel;

    for (const actor of bp.actores ?? []) clase(actor, "actor").requisitos.add(r.id);

    let principal = null;
    for (const ac of bp.acciones ?? []) {
      if (!ac.actor || !ac.objeto) continue;
      const de = clase(ac.actor, "actor");
      const hacia = clase(ac.objeto, "entidad");
      de.requisitos.add(r.id);
      hacia.requisitos.add(r.id);
      principal ??= hacia;
      for (const [k, v] of Object.entries(ac)) {
        if (["actor", "verbo", "objeto"].includes(k)) continue;
        hacia.atributos.add(`${k}: ${Array.isArray(v) ? v.join(", ") : v}`);
      }
      const clave = `${de.id}|${hacia.id}|${norm(ac.verbo)}`;
      if (!relaciones.has(clave)) relaciones.set(clave, { de: de.id, hacia: hacia.id, verbo: ac.verbo, requisitos: new Set() });
      relaciones.get(clave).requisitos.add(r.id);
    }

    if (lel) {
      if (lel.tipo === "sujeto") clase(lel.simbolo, "actor").requisitos.add(r.id);
      if (lel.tipo === "objeto") clase(lel.simbolo, "entidad").requisitos.add(r.id);
      if (lel.tipo === "estado") {
        // El estado se vuelve atributo de la entidad que nombra ("estatus del pedido" → Pedido)
        const duena = [...clases.values()].find((c) => c.tipo === "entidad" && norm(lel.simbolo).includes(norm(c.nombre)));
        if (duena) duena.atributos.add(lel.simbolo);
        else clase(lel.simbolo, "estado").requisitos.add(r.id);
      }
    }

    const destino = principal ?? [...clases.values()].at(-1);
    if (destino) {
      for (const x of bp.restricciones ?? []) destino.notas.push(`${r.id} · ${texto(x)}`);
      for (const t of bp.terminosResueltos ?? []) destino.notas.push(`«${t.termino}» = ${t.significado}`);
    }
  }

  return { clases: [...clases.values()], relaciones: [...relaciones.values()] };
}

/* ---------- Mermaid ---------- */
const limpiarM = (s) => String(s).replace(/"/g, "'").replace(/[{}<>]/g, " ");

export function aMermaid({ clases, relaciones }, { claro = false } = {}) {
  const l = ["classDiagram", "  direction LR"];
  for (const c of clases) {
    l.push(`  class ${c.id}["${limpiarM(c.nombre)}"]`);
    l.push(`  <<${c.tipo}>> ${c.id}`);
    for (const at of c.atributos) l.push(`  ${c.id} : +${limpiarM(at).replace(/:/g, " =")}`);
  }
  for (const r of relaciones) l.push(`  ${r.de} --> ${r.hacia} : ${limpiarM(r.verbo)}`);
  // Una nota por idea: Mermaid no admite saltos de línea en notas sin HTML
  for (const c of clases) for (const nota of c.notas) l.push(`  note for ${c.id} "${limpiarM(nota)}"`);
  const estilos = claro
    ? {
        actor: "fill:#eef0ff,stroke:#5b5bd6,color:#1b1712",
        entidad: "fill:#ecfbf3,stroke:#0f9a6a,color:#1b1712",
        estado: "fill:#fff6e5,stroke:#d38b00,color:#1b1712",
      }
    : {
        actor: "fill:#1c1830,stroke:#a99bff,color:#efe9de",
        entidad: "fill:#10201a,stroke:#57f7a7,color:#efe9de",
        estado: "fill:#231b0c,stroke:#ffc457,color:#efe9de",
      };
  // Color por tipo de clase (style por nodo: más fiable que cssClass entre versiones)
  for (const c of clases) l.push(`  style ${c.id} ${estilos[c.tipo]}`);
  return l.join("\n");
}

/* ---------- PlantUML ---------- */
const limpiarP = (s) => String(s).replace(/"/g, "'");

export function aPlantUML({ clases, relaciones }, { titulo: t = "Modelo conceptual" } = {}) {
  const l = [
    "@startuml",
    `title ${limpiarP(t)}`,
    "left to right direction",
    "hide empty methods",
    "skinparam classAttributeIconSize 0",
    "skinparam shadowing false",
    "skinparam class {",
    "  BackgroundColor<<actor>> #EEF0FF",
    "  BorderColor<<actor>> #5B5BD6",
    "  BackgroundColor<<entidad>> #ECFBF3",
    "  BorderColor<<entidad>> #0F9A6A",
    "  BackgroundColor<<estado>> #FFF6E5",
    "  BorderColor<<estado>> #D38B00",
    "}",
    "",
  ];
  for (const c of clases) {
    if (c.atributos.size) {
      l.push(`class "${limpiarP(c.nombre)}" as ${c.id} <<${c.tipo}>> {`);
      for (const at of c.atributos) l.push(`  ${limpiarP(at)}`);
      l.push("}");
    } else {
      l.push(`class "${limpiarP(c.nombre)}" as ${c.id} <<${c.tipo}>>`);
    }
  }
  l.push("");
  for (const r of relaciones) l.push(`${r.de} --> ${r.hacia} : ${limpiarP(r.verbo)}`);
  for (const c of clases) {
    if (!c.notas.length) continue;
    l.push(`note "${c.notas.map(limpiarP).join("\\n")}" as N${c.id}`);
    l.push(`${c.id} .. N${c.id}`);
  }
  l.push("@enduml");
  return l.join("\n");
}

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
