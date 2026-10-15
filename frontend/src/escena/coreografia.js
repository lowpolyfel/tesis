/*
 * Coreografía de la escena en vivo: traduce cada Mensaje real del backend
 * (emisor → receptor, tipo, payload) a movimientos del orbe. Es «el relevo»:
 * cuatro esferas como máximo, con ids fijos, así que nunca hay más.
 *
 *   - core: la esfera principal, arriba y con el cronómetro, es el sistema (la
 *     orquestación); lo que dice el sistema va en su subtítulo.
 *   - agente: quien tiene el turno. Viaja a la estación del emisor de cada mensaje
 *     (ESTACIONES_* en constants/agentes.js), toma su tono y su nombre; su rótulo
 *     dice «Emisor → Receptor» y lo esencial del mensaje. Su viaje es el mensaje;
 *     si el receptor es el sistema, el core da un pulso.
 *   - par:1 y par:2: las dos intenciones más distintas del término en debate (el
 *     par_minimo de la similitud, ADR 0002). Nacen del agente y su distancia
 *     refleja la similitud. En el acuerdo se funden en la elegida; en el arbitraje
 *     el agente (el Crítico) absorbe la otra; una retirada vuelve al agente; lo
 *     acordado entra al sistema.
 *   - En escritorio la columna de la derecha ocupa `COLUMNA_ESCENA`: la escena se
 *     centra en el resto. `riel()` da las estaciones para el riel de texto (Riel.jsx).
 *
 * No decide nada del método: solo dibuja lo que dicen los mensajes. Un término
 * se identifica por su forma normalizada, como en el grafo y en la vista del
 * backend: el Clasificador puede escribir «Sesión» por el candidato «sesión».
 */
import { ESTACIONES_REQUISITO, nodo, colorInterpretacion } from "../constants/agentes";
import { estadoSimple } from "../constants/estados";
import { isMobile } from "../components/orb/poses";

const fmt = (x) => (x == null ? "—" : Number(x).toFixed(2));
const corto = (t, n = 26) => (t && t.length > n ? `${t.slice(0, n - 1)}…` : t ?? "");
const plural = (n, uno, otros) => `${n} ${n === 1 ? uno : otros}`;
const acotar = (x) => Math.max(0, Math.min(1, x));
/* Minúsculas y sin acentos (app.nlp.normalizar / app.analisis.traza.clave) */
export const clave = (termino) => (termino ?? "").normalize("NFD").replace(/\p{Mn}/gu, "").toLowerCase().trim();

/* Ancho de la columna de la derecha de la escena y lo que ocupa con su margen */
export const COLUMNA_ESCENA = "clamp(340px, 30vw, 460px)";
const anchoColumna = () => (isMobile() ? 0 : Math.min(460, Math.max(340, innerWidth * 0.3)) + 32);
/* Centro horizontal de la escena (fracción del ancho desde el centro de la pantalla) */
export const centroEscena = () => -anchoColumna() / innerWidth / 2;

/* Px por unidad de tamaño de una esfera: su rótulo empieza en s·128 + 14 (OrbField) */
const RADIO = 128;

function geometria(estaciones, bajarMovil) {
  const m = isMobile();
  const libre = 1 - anchoColumna() / innerWidth; // fracción del ancho que queda para la escena
  const cx = centroEscena();
  // en el teléfono el tramo es corto: el rótulo del agente no se sale por los lados
  const ancho = m ? 0.5 : libre * 0.62;
  const n = estaciones.length;
  const xs = estaciones.map((_, i) => cx - ancho / 2 + (ancho * i) / (n - 1));
  const b = m ? bajarMovil : 0;
  const sistema = { x: cx, y: (m ? -0.34 : -0.29) + b, s: m ? 0.2 : 0.36 };
  const yAgente = (m ? -0.17 : -0.01) + b, sAgente = m ? 0.2 : 0.42;
  // el riel va entre el rótulo del sistema (nombre y hasta dos líneas) y la cima del agente
  const bajoSistema = sistema.y * innerHeight + sistema.s * RADIO + 14 + (m ? 36 : 50);
  const sobreAgente = yAgente * innerHeight - sAgente * RADIO;
  return {
    sistema, xs, yAgente, sAgente,
    estacion: Object.fromEntries(estaciones.flatMap((e, i) => e.nodos.map((nd) => [nd, i]))), // nodo → estación
    riel: (bajoSistema + sobreAgente) / 2 / innerHeight,
    par: { x: cx, y: (m ? -0.035 : 0.25) + b },
    sPar: m ? 0.13 : 0.22,
    largo: m ? 12 : 18, // del significado bajo cada intención (en el teléfono, una línea)
    // separación del par: más juntas cuanto más similares
    sepMin: m ? 0.22 : 0.085,
    sepMax: m ? 0.5 : 0.3,
  };
}

const PAR = ["par:1", "par:2"];

/*
 * `estaciones`: los tramos por los que viaja el agente (ESTACIONES_REQUISITO en la versión 1,
 * ESTACIONES_ENTREVISTA en la 2). `bajarMovil`: cuánto baja la escena en el teléfono (fracción
 * del alto) para dejar sitio arriba, como el requisito en foco de pages/Analisis.jsx.
 */
export function crearCoreografia(orb, { estaciones = ESTACIONES_REQUISITO, bajarMovil = 0 } = {}) {
  let g = geometria(estaciones, bajarMovil);
  let montada = false;
  const primero = () => estaciones[0].nodos[0];
  let actual = primero(); // el nodo que tiene el turno: donde está el agente
  const intenciones = new Map(); // clave → Map(id → significado), de interpretaciones y refinamiento
  const pares = new Map(); // clave → { ids, similitud }: el último par mínimo de cada término
  let foco = null; // el par a la vista: { k, termino, ids }
  let rapido = false;
  let ritmo = 1;
  let vuelta = 0; // sube al reiniciar o desmontar: los pasos pendientes de antes ya no se aplican

  /* Un paso que se ve después del mensaje: dura según el ritmo; con «saltar» se aplica ya */
  function despues(ms, fn) {
    if (rapido) { fn(); return; }
    const v = vuelta;
    setTimeout(() => { if (montada && v === vuelta) fn(); }, ms / Math.max(0.25, ritmo));
  }

  /* Fusión sin arrastrar textos ni velo: las etiquetas se borran antes de que viajen */
  function fundir(ids, destino) {
    const vivos = ids.filter((id) => orb.has(id));
    vivos.forEach((id) => orb.update(id, { label: null, sub: null }));
    if (vivos.length) orb.fuse(vivos, destino, { membrana: false });
  }

  const nombre = (n) => nodo(n).nombre;
  const tieneEstacion = (n) => Object.hasOwn(g.estacion, n);
  const xDe = (n) => g.xs[g.estacion[n]];
  const rotulo = (m) => (m.receptor && m.receptor !== m.emisor ? `${nombre(m.emisor)} → ${nombre(m.receptor)}` : nombre(m.emisor));
  const sep = (sim) => (sim == null ? g.sepMax : g.sepMin + (g.sepMax - g.sepMin) * acotar((1 - sim) * 2));

  /* El agente toma el turno: viaja a la estación del emisor y dice lo esencial; lo del sistema lo dice el core */
  function hablar(m, sub, extra = {}) {
    const n = m.emisor;
    if (!tieneEstacion(n)) {
      orb.update("core", { sub });
      orb.poke(0.5, "core");
      return;
    }
    actual = n;
    orb.update("agente", { mood: n, label: rotulo(m), sub, x: xDe(n), y: g.yAgente, active: true, ...extra });
    orb.poke(0.5, "agente");
    if (m.receptor === "sistema") despues(450, () => orb.poke(0.45, "core")); // lo recibe el sistema
  }

  /* ---------------------------------------------- el par de intenciones */

  const significado = (k, id) => intenciones.get(k)?.get(id);
  const idsDe = (k) => (pares.get(k)?.ids?.length ? pares.get(k).ids : [...(intenciones.get(k)?.keys() ?? [])].slice(0, 2));

  function mostrarPar(termino, ids, similitud) {
    const k = clave(termino);
    if (!ids.length) { retirarPar("agente"); return; }
    const nuevo = foco?.k !== k;
    foco = { k, termino, ids: ids.slice(0, 2) };
    const d = sep(similitud);
    foco.ids.forEach((id, j) => {
      const datos = {
        mood: colorInterpretacion(id).mood, label: id, sub: corto(significado(k, id), g.largo),
        x: g.par.x + (foco.ids.length === 1 ? 0 : j ? d / 2 : -d / 2), y: g.par.y, s: g.sPar, active: false, dim: false,
      };
      // el mismo término: solo se acercan o alejan; otro término: sus intenciones salen del agente
      // (si la esfera sigue a la vista, cambia de rótulo en su sitio)
      if (orb.has(PAR[j]) && !nuevo) orb.update(PAR[j], datos);
      else orb.divide("agente", [{ id: PAR[j], ...datos }], { membrana: false });
    });
    if (foco.ids.length < 2) fundir([PAR[1]], "agente");
  }

  function retirarPar(hacia) {
    fundir(PAR, hacia);
    foco = null;
  }

  /* Queda una intención: la otra se funde en ella (acuerdo) o en el agente (la descarta el Crítico) */
  function resolver(termino, ganadora, { absorbe = null, nota }) {
    const k = clave(termino);
    if (foco?.k !== k) mostrarPar(termino, [ganadora], 1);
    let j = foco.ids.indexOf(ganadora);
    if (j < 0) { // la elegida no estaba a la vista: toma el primer lugar
      j = 0;
      foco.ids[0] = ganadora;
      orb.update(PAR[0], { mood: colorInterpretacion(ganadora).mood, label: ganadora, sub: corto(significado(k, ganadora), g.largo) });
    }
    fundir([PAR[1 - j]], absorbe ?? PAR[j]);
    orb.update(PAR[j], { mood: "success", sub: `${corto(termino, 12)} · ${nota}`, x: g.par.x });
    orb.poke(0.8, PAR[j]);
    const visto = foco;
    despues(1200, () => { if (foco === visto) retirarPar("core"); }); // lo acordado queda en el sistema
  }

  /* ------------------------------------------------------------ mensajes */

  const MANEJADORES = {
    ficha(m) {
      const p = m.payload;
      hablar(m, `${plural(p.participantes?.length ?? 0, "participante", "participantes")} · ${plural(p.necesidades ?? 0, "necesidad", "necesidades")}`);
      return 1100;
    },
    extraccion(m) {
      hablar(m, `${plural(m.payload.terminos?.length ?? 0, "término", "términos")} del dominio`);
      return 900;
    },
    filtrado(m) {
      const ts = m.payload.terminos ?? [];
      const de = (...ds) => ts.filter((t) => ds.includes(t.decision_filtro)).length;
      const partes = [
        de("resuelto_por_lel") && `${de("resuelto_por_lel")} ya en el léxico`,
        de("vaguedad") && `${de("vaguedad")} ${de("vaguedad") === 1 ? "vago" : "vagos"}`,
        de("regional") && `${plural(de("regional"), "regional", "regionales")}`,
      ].filter(Boolean);
      hablar(m, `${de("candidato", "regional", "alcance", "anafora")} a interpretar${partes.length ? ` · ${partes.join(" · ")}` : ""}`);
      return 900;
    },
    interpretaciones(m) {
      const rs = m.payload.resultados ?? [];
      const amb = rs.filter((r) => !r.univoco && r.interpretaciones?.length);
      // no nace ninguna esfera: se guardan las intenciones para cuando su término se debata
      for (const r of amb) intenciones.set(clave(r.termino), new Map(r.interpretaciones.map((i) => [i.id, i.significado])));
      hablar(m, amb.length
        ? `${amb.length === 1 ? "1 término" : `${amb.length} términos`} con varias intenciones: ${amb.slice(0, 2).map((r) => `«${corto(r.termino, 12)}»`).join(", ")}${amb.length > 2 ? "…" : ""}`
        : rs.length ? "sin doble sentido" : "nada nuevo que interpretar");
      return amb.length ? 1300 : 900;
    },
    similitud(m) {
      const p = m.payload;
      if (p.similitud == null) { hablar(m, "nada que comparar"); return 700; }
      const k = clave(p.termino);
      const ids = p.par_minimo?.length ? p.par_minimo : idsDe(k);
      pares.set(k, { ids, similitud: p.similitud });
      const sobre = p.similitud >= p.umbral;
      hablar(m, `«${corto(p.termino, 14)}» ${fmt(p.similitud)} ${sobre ? "≥" : "<"} ${fmt(p.umbral)} · ${sobre ? (m.ronda ? "acuerdo" : "se parecen") : m.ronda ? "siguen lejos" : "a debate"}`,
        { mood: sobre ? "success" : "divergencia" });
      mostrarPar(p.termino, ids, p.similitud);
      // aceptado directo: se juntan y queda la primera (la que propone el grafo)
      if (sobre && !m.ronda) {
        const primera = [...(intenciones.get(k)?.keys() ?? ids)][0] ?? ids[0];
        const visto = foco;
        despues(700, () => { if (foco === visto) resolver(p.termino, primera, { nota: "sin debate" }); });
      }
      despues(1100, () => actual === "divergencia" && orb.update("agente", { mood: "divergencia" }));
      return 1300;
    },
    objecion(m) {
      const p = m.payload;
      const k = clave(p.termino);
      const ob = p.objeciones ?? [];
      if (foco?.k !== k) mostrarPar(p.termino, idsDe(k), pares.get(k)?.similitud);
      hablar(m, ob.length ? `ronda ${m.ronda} · objeta ${ob.map((o) => `${o.interpretacion_id} (${o.regla})`).join(", ")}` : `ronda ${m.ronda} · sin objeciones`);
      for (const o of ob) {
        const j = foco?.ids.indexOf(o.interpretacion_id) ?? -1;
        if (j < 0 || !orb.has(PAR[j])) continue;
        orb.update(PAR[j], { mood: "error" });
        orb.poke(-0.4, PAR[j]);
        despues(1100, () => foco?.ids[j] === o.interpretacion_id && orb.update(PAR[j], { mood: colorInterpretacion(o.interpretacion_id).mood }));
      }
      return ob.length ? 1500 : 1000;
    },
    refinamiento(m) {
      const p = m.payload;
      const k = clave(p.termino);
      const retiradas = (p.retiradas ?? []).map((r) => r.interpretacion_id);
      if (p.interpretaciones) intenciones.set(k, new Map(p.interpretaciones.map((i) => [i.id, i.significado])));
      hablar(m, m.emisor === "sistema" ? "sin objeciones: no hace falta refinar"
        : retiradas.length ? `retira ${retiradas.join(", ")}` : `ronda ${m.ronda} · ajusta los significados`);
      if (foco?.k === k) {
        // la retirada vuelve al agente; las demás dicen su significado nuevo
        foco.ids.forEach((id, j) => {
          if (retiradas.includes(id)) fundir([PAR[j]], "agente");
          else if (orb.has(PAR[j])) orb.update(PAR[j], { sub: corto(significado(k, id), g.largo) });
        });
        foco.ids = foco.ids.filter((id) => !retiradas.includes(id));
      }
      return 1200;
    },
    consenso(m) {
      const p = m.payload;
      hablar(m, `acuerdo sobre «${corto(p.termino, 14)}»`);
      resolver(p.termino, p.propuesta, { nota: "acuerdo" });
      return 1500;
    },
    arbitraje(m) {
      const p = m.payload;
      hablar(m, `elige ${p.interpretacion_elegida} para «${corto(p.termino, 14)}»`);
      resolver(p.termino, p.interpretacion_elegida, { absorbe: "agente", nota: "la eligió el Crítico" });
      return 1800;
    },
    solicitud_validacion(m) {
      const n = m.payload.terminos?.length ?? 0;
      // el sistema le pasa el turno a la persona: el agente viaja a la estación de validación
      orb.update("core", { sub: "pide tu revisión" });
      orb.poke(0.5, "core");
      if (tieneEstacion("humano")) {
        actual = "humano";
        orb.update("agente", { mood: "humano", label: nombre("humano"), sub: n ? `revisa ${plural(n, "término", "términos")}` : "revisa el requisito", x: xDe("humano"), y: g.yAgente });
      }
      return 900;
    },
    validacion(m) {
      const p = m.payload;
      retirarPar("agente");
      if (p.automatica) { hablar(m, "sin conflictos: sigue solo"); return 900; }
      const cambios = (p.terminos ?? []).filter((t) => t.cambio !== "ninguno").length;
      hablar(m, p.decision === "aprobar" ? `aprobó${cambios ? ` (${plural(cambios, "cambio", "cambios")})` : ""}` : "rechazó",
        { mood: p.decision === "aprobar" ? "success" : "error" });
      return 1200;
    },
    formalizacion(m) {
      const p = m.payload;
      retirarPar("agente");
      const texto = p.alcance === "lexico"
        ? (p.entradas?.length ? `${plural(p.entradas.length, "término", "términos")} al léxico` : "nada nuevo para el léxico")
        : p.alcance === "termino" ? `«${p.entrada_lel?.simbolo ?? p.termino}» al léxico` : "requisito reescrito";
      hablar(m, texto, { mood: "success" });
      despues(900, () => actual === "modelador" && orb.update("agente", { mood: "modelador" }));
      return 1100;
    },
    edicion(m) {
      hablar(m, "corrigió el resultado", { mood: "humano" });
      return 900;
    },
    error(m) {
      const exc = corto(m.payload.excepcion ?? m.payload.mensaje, 24);
      if (tieneEstacion(m.emisor)) hablar(m, `falló: ${exc}`, { mood: "error" });
      else { orb.update("core", { sub: `falló: ${exc}` }); orb.setMood("error", { revertAfter: 2500 }); }
      return 1400;
    },
  };

  /* El agente vuelve a la primera estación, sin turno */
  function enEspera() {
    actual = primero();
    if (orb.has("agente")) orb.update("agente", { mood: actual, label: nombre(actual), sub: "en espera", x: xDe(actual), y: g.yAgente, active: false });
  }

  return {
    /* La esfera principal sube y se vuelve el sistema; de ella nace el agente (la única membrana) */
    montar() {
      g = geometria(estaciones, bajarMovil);
      if (montada) return;
      montada = true;
      orb.setPose({ ...g.sistema });
      orb.update("core", { label: "Sistema", sub: "coordina", s: g.sistema.s });
      actual = primero();
      orb.divide("core", [{ id: "agente", mood: actual, x: xDe(actual), y: g.yAgente, s: g.sAgente, label: nombre(actual), sub: "en espera", active: false, dim: false }]);
    },

    /* Vuelve a fundir todo en la esfera principal */
    desmontar() {
      if (!montada) return;
      montada = false;
      vuelta++;
      foco = null;
      fundir(["agente", ...PAR], "core");
      orb.update("core", { label: null, sub: null });
    },

    /* Para seguir otro requisito: lo de antes se olvida, el par vuelve al sistema y el agente al principio */
    reiniciar() {
      vuelta++;
      intenciones.clear();
      pares.clear();
      retirarPar("core");
      enEspera();
    },

    /*
     * Aplica un mensaje; devuelve cuánto dura su animación (ms, a 1×). `ritmo` escala
     * los pasos que vienen después (juntarse, entrar al sistema); con `rapido`
     * («saltar») se aplican al instante: lo que se salta se ve en su estado final.
     */
    aplicar(m, opciones = {}) {
      if (!montada) return 0;
      rapido = Boolean(opciones.rapido);
      ritmo = opciones.ritmo ?? ritmo;
      const manejar = MANEJADORES[m.tipo];
      const ms = manejar ? manejar(m) : 700;
      rapido = false;
      return ms;
    },

    /* Estado del requisito o de la entrevista, dicho debajo del sistema; al terminar, el agente descansa */
    estado(estado, texto) {
      orb.update("core", { sub: texto ?? (estado ? estadoSimple(estado).texto.toLowerCase() : "") });
      if (estado === "pendiente_validacion" && tieneEstacion("humano") && actual !== "humano") {
        actual = "humano";
        orb.update("agente", { mood: "humano", label: nombre("humano"), sub: "espera tu revisión", x: xDe("humano"), y: g.yAgente });
      }
      if (["formalizado", "rechazado", "error", "lista", "cancelada"].includes(estado) && orb.has("agente")) orb.update("agente", { active: false });
      if (estado === "formalizado" || estado === "lista") orb.setMood("success", { revertAfter: 2500 });
      if (estado === "error") orb.setMood("error", { revertAfter: 2500 });
    },

    reacomodar() {
      g = geometria(estaciones, bajarMovil);
      if (!montada) return;
      orb.setPose({ ...g.sistema });
      if (orb.has("agente")) orb.update("agente", { x: xDe(actual), y: g.yAgente, s: g.sAgente });
      if (foco) mostrarPar(foco.termino, foco.ids, pares.get(foco.k)?.similitud);
    },

    /* Para el riel de texto (Riel.jsx): la y del riel, la x de cada estación y cuál tiene el turno */
    riel() {
      if (!montada) return null;
      const r = geometria(estaciones, bajarMovil); // al día aunque la ventana acabe de cambiar
      return {
        y: r.riel, actual: r.estacion[actual] ?? 0, nodo: actual,
        estaciones: estaciones.map((e, i) => ({ id: e.id, nombre: e.nombre, x: r.xs[i] })),
      };
    },
  };
}
