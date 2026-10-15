/*
 * Una cita de la entrevista con el término resaltado: «T3 · Dra. Ruiz: … las consultas …».
 * El resaltado no distingue mayúsculas ni acentos, y acepta el plural (consulta → consultas).
 */
const sinAcentos = (s) => s.normalize("NFD").replace(/\p{Mn}/gu, "").toLowerCase();
const LETRA = /\p{L}/u;

/* El resaltado se calcula una vez por texto y términos: las tarjetas se vuelven a montar al
   filtrar o buscar en el léxico, y normalizar y recorrer cada cita letra por letra cuesta */
const resaltados = new Map();
const MAX_RESALTADOS = 800;

export function resaltar(texto, terminos) {
  const clave = `${texto}\u0000${terminos.join("\u0001")}`;
  let partes = resaltados.get(clave);
  if (!partes) {
    if (resaltados.size >= MAX_RESALTADOS) resaltados.clear();
    partes = marcar(texto, terminos);
    resaltados.set(clave, partes);
  }
  return partes;
}

function marcar(texto, terminos) {
  const base = sinAcentos(texto);
  const marcas = [];
  for (const t of terminos.filter(Boolean)) {
    const raiz = sinAcentos(t).replace(/(es|s)$/, "");
    if (raiz.length < 3) continue;
    let i = base.indexOf(raiz);
    while (i !== -1) {
      let fin = i + raiz.length;
      while (fin < base.length && LETRA.test(base[fin])) fin++; // la palabra completa (plurales, flexiones)
      if (i === 0 || !LETRA.test(base[i - 1])) marcas.push([i, fin]);
      i = base.indexOf(raiz, fin);
    }
  }
  marcas.sort((a, b) => a[0] - b[0]);
  const partes = [];
  let pos = 0;
  for (const [a, b] of marcas) {
    if (a < pos) continue;
    if (a > pos) partes.push(texto.slice(pos, a));
    partes.push(<mark key={a} className="resaltado">{texto.slice(a, b)}</mark>);
    pos = b;
  }
  partes.push(texto.slice(pos));
  return partes;
}

export default function Cita({ cita, terminos }) {
  return (
    <li className="text-[13.5px] leading-relaxed">
      <span className="mono mr-1.5 text-[9.5px] text-[var(--bone-faint)]">{cita.entrevista}·T{cita.turno}</span>
      {cita.hablante && <b className="font-medium text-[var(--bone)]">{cita.hablante}: </b>}
      <span className="text-[var(--bone-dim)]">«{resaltar(cita.fragmento, terminos)}»</span>
    </li>
  );
}
