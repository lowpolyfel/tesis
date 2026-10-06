/*
 * Coreografía de la escena en vivo: traduce cada Mensaje real del backend
 * (emisor → receptor, tipo, payload) a movimientos del orbe.
 *
 *   - Cada nodo real es una esfera: extractor, filtros, clasificador,
 *     divergencia, crítico, humano, modelador. La esfera principal (core)
 *     queda arriba, pequeña, como el sistema (la orquestación).
 *   - Cada mensaje viaja como una partícula del emisor al receptor.
 *   - Las interpretaciones I1…In nacen por mitosis del Clasificador y se
 *     agrupan bajo la Divergencia: su distancia refleja la similitud.
 *   - Retirar una interpretación la devuelve al Clasificador; en el consenso
 *     se funden en la propuesta; en el arbitraje el Crítico absorbe las demás.
 *
 * No decide nada del método: solo dibuja lo que dicen los mensajes.
 */
import { ORDEN_NODOS, nodo, colorInterpretacion } from "../constants/agentes";
import { isMobile } from "../components/orb/poses";

const fmt = (x) => (x == null ? "—" : Number(x).toFixed(2));
const corto = (t, n = 26) => (t && t.length > n ? `${t.slice(0, n - 1)}…` : t ?? "");

function geometria() {
  const m = isMobile();
  const n = ORDEN_NODOS.length;
  const ancho = m ? 0.86 : 0.74;
  const xs = ORDEN_NODOS.map((_, i) => -ancho / 2 + (ancho * i) / (n - 1));
  // arco suave: los extremos un poco más abajo que el centro
  const ys = xs.map((x) => (m ? -0.12 : -0.11) + Math.abs(x) * 0.1);
  return {
    pos: Object.fromEntries(ORDEN_NODOS.map((id, i) => [id, { x: xs[i], y: ys[i] }])),
    s: m ? 0.14 : 0.22,
    sActivo: m ? 0.2 : 0.3,
    sistema: { x: 0, y: m ? -0.27 : -0.26, s: m ? 0.09 : 0.11 },
    grupo: { x: 0, y: m ? 0.05 : 0.06 }, // centro de las interpretaciones
    radioMax: m ? 0.15 : 0.19,
    radioMin: m ? 0.035 : 0.045,
    sInterp: m ? 0.1 : 0.14,
    sParticula: 0.05,
  };
}

export function crearCoreografia(orb) {
  let g = geometria();
  let montada = false;
  let particula = 0;
  // estado visual por término: { ids: Map(interpId -> esferaId), similitud, centro }
  const terminos = new Map();

  const idNodo = (n) => (n === "sistema" ? "core" : `n:${n}`);

  /* Fusión sin arrastrar textos: las etiquetas se borran antes de que viajen */
  function fundir(ids, destino, opciones) {
    const vivos = ids.filter((id) => orb.has(id));
    vivos.forEach((id) => orb.update(id, { label: null, sub: null }));
    if (vivos.length) orb.fuse(vivos, destino, opciones);
  }
  const posNodo = (n) => (n === "sistema" ? g.sistema : g.pos[n] ?? g.sistema);

  function etiquetar(n, sub, extra = {}) {
    const id = idNodo(n);
    if (!orb.has(id)) return;
    orb.update(id, { sub, ...extra });
  }

  function activar(n) {
    for (const otro of ORDEN_NODOS) {
      const id = idNodo(otro);
      if (!orb.has(id)) continue;
      const activo = otro === n;
      orb.update(id, { active: activo, dim: !activo, s: activo ? g.sActivo : g.s });
    }
    if (n) orb.poke(0.5, idNodo(n));
  }

  /* Partícula de mensaje: nace en el emisor, viaja y se funde en el receptor */
  function enviar(desde, hacia, mood) {
    const de = idNodo(desde), a = idNodo(hacia);
    if (!orb.has(de) || !orb.has(a) || de === a) return;
    const id = `msg:${++particula}`;
    const p = posNodo(hacia);
    orb.divide(de, [{ id, mood: mood ?? nodo(desde).id, x: p.x, y: p.y, s: g.sParticula, label: null, sub: null }],
      { membrana: false });
    setTimeout(() => fundir([id], a, { membrana: false }), 380);
  }

  /* ---------------------------------------------------- interpretaciones */

  /* Separación entre interpretaciones de un término: más juntas cuanto más similares */
  function separacion(t) {
    const min = isMobile() ? 0.13 : 0.1, max = isMobile() ? 0.22 : 0.17;
    if (t.similitud == null) return max;
    return min + (max - min) * Math.max(0, Math.min(1, (1 - t.similitud) * 2));
  }

  /* Los términos se acomodan en fila, uno junto a otro; dentro de cada uno, sus interpretaciones en fila */
  function distribuirTodos() {
    const claves = [...terminos.keys()];
    const anchos = claves.map((k) => Math.max(0, terminos.get(k).ids.size - 1) * separacion(terminos.get(k)));
    const hueco = isMobile() ? 0.16 : 0.12;
    const bruto = anchos.reduce((a, w) => a + w, 0) + hueco * Math.max(0, claves.length - 1);
    // si no cabe, todo se comprime en la misma proporción (la distancia relativa se conserva)
    const disponible = isMobile() ? 0.8 : 0.78;
    const f = bruto > disponible ? disponible / bruto : 1;
    let x = g.grupo.x - (bruto * f) / 2;
    claves.forEach((k, i) => {
      const t = terminos.get(k);
      const sep = separacion(t) * f;
      [...t.ids.values()].forEach((esfera, j) => orb.update(esfera, { x: x + j * sep, y: g.grupo.y + (i % 2) * 0.045 }));
      x += anchos[i] * f + hueco * f;
    });
  }
  const distribuir = () => distribuirTodos();

  function nacerInterpretaciones(termino, interps) {
    if (!terminos.has(termino)) terminos.set(termino, { ids: new Map(), similitud: null });
    const t = terminos.get(termino);
    const nuevas = [];
    for (const i of interps) {
      if (t.ids.has(i.id)) continue;
      const esfera = `i:${termino}:${i.id}`;
      t.ids.set(i.id, esfera);
      nuevas.push({
        id: esfera, mood: colorInterpretacion(i.id).mood, s: g.sInterp, x: g.grupo.x, y: g.grupo.y,
        label: i.id, sub: corto(i.significado, 18),
      });
    }
    if (nuevas.length) orb.divide(idNodo("clasificador"), nuevas);
    distribuirTodos();
  }

  function retirar(termino, ids, hacia) {
    const t = terminos.get(termino);
    if (!t) return;
    const esferas = ids.map((id) => t.ids.get(id)).filter(Boolean);
    ids.forEach((id) => t.ids.delete(id));
    if (esferas.length) fundir(esferas, idNodo(hacia));
    distribuir(termino);
  }

  function resolver(termino, ganadora, absorbe, nota = "elegida") {
    const t = terminos.get(termino);
    if (!t) return;
    const perdedoras = [...t.ids.keys()].filter((id) => id !== ganadora);
    const destino = t.ids.get(ganadora);
    const esferas = perdedoras.map((id) => t.ids.get(id)).filter(Boolean);
    perdedoras.forEach((id) => t.ids.delete(id));
    if (esferas.length) fundir(esferas, absorbe ? idNodo(absorbe) : destino ?? idNodo("clasificador"));
    if (destino && orb.has(destino)) {
      orb.update(destino, { mood: "success", sub: `${corto(termino, 12)} · ${nota}` });
      orb.poke(0.8, destino);
    }
    t.similitud = 1;
    distribuir(termino);
  }

  /* ------------------------------------------------------------ mensajes */

  const MANEJADORES = {
    extraccion(m) {
      const n = m.payload.terminos?.length ?? 0;
      etiquetar("extractor", `${n} término${n === 1 ? "" : "s"} del dominio`);
      return 900;
    },
    filtrado(m) {
      const ts = m.payload.terminos ?? [];
      const cuenta = (d) => ts.filter((t) => t.decision_filtro === d).length;
      const partes = [];
      if (cuenta("resuelto_por_lel")) partes.push(`${cuenta("resuelto_por_lel")} del LEL`);
      if (cuenta("vaguedad")) partes.push(`${cuenta("vaguedad")} vago${cuenta("vaguedad") > 1 ? "s" : ""}`);
      if (cuenta("regional")) partes.push(`${cuenta("regional")} regional${cuenta("regional") > 1 ? "es" : ""}`);
      if (cuenta("alcance") + cuenta("anafora")) partes.push(`${cuenta("alcance") + cuenta("anafora")} estructura(s)`);
      const candidatos = ts.filter((t) => ["candidato", "regional", "alcance", "anafora"].includes(t.decision_filtro)).length;
      etiquetar("filtros", `${candidatos} candidato${candidatos === 1 ? "" : "s"}${partes.length ? ` · ${partes.join(" · ")}` : ""}`);
      return 900;
    },
    interpretaciones(m) {
      const rs = m.payload.resultados ?? [];
      const ambiguos = rs.filter((r) => !r.univoco && r.interpretaciones?.length);
      etiquetar("clasificador", ambiguos.length
        ? ambiguos.map((r) => `«${corto(r.termino, 12)}» ${r.interpretaciones.length}`).join(" · ")
        : rs.length ? "todo unívoco" : "sin candidatos");
      ambiguos.slice(0, 6).forEach((r) => nacerInterpretaciones(r.termino, r.interpretaciones));
      return ambiguos.length ? 1700 : 900;
    },
    similitud(m) {
      const p = m.payload;
      if (p.similitud == null) {
        etiquetar("divergencia", p.motivo === "sin_interpretaciones" ? "nada que comparar" : "—");
        return 700;
      }
      const t = terminos.get(p.termino);
      if (t) { t.similitud = p.similitud; distribuir(p.termino); }
      const sobre = p.similitud >= p.umbral;
      // aceptado directo: se ven juntarse y luego quedan como una sola interpretación
      if (t && sobre && m.ronda === 0) {
        const primera = [...t.ids.keys()][0];
        setTimeout(() => resolver(p.termino, primera, null, "directo"), 900);
        // ya no se debate: la Divergencia lo absorbe y deja espacio a los que sí
        setTimeout(() => {
          const sigue = terminos.get(p.termino);
          if (!sigue) return;
          terminos.delete(p.termino);
          fundir([...sigue.ids.values()], idNodo("divergencia"));
          distribuirTodos();
        }, 2600);
      }
      etiquetar("divergencia", `«${corto(p.termino, 12)}» ${fmt(p.similitud)} ${sobre ? "≥" : "<"} ${fmt(p.umbral)}`,
        { mood: sobre ? "success" : "divergencia" });
      setTimeout(() => orb.has(idNodo("divergencia")) && orb.update(idNodo("divergencia"), { mood: "divergencia" }), 1400);
      return 1300;
    },
    objecion(m) {
      const p = m.payload;
      const ob = p.objeciones ?? [];
      etiquetar("critico", ob.length ? `ronda ${m.ronda}: ${ob.length} objeción${ob.length === 1 ? "" : "es"}` : `ronda ${m.ronda}: sin objeciones`);
      const t = terminos.get(p.termino);
      for (const o of ob) {
        const esfera = t?.ids.get(o.interpretacion_id);
        if (esfera && orb.has(esfera)) {
          orb.update(esfera, { mood: "error" });
          orb.poke(-0.4, esfera);
          setTimeout(() => orb.has(esfera) && orb.update(esfera, { mood: colorInterpretacion(o.interpretacion_id).mood }), 1100);
        }
      }
      return ob.length ? 1500 : 1000;
    },
    refinamiento(m) {
      const p = m.payload;
      const retiradas = (p.retiradas ?? []).map((r) => r.interpretacion_id);
      etiquetar("clasificador", retiradas.length ? `retira ${retiradas.join(", ")}` : `ronda ${m.ronda}: refina`);
      if (retiradas.length) retirar(p.termino, retiradas, "clasificador");
      const t = terminos.get(p.termino);
      for (const i of p.interpretaciones ?? []) {
        const esfera = t?.ids.get(i.id);
        if (esfera && orb.has(esfera)) orb.update(esfera, { sub: corto(i.significado, 18) });
      }
      return 1200;
    },
    consenso(m) {
      const p = m.payload;
      resolver(p.termino, p.propuesta, null, "consenso");
      etiquetar("divergencia", `consenso «${corto(p.termino, 12)}» (${p.motivo === "umbral" ? "umbral" : "una interpretación"})`, { mood: "success" });
      return 1500;
    },
    arbitraje(m) {
      const p = m.payload;
      resolver(p.termino, p.interpretacion_elegida, "critico", "arbitraje");
      etiquetar("critico", `arbitra «${corto(p.termino, 12)}»: ${p.interpretacion_elegida}`);
      return 1800;
    },
    solicitud_validacion(m) {
      const n = m.payload.terminos?.length ?? 0;
      etiquetar("humano", n ? `valida ${n} término${n === 1 ? "" : "s"}` : "valida el requisito", { mood: "humano" });
      return 900;
    },
    validacion(m) {
      const p = m.payload;
      const cambios = (p.terminos ?? []).filter((t) => t.cambio !== "ninguno").length;
      etiquetar("humano", p.decision === "aprobar" ? `aprobó${cambios ? ` (${cambios} cambio${cambios > 1 ? "s" : ""})` : ""}` : "rechazó",
        { mood: p.decision === "aprobar" ? "success" : "error" });
      // lo validado pasa al Modelador
      const esferas = [...terminos.values()].flatMap((t) => [...t.ids.values()]);
      if (p.decision === "aprobar" && esferas.length) fundir(esferas, idNodo("modelador"));
      else if (esferas.length) fundir(esferas, idNodo("humano"));
      terminos.clear();
      return 1200;
    },
    formalizacion(m) {
      const p = m.payload;
      if (p.alcance === "termino") etiquetar("modelador", `LEL: ${p.entrada_lel?.simbolo ?? p.termino}`);
      else etiquetar("modelador", `${p.entradas_lel?.length ?? 0} LEL · ${p.metas?.length ?? 0} meta${(p.metas?.length ?? 0) === 1 ? "" : "s"}`, { mood: "success" });
      return 1100;
    },
    error(m) {
      const n = m.emisor === "sistema" ? "sistema" : m.emisor;
      etiquetar(n, `error: ${corto(m.payload.excepcion ?? m.payload.mensaje, 24)}`, { mood: "error" });
      return 1400;
    },
  };

  return {
    /* La esfera principal se divide en los nodos */
    montar() {
      g = geometria();
      if (montada) return;
      montada = true;
      orb.setPose({ ...g.sistema });
      orb.update("core", { label: "Sistema", sub: "orquestación", s: g.sistema.s });
      orb.divide("core", ORDEN_NODOS.map((n) => ({
        id: idNodo(n), mood: n, ...g.pos[n], s: g.s, label: nodo(n).nombre, sub: "en espera", active: false, dim: true,
      })));
    },

    /* Vuelve a fundir todo en la esfera principal */
    desmontar() {
      if (!montada) return;
      montada = false;
      const interps = [...terminos.values()].flatMap((t) => [...t.ids.values()]);
      terminos.clear();
      fundir([...ORDEN_NODOS.map(idNodo), ...interps], "core");
      orb.update("core", { label: null, sub: null });
    },

    /* Limpia interpretaciones y textos para seguir otro requisito */
    reiniciar() {
      const interps = [...terminos.values()].flatMap((t) => [...t.ids.values()]);
      terminos.clear();
      if (interps.length) fundir(interps, idNodo("clasificador"));
      for (const n of ORDEN_NODOS) etiquetar(n, "en espera", { mood: n });
      activar(null);
    },

    /* Aplica un mensaje; devuelve cuánto dura su animación (ms) */
    aplicar(m) {
      if (!montada) return 0;
      activar(m.emisor === "sistema" ? null : m.emisor);
      if (m.emisor !== m.receptor) enviar(m.emisor, m.receptor, m.tipo === "error" ? "error" : undefined);
      const manejar = MANEJADORES[m.tipo];
      return manejar ? manejar(m) : 700;
    },

    /* Estado del requisito: al terminar, todos descansan */
    estado(estado) {
      orb.update("core", { sub: estado?.replaceAll("_", " ") ?? "" });
      if (["formalizado", "rechazado", "error", "pendiente_validacion"].includes(estado)) activar(estado === "pendiente_validacion" ? "humano" : null);
      if (estado === "formalizado") orb.setMood("success", { revertAfter: 2500 });
      if (estado === "error") orb.setMood("error", { revertAfter: 2500 });
    },

    reacomodar() {
      g = geometria();
      for (const n of ORDEN_NODOS) {
        const id = idNodo(n);
        if (orb.has(id)) orb.update(id, { ...g.pos[n] });
      }
      distribuirTodos();
    },
  };
}
