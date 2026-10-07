/*
 * Una línea legible por mensaje del protocolo (bitácora en vivo y traza).
 * Solo describe el payload; no interpreta nada que el backend no haya dicho.
 */
const n2 = (x) => (x == null ? "—" : Number(x).toFixed(2));
const plural = (n, uno, otros) => `${n} ${n === 1 ? uno : otros}`;

export function resumenMensaje(m) {
  const p = m.payload ?? {};
  switch (m.tipo) {
    case "extraccion":
      return `${plural(p.terminos?.length ?? 0, "término", "términos")} del dominio${p.descartados?.length ? ` · ${p.descartados.length} descartado(s) por no estar en el texto` : ""}`;
    case "filtrado": {
      const ts = p.terminos ?? [];
      const por = (d) => ts.filter((t) => t.decision_filtro === d).map((t) => `«${t.termino}»`);
      const partes = [
        por("resuelto_por_lel").length && `LEL: ${por("resuelto_por_lel").join(", ")}`,
        por("vaguedad").length && `vaguedad: ${por("vaguedad").join(", ")}`,
        por("regional").length && `regional: ${por("regional").join(", ")}`,
        por("alcance").length && `alcance: ${por("alcance").join(", ")}`,
        por("anafora").length && `anáfora: ${por("anafora").join(", ")}`,
        por("candidato").length && `candidatos: ${por("candidato").join(", ")}`,
      ].filter(Boolean);
      return partes.join(" · ") || "sin términos";
    }
    case "interpretaciones": {
      const rs = p.resultados ?? [];
      if (!rs.length) return p.nota ?? "sin candidatos";
      const amb = rs.filter((r) => !r.univoco);
      const uni = rs.filter((r) => r.univoco).map((r) => `«${r.termino}»`);
      return [
        ...amb.map((r) => `«${r.termino}» ${r.tipo_ambiguedad ?? ""}: ${r.interpretaciones.map((i) => i.id).join(", ")}`),
        uni.length && `unívocos: ${uni.join(", ")}`,
      ].filter(Boolean).join(" · ");
    }
    case "similitud":
      if (p.similitud == null) return p.motivo === "sin_interpretaciones" ? "no hay interpretaciones que comparar" : "sin similitud";
      return `«${p.termino}» similitud ${n2(p.similitud)} ${p.similitud >= p.umbral ? "≥" : "<"} ${n2(p.umbral)} → ${String(p.decision).replaceAll("_", " ")}`;
    case "objecion": {
      const ob = p.objeciones ?? [];
      return ob.length
        ? `«${p.termino}» ${ob.map((o) => `${o.interpretacion_id} ${o.regla}`).join(", ")}`
        : `«${p.termino}» sin objeciones: todas cumplen R1–R3`;
    }
    case "refinamiento":
      return `«${p.termino}» quedan ${(p.interpretaciones ?? []).map((i) => i.id).join(", ")}${p.retiradas?.length ? ` · retira ${p.retiradas.map((r) => r.interpretacion_id).join(", ")}` : ""}${p.nota ? ` · ${p.nota}` : ""}`;
    case "consenso":
      return `«${p.termino}» consenso por ${p.motivo === "umbral" ? `umbral (${n2(p.similitud)})` : "una sola interpretación"} · propuesta ${p.propuesta}`;
    case "arbitraje":
      return `«${p.termino}» el Crítico elige ${p.interpretacion_elegida}`;
    case "solicitud_validacion":
      return `${plural(p.terminos?.length ?? 0, "término", "términos")} por validar${p.vaguedad?.length ? ` · vaguedad: ${p.vaguedad.join(", ")}` : ""}`;
    case "validacion": {
      const cambios = (p.terminos ?? []).filter((t) => t.cambio && t.cambio !== "ninguno");
      return `${p.decision === "aprobar" ? "aprobó" : "rechazó"}${cambios.length ? ` · ${cambios.map((t) => `«${t.termino}» ${t.cambio}`).join(", ")}` : ""}${p.comentario ? ` · «${p.comentario}»` : ""}`;
    }
    case "formalizacion":
      if (p.alcance === "termino") return `LEL: ${p.entrada_lel?.simbolo ?? p.termino} (${p.entrada_lel?.tipo ?? "—"})`;
      return `requisito reescrito · ${plural(p.entradas_lel?.length ?? 0, "entrada", "entradas")} del LEL · ${plural(p.metas?.length ?? 0, "meta", "metas")}`;
    case "error":
      return `${p.excepcion ?? "error"}${p.nodo ? ` en ${p.nodo}` : ""}: ${p.mensaje ?? ""}`;
    default:
      return "";
  }
}

/* Marcas para el texto del requisito a partir del mensaje `filtrado` (y del Clasificador si ya habló) */
export function marcasDesdeMensajes(mensajes) {
  const filtrado = [...mensajes].reverse().find((m) => m.tipo === "filtrado");
  if (!filtrado) return [];
  const interp = [...mensajes].reverse().find((m) => m.tipo === "interpretaciones");
  const tipoDe = new Map((interp?.payload?.resultados ?? []).map((r) => [r.termino, r.univoco ? null : r.tipo_ambiguedad]));
  const DECISION = { vaguedad: "vaguedad", regional: "regional", resuelto_por_lel: "lel", alcance: "alcance", anafora: "anaforica" };
  return (filtrado.payload.terminos ?? [])
    .map((t) => {
      const tipo = tipoDe.get(t.termino) ?? DECISION[t.decision_filtro] ?? null;
      return tipo ? { inicio: t.posicion.inicio, fin: t.posicion.fin, tipo, detalle: t.detalle, termino: t.termino } : null;
    })
    .filter(Boolean);
}
