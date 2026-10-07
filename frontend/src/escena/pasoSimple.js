/*
 * Un mensaje del protocolo dicho como un paso, en una frase y sin jerga: es lo
 * que se lee en la escena en vivo. La bitácora técnica (resumenMensaje) sigue
 * en los detalles.
 */
const comillas = (t) => `«${t}»`;
const lista = (xs) => (xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} y ${xs.at(-1)}`);

export function pasoSimple(m) {
  const p = m.payload ?? {};
  switch (m.tipo) {
    case "extraccion": {
      const n = p.terminos?.length ?? 0;
      return n ? `El Extractor separó ${n} término${n === 1 ? "" : "s"} del dominio.` : "El Extractor no encontró términos del dominio.";
    }
    case "filtrado": {
      const ts = p.terminos ?? [];
      const de = (d) => ts.filter((t) => t.decision_filtro === d).map((t) => comillas(t.termino));
      const partes = [
        de("vaguedad").length && `${lista(de("vaguedad"))} es vago`,
        de("regional").length && `${lista(de("regional"))} es regional`,
        de("resuelto_por_lel").length && `${lista(de("resuelto_por_lel"))} ya está en el léxico`,
        (de("alcance").length || de("anafora").length) && `${lista([...de("alcance"), ...de("anafora")])} puede referirse a más de una cosa`,
      ].filter(Boolean);
      return partes.length ? `Los filtros notaron que ${lista(partes)}.` : "Los filtros no notaron nada fuera de lo común.";
    }
    case "interpretaciones": {
      const amb = (p.resultados ?? []).filter((r) => !r.univoco).map((r) => comillas(r.termino));
      if (!(p.resultados ?? []).length) return "No hubo términos que revisar.";
      return amb.length ? `El Clasificador encontró varios significados para ${lista(amb)}.` : "El Clasificador no encontró palabras con doble sentido.";
    }
    case "similitud":
      if (p.similitud == null) return p.motivo === "sin_interpretaciones" ? "No hay significados que comparar." : "Sin comparación.";
      return p.similitud >= p.umbral
        ? `Los significados de ${comillas(p.termino)} se parecen: no hace falta debatir.`
        : `Los significados de ${comillas(p.termino)} son distintos: ${m.ronda ? "siguen debatiendo" : "empieza el debate"}.`;
    case "objecion": {
      const n = p.objeciones?.length ?? 0;
      return n ? `El Crítico objetó ${n === 1 ? "un significado" : `${n} significados`} de ${comillas(p.termino)}.` : `El Crítico no objetó nada de ${comillas(p.termino)}.`;
    }
    case "refinamiento":
      return p.retiradas?.length
        ? `El Clasificador retiró ${p.retiradas.length === 1 ? "un significado" : `${p.retiradas.length} significados`} de ${comillas(p.termino)}.`
        : `El Clasificador mantuvo los significados de ${comillas(p.termino)}.`;
    case "consenso":
      return `Acuerdo sobre ${comillas(p.termino)}.`;
    case "arbitraje":
      return `Sin acuerdo sobre ${comillas(p.termino)}: el Crítico eligió un significado.`;
    case "solicitud_validacion":
      return "Hace falta tu revisión: los agentes no se pusieron de acuerdo.";
    case "validacion":
      if (p.automatica) return "Sin conflictos que revisar: sigue solo.";
      return p.decision === "aprobar" ? "Lo revisaste y lo aprobaste." : "Lo descartaste.";
    case "formalizacion":
      return p.alcance === "termino"
        ? `${comillas(p.entrada_lel?.simbolo ?? p.termino)} entró al léxico del proyecto.`
        : "El Modelador reescribió el requisito completo.";
    case "edicion":
      return "Corregiste el resultado.";
    case "error":
      return `Algo falló${p.nodo ? ` en ${p.nodo}` : ""}.`;
    default:
      return "";
  }
}
