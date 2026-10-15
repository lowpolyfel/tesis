import { memo, useEffect, useReducer, useRef, useState } from "react";
import { oklabToRgb, rgb, rgba } from "./color";
import { MOODS, MOODS_LAB, NUM_KEYS, COLOR_KEYS } from "./moods";
import { AMP_PX, LIENZO, fasesIniciales, dibujarOndas } from "./geometry";
import "./orb.css";

/* =========================================================================
   OrbField — todas las esferas de Dudamel, vivas en toda la app.
   - La esfera principal viaja con resortes: rebasa un poco y se asienta
   - Al viajar describe un arco, se estira como gelatina y agita sus ondas
   - Mira al cursor; si lo dejas quieto, curiosea solo; flota siempre
   - Mitosis: una esfera se divide en otras que nacen dentro de ella; una
     membrana (capa "goo") las une mientras se separan y cuando se fusionan
   Rendimiento: cada cuadro solo cambia transformaciones y opacidades (sin filtros SVG
   encima, que obligaban a repintar áreas enormes). Las ondas van en un lienzo que dibuja
   un worker (geometry.js) cuando el navegador lo permite: el hilo principal solo le pasa
   unos números por cuadro.
   El fondo cambia despacio en su propia capa (.orb-ambient, a 30 Hz); la raíz del
   documento recibe el color final una sola vez por cambio de ánimo o de tema:
   cada escritura ahí recalcula los estilos de toda la página.
   ========================================================================= */

const lerpK = (dt, rate) => 1 - Math.exp(-dt * rate);

const LADO_MAX = 3072; // tope del búfer de las ondas: con dpr 2 la esfera de sección (≈2700 px) cabe entera

/* Quien dibuja las ondas: un solo worker para toda la app (null si el navegador no puede
   pasarle un lienzo; entonces se dibujan aquí). Vive fuera de los efectos: un lienzo se le
   pasa una sola vez y no se puede recuperar */
let pintor;
let ultimaClave = 0;
const alFallar = new Set(); // quienes vuelven a montar sus lienzos si el worker no carga
function elPintor() {
  if (pintor === undefined) {
    pintor = null;
    if (typeof OffscreenCanvas !== "undefined" && "transferControlToOffscreen" in HTMLCanvasElement.prototype) {
      try {
        const w = new Worker(new URL("./geometry.js", import.meta.url), { type: "module" });
        // Si no llega a cargar (un 404, una CSP, un navegador sin workers de módulo), los lienzos
        // que ya se le pasaron no se recuperan: se vuelven a montar y se dibujan aquí
        const fallo = () => {
          if (pintor !== w) return;
          pintor = null;
          w.terminate();
          alFallar.forEach((fn) => fn());
        };
        w.addEventListener("error", fallo);
        w.addEventListener("messageerror", fallo);
        pintor = w;
      } catch {
        pintor = null;
      }
    }
  }
  return pintor;
}

/* Prepara el lienzo de una esfera una sola vez (los efectos pueden correr dos veces). Lo
   guarda en el propio lienzo: sobrevive a que este archivo se recargue en desarrollo */
function prepararLienzo(lienzo) {
  if (!lienzo.ondas) {
    const w = elPintor();
    if (w) {
      const off = lienzo.transferControlToOffscreen();
      lienzo.ondas = { pintor: w, clave: ++ultimaClave };
      w.postMessage({ alta: lienzo.ondas.clave, lienzo: off }, [off]);
    } else {
      lienzo.ondas = { ctx: lienzo.getContext("2d") };
    }
  }
  return lienzo.ondas;
}

/* Resolución del búfer del lienzo: escalones de √2 con histéresis, para no reasignarlo a
   cada rato mientras la esfera crece o se encoge. Nunca más de un 4 % más gruesa que lo
   que se ve: la esfera grande queda nítida */
function escalon(actual, ideal) {
  if (actual && ideal <= actual * 1.04 && ideal >= actual * 0.6) return actual;
  return Math.SQRT2 ** Math.ceil(2 * Math.log2(Math.max(ideal, 0.05)));
}

function nuevaFisica(body, desde, el) {
  const mood = body.mood in MOODS ? body.mood : "idle";
  return {
    px: desde ? desde.px : body.target.x * innerWidth,
    py: desde ? desde.py : body.target.y * innerHeight,
    // Al nacer de otra esfera sale disparada hacia su lugar: la mitosis se siente decidida
    vx: desde ? (body.target.x * innerWidth - desde.px) * 2.6 : 0,
    vy: desde ? (body.target.y * innerHeight - desde.py) * 2.6 : 0,
    // Nace a un tamaño cercano al suyo: las hijas del menú nacían a 0.7× de la esfera de la
    // sección (capas de ~730 px con el brillo desenfocado) para encogerse en pleno vuelo
    // Las que van a ser chicas nacen ya por debajo del umbral de es-chica (con la histéresis del tick)
    sc: desde ? Math.max(0.15, Math.min(desde.sc * 0.7, body.target.s * (body.target.s < 0.5 ? 1.15 : 1.3))) : body.target.s,
    edad: 0,
    cuadro: 0,
    vs: 0,
    cur: Object.fromEntries(NUM_KEYS.map((k) => [k, MOODS[mood][k]])),
    lab: Object.fromEntries(COLOR_KEYS.map((c) => [c, [...MOODS_LAB[mood][c]]])),
    fase: 0, // avance acumulado de las ondas
    fases: fasesIniciales(), // solo si las ondas se dibujan aquí (sin worker)
    gx: 0, gy: 0, svx: 0, svy: 0, stretch: 0,
    pop: 0, popVel: 0,
    breathePh: Math.random() * 6, pulsePh: 0, gradAng: Math.random() * 360,
    seed: Math.random() * 100,
    op: desde ? 1 : 1,
    // la clase es-chica ya viene del primer render (Esfera): el motor parte de lo que hay
    cache: { chica: el ? el.wrap.classList.contains("es-chica") : undefined },
  };
}

export default function OrbField({ controller, rootRef }) {
  const [ids, setIds] = useState(() => [...controller.state.bodies.keys()]);
  // sube si el worker de las ondas no cargó: las esferas se vuelven a montar con lienzos nuevos
  const [generacion, setGeneracion] = useState(0);
  useEffect(() => {
    const otra = () => setGeneracion((g) => g + 1);
    alFallar.add(otra);
    return () => alFallar.delete(otra);
  }, []);
  // Rótulos, cronómetros y la capa elevada: OrbField se vuelve a dibujar, pero cada Esfera
  // solo si cambió su `rev`
  const [, refrescar] = useReducer((n) => n + 1, 0);
  const nodes = useRef(new Map()); // id -> refs DOM
  const [registros] = useState(() => new Map()); // id -> función estable que guarda sus refs
  const gooRefs = useRef(new Map());
  const membranaRef = useRef(null);
  const nieblaRef = useRef(null);
  const ambienteRef = useRef(null);

  useEffect(() => controller.subscribe(() => {
    const nuevos = [...controller.state.bodies.keys()];
    setIds((prev) => (prev.length === nuevos.length && prev.every((id, i) => id === nuevos[i]) ? prev : nuevos));
    refrescar();
  }), [controller]);

  const registrar = (id) => {
    let fn = registros.get(id);
    if (!fn) {
      fn = (refs) => (refs ? nodes.current.set(id, refs) : nodes.current.delete(id));
      registros.set(id, fn);
    }
    return fn;
  };

  useEffect(() => {
    const root = rootRef.current;
    const bodies = controller.state.bodies;
    const fis = new Map();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const amb = {
      lab: Object.fromEntries(COLOR_KEYS.map((c) => [c, [...MOODS_LAB.idle[c]]])),
      fog: 1,
      cache: {}, // lo último escrito en .orb-ambient
      raiz: {}, // lo último escrito en la raíz
      nombre: null, // ánimo y tema con que se escribió la raíz
      tema: null,
    };
    const setVar = (el, cache, k, v) => {
      if (cache[k] !== v) { el.style.setProperty(k, v); cache[k] = v; }
    };
    // Modo claro: el mismo tinte del estado de ánimo, sobre papel
    const fondo = (bg, tema) => (tema === "claro" ? [0.965, bg[1] * 3, bg[2] * 3] : bg);
    const colores = (el, cache, lab, fog, tema) => {
      const a1 = oklabToRgb(lab.c1), a2 = oklabToRgb(lab.c2);
      setVar(el, cache, "--bg", rgb(oklabToRgb(fondo(lab.bg, tema))));
      setVar(el, cache, "--c1", rgb(a1));
      setVar(el, cache, "--c2", rgb(a2));
      setVar(el, cache, "--glow", rgba(a1, 0.5));
      setVar(el, cache, "--glowSoft", rgba(a2, 0.22));
      setVar(el, cache, "--fog", fog.toFixed(2));
    };

    const mouse = { x: innerWidth / 2, y: innerHeight / 2, active: false };
    let lastMove = performance.now();
    const onMove = (e) => { mouse.x = e.clientX; mouse.y = e.clientY; mouse.active = true; lastMove = performance.now(); };
    const onLeave = () => { mouse.active = false; };
    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerleave", onLeave);

    let last = performance.now(), time = 0, raf, cuadro = 0;
    const lotes = new Map(); // pintor -> parámetros de las ondas de este cuadro

    const tick = (now) => {
      const dt = Math.max(Math.min((now - last) / 1000, 0.05), 1e-4);
      // La membrana (filtro a pantalla completa) solo existe mientras hay mitosis o fusión
      const membrana = membranaRef.current;
      const conMembrana = now < (controller.state.membranaHasta ?? 0);
      if (membrana && membrana.style.display !== (conMembrana ? "" : "none")) membrana.style.display = conMembrana ? "" : "none";
      last = now;
      time += dt;
      const vw = innerWidth, vh = innerHeight;

      /* ---- ambiente (fondo y niebla) ---- */
      const ambName = controller.state.ambient in MOODS ? controller.state.ambient : "idle";
      const tema = root.dataset.tema;
      // Cambiar una variable de la raíz recalcula los estilos de toda la página: las tarjetas,
      // la barra y los velos pasan de una vez al tinte final, solo al cambiar el ánimo o el tema
      if (ambName !== amb.nombre || tema !== amb.tema) {
        amb.nombre = ambName;
        amb.tema = tema;
        colores(root, amb.raiz, MOODS_LAB[ambName], MOODS[ambName].fog, tema);
      }
      const kA = lerpK(dt, 2.6);
      for (const c of COLOR_KEYS) {
        const a = amb.lab[c], b = MOODS_LAB[ambName][c];
        for (let i = 0; i < 3; i++) a[i] += (b[i] - a[i]) * kA;
      }
      amb.fog += (MOODS[ambName].fog - amb.fog) * kA;
      // La transición suave se ve en la capa del ambiente (su fondo cubre la página) y solo
      // recalcula esa capa: a 30 Hz basta
      const ambiente = ambienteRef.current;
      if (ambiente && cuadro++ % 2 === 0) colores(ambiente, amb.cache, amb.lab, amb.fog, tema);
      const dpr = window.devicePixelRatio || 1;

      const idleFor = (now - lastMove) / 1000;
      const wander = mouse.active ? Math.min(1, Math.max(0, (idleFor - 2.5) / 1.5)) : 1;

      for (const [id, body] of bodies) {
        const el = nodes.current.get(id);
        let f = fis.get(id);
        if (!f) {
          f = nuevaFisica(body, body.spawnFrom ? fis.get(body.spawnFrom) : null, el);
          fis.set(id, f);
        }
        // Elementos nuevos para la misma esfera (se montó después, o se volvió a montar): lo
        // escrito en los anteriores no cuenta
        if (el && f.el !== el) {
          f.el = el;
          f.cache = { chica: el.wrap.classList.contains("es-chica") };
        }
        const mood = body.mood in MOODS ? body.mood : "idle";
        const tgt = MOODS[mood];

        /* ---- fusión: viaja al centro de la esfera destino y se encoge ---- */
        let tx = body.target.x * vw, ty = body.target.y * vh, ts = body.target.s;
        // vaivén lento a lo largo del borde: la esfera de la esquina nunca se queda quieta
        if (body.target.deriva && !reduced) ty += Math.sin(time * 0.16 + f.seed) * body.target.deriva * vh;
        if (body.fuseInto) {
          const dest = fis.get(body.fuseInto);
          if (dest) { tx = dest.px; ty = dest.py; ts = 0.05; }
          if (Math.hypot(f.px - tx, f.py - ty) < 14 || !dest) {
            fis.delete(id);
            const into = bodies.get(body.fuseInto);
            if (into) into.kick += 0.6;
            controller._remove(id);
            continue;
          }
        }

        const kN = lerpK(dt, 3.4), kC = lerpK(dt, 2.8);
        for (const k of NUM_KEYS) f.cur[k] += (tgt[k] - f.cur[k]) * kN;
        for (const c of COLOR_KEYS) {
          const a = f.lab[c], b = MOODS_LAB[mood][c];
          for (let i = 0; i < 3; i++) a[i] += (b[i] - a[i]) * kC;
        }

        // Resortes algo subamortiguados para que rebase y se asiente
        f.edad += dt;
        const joven = f.edad < 0.9;
        const k = body.fuseInto ? 120 : joven ? 95 : 70;
        const c = body.fuseInto ? 20 : joven ? 15 : 14;
        f.vx += (k * (tx - f.px) - c * f.vx) * dt;
        f.vy += (k * 0.8 * (ty - f.py) - c * 0.95 * f.vy) * dt;
        f.px += f.vx * dt;
        f.py += f.vy * dt;
        f.vs += ((joven || body.fuseInto ? 110 : 90) * (ts - f.sc) - (joven || body.fuseInto ? 14 : 12) * f.vs) * dt;
        f.sc = Math.max(0, f.sc + f.vs * dt);

        if (!el) continue;
        const cur = f.cur;
        const travel = Math.hypot(f.vx, f.vy);
        const travelN = Math.min(1, travel / 1600);
        const lift = body.fuseInto ? 0 : -Math.min(110, Math.abs(f.vx) * 0.045);
        const fx = reduced ? 0 : Math.sin(time * 0.47 + f.seed) * 8 + Math.sin(time * 1.13 + 2 + f.seed) * 3;
        const fy = reduced ? 0 : Math.sin(time * 0.71 + 1 + f.seed) * 10 + Math.cos(time * 1.37 + f.seed) * 3;

        // Mirada: hacia el cursor (relativo a cada esfera) o curioseando
        const ocx = vw / 2 + f.px, ocy = vh / 2 + f.py;
        const wanderX = Math.sin(time * 0.31 + f.seed) * 0.22 + Math.sin(time * 0.83 + 1.3) * 0.08;
        const wanderY = Math.cos(time * 0.27 + f.seed) * 0.14 + Math.sin(time * 0.61) * 0.06;
        const mx = Math.max(-0.55, Math.min(0.55, (mouse.x - ocx) / vw));
        const my = Math.max(-0.55, Math.min(0.55, (mouse.y - ocy) / vh));
        let lx = mx * (1 - wander) + wanderX * wander;
        let ly = my * (1 - wander) + wanderY * wander;
        if (controller.state.shy && id === "core") { lx = -Math.sign(mx || 1) * 0.42; ly = -0.36; }

        const pgx = f.gx, pgy = f.gy;
        const km = lerpK(dt, 4);
        f.gx += (lx - f.gx) * km;
        f.gy += (ly - f.gy) * km;
        const kv = lerpK(dt, 8);
        f.svx += ((f.gx - pgx) / dt - f.svx) * kv;
        f.svy += ((f.gy - pgy) / dt - f.svy) * kv;
        const vxT = f.svx + f.vx / 1300, vyT = f.svy + (f.vy + lift * 2) / 1300;
        const stretchTgt = Math.min(0.22, Math.hypot(vxT, vyT) * 0.09);
        f.stretch += (stretchTgt - f.stretch) * lerpK(dt, 10);
        const ang = Math.atan2(vyT, vxT);

        f.breathePh += dt * (1.2 + cur.speed * 0.25 + (body.active ? 1.2 : 0));
        f.pulsePh += dt * 2.6;
        const breath = Math.sin(f.breathePh) * (cur.breathe + (body.active ? 0.03 : 0));
        if (body.kick) { f.popVel += body.kick; body.kick = 0; }
        f.popVel += (-60 * f.pop - 7 * f.popVel) * dt;
        f.pop += f.popVel * dt;

        const wx = cur.wobble * (Math.sin(time * 6.1) * 3 + Math.sin(time * 9.7) * 1.5);
        const wy = cur.wobble * Math.cos(time * 7.3) * 2;

        const sx = f.px + fx + f.gx * 24 + wx;
        const sy = f.py + fy + lift + f.gy * 20 + wy;
        const escala = f.sc * cur.scale;

        // Atenuada cuando no es su turno
        const opT = body.dim ? 0.72 : 1;
        f.op += (opT - f.op) * lerpK(dt, 4);

        el.wrap.style.transform = `translate3d(${sx.toFixed(2)}px, ${sy.toFixed(2)}px, 0)`;
        el.wrap.style.opacity = f.op.toFixed(3);
        // con histéresis: cerca del umbral (al nacer, al rebotar) no alterna la clase cuadro a cuadro
        const chica = escala < (f.cache.chica ? 0.56 : 0.5);
        if (f.cache.chica !== chica) { el.wrap.classList.toggle("es-chica", chica); f.cache.chica = chica; }
        // Sin inclinación 3D: obligaba a recortar la esfera con una máscara en cada cuadro
        el.scene.style.transform = `scale(${escala.toFixed(4)}) rotate(${(f.vx * 0.004).toFixed(2)}deg)`;
        if (el.label) el.label.style.transform = `translate(-50%, ${(escala * 128 + 14).toFixed(1)}px)`;
        if (el.reloj) el.reloj.style.transform = `translate(-50%, calc(-100% - ${(escala * 128 + 10).toFixed(1)}px))`;

        const s = 1 + breath + f.pop;
        el.orb.style.transform =
          `translate(${(f.gx * 12).toFixed(2)}px, ${(f.gy * 10).toFixed(2)}px) rotate(${ang.toFixed(3)}rad) ` +
          `scale(${(s * (1 + f.stretch)).toFixed(4)}, ${(s * (1 - f.stretch * 0.7)).toFixed(4)}) rotate(${(-ang).toFixed(3)}rad)`;
        // El brillo sigue la mirada moviéndose como capa: cambiar el fondo de la esfera la
        // repintaría entera (con sus sombras grandes) en cada cuadro
        el.spec.style.transform = `translate(${(f.gx * 74).toFixed(1)}px, ${(f.gy * 74).toFixed(1)}px)`;

        // Colores propios de esta esfera. Cada cambio re-rasteriza sus sombras desenfocadas
        // grandes: mientras cambian se escriben a lo más a 20 Hz (el valor final siempre queda)
        if (f.tColores === undefined || now - f.tColores >= 45) {
          f.tColores = now;
          const c1 = oklabToRgb(f.lab.c1), c2 = oklabToRgb(f.lab.c2);
          f.c1s = rgb(c1);
          f.c2s = rgb(c2);
          setVar(el.wrap, f.cache, "--c1", f.c1s);
          setVar(el.wrap, f.cache, "--c2", f.c2s);
          setVar(el.wrap, f.cache, "--glow", rgba(c1, 0.5));
          setVar(el.wrap, f.cache, "--glowSoft", rgba(c2, 0.22));
          setVar(el.wrap, f.cache, "--rim", rgba(c1, 0.42));
          setVar(el.wrap, f.cache, "--glowOp", (cur.glow + (body.active ? 0.15 : 0)).toFixed(3));
        }
        f.gradAng = (f.gradAng + dt * (14 + cur.speed * 10)) % 360;

        el.shadow.style.transform =
          `translate(${(f.gx * 18).toFixed(2)}px, ${(-lift * 0.6).toFixed(2)}px) scale(${(1 - breath * 1.6 - f.pop * 0.8 + lift * 0.003).toFixed(4)}, 1)`;

        // Membrana de la mitosis (solo mientras se ve)
        const goo = conMembrana && gooRefs.current.get(id);
        if (goo) {
          goo.setAttribute("cx", (vw / 2 + sx).toFixed(1));
          goo.setAttribute("cy", (vh / 2 + sy).toFixed(1));
          goo.setAttribute("r", Math.max(0, escala * 104 * (1 + f.pop * 0.5)).toFixed(1));
          goo.setAttribute("opacity", f.op.toFixed(2));
        }

        if (id === "core") {
          // La niebla sigue a la esfera moviéndose como capa (sin repintar el desenfoque
          // ni recalcular estilos de toda la página)
          if (nieblaRef.current) {
            f.niebla = f.niebla ?? { x: vw / 2 + sx, y: vh / 2 + sy };
            const kf = lerpK(dt, 1.2);
            f.niebla.x += (vw / 2 + sx - f.niebla.x) * kf;
            f.niebla.y += (vh / 2 + sy - f.niebla.y) * kf;
            nieblaRef.current.style.transform = `translate3d(${(f.niebla.x + vw * 0.1).toFixed(0)}px, ${(f.niebla.y + vh * 0.1).toFixed(0)}px, 0) translate(-50%, -50%)`;
          }
        }

        // Ondas: concéntricas a la esfera; se agitan mientras viaja o trabaja
        f.cuadro++;
        f.dtOndas = (f.dtOndas ?? 0) + dt;
        // Las ondas de las esferas atenuadas, chicas o en reposo (sin viajar, sin trabajar, sin
        // rebotar) se redibujan a 30 Hz: no se nota y cuesta la mitad. En los cuadros que se
        // saltan no se escribe nada
        const reposo = !body.active && travelN < 0.02 && Math.abs(f.popVel) < 0.3;
        if ((body.dim || chica || reposo) && f.cuadro % 2) continue;
        const pulseMul = 1 + cur.pulse * 0.35 * (0.5 + 0.5 * Math.sin(f.pulsePh));
        const activo = body.active ? 0.5 : 0;
        f.fase += f.dtOndas * cur.speed * (1 + travelN * 1.6 + activo * 1.6);
        f.dtOndas = 0;
        // El búfer sigue la escala con que se ve la esfera (la escena se escala con transform)
        f.nivel = escalon(f.nivel, escala * dpr);
        const p = {
          lado: Math.min(LADO_MAX, Math.max(16, Math.round(LIENZO * f.nivel))),
          fase: f.fase,
          radScale: 1 + breath * 0.85 + f.pop * 0.9,
          ampPx: AMP_PX * cur.amp * pulseMul * (1 + travelN * 1.1 + activo),
          turb: Math.min(1, cur.turbulence + travelN * 0.5 + activo * 0.4),
          cx: 200 + f.gx * 12,
          cy: 200 + f.gy * 10,
          giro: (f.gradAng * Math.PI) / 180,
          c1: f.c1s,
          c2: f.c2s,
        };
        const { ondas } = el;
        if (ondas.pintor) {
          p.clave = ondas.clave;
          let lote = lotes.get(ondas.pintor);
          if (!lote) lotes.set(ondas.pintor, (lote = []));
          lote.push(p);
        } else {
          dibujarOndas(el.lienzo, ondas.ctx, f.fases, p);
        }
      }
      // Un solo mensaje por cuadro con las ondas de todas las esferas
      for (const [w, lote] of lotes) w.postMessage({ cuadro: lote });
      lotes.clear();
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerleave", onLeave);
    };
  }, [controller, rootRef]);

  const bodies = controller.state.bodies;
  return (
    <>
      <div ref={ambienteRef} className="orb-ambient" aria-hidden="true">
        <div className="orb-fog a" />
        <div className="orb-fog b" />
        <div ref={nieblaRef} className="orb-fog c" />
      </div>
      <div className="orb-vignette" aria-hidden="true" />

      <div className={`orb-stage${controller.state.elevada ? " es-elevada" : ""}`} aria-hidden="true">
        <svg ref={membranaRef} className="orb-membrane" width="100%" height="100%" style={{ display: "none" }}>
          <defs>
            <filter id="orbMembrane" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="14" result="b" />
              <feColorMatrix in="b" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 26 -11" />
            </filter>
          </defs>
          <g filter="url(#orbMembrane)">
            {ids.map((id) => (
              <circle
                key={id}
                ref={(el) => (el ? gooRefs.current.set(id, el) : gooRefs.current.delete(id))}
                r="0"
                fill="#e4dac8"
              />
            ))}
          </g>
        </svg>
        {ids.map((id) => (
          <Esfera key={`${id}:${generacion}`} id={id} rev={bodies.get(id)?.rev ?? 0} bodies={bodies} registrar={registrar(id)} />
        ))}
      </div>
    </>
  );
}

/* ---------------------------------------------------------------- */

/* Tiempo transcurrido de un proceso: lo pone quien trabaja con orb.update(id, { desde: Date.now() }) */
export function Cronometro({ desde }) {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setAhora(Date.now()), 1000);
    return () => clearInterval(t);
  }, [desde]);
  const s = Math.max(0, Math.floor((ahora - desde) / 1000));
  const m = Math.floor(s / 60);
  return <span className="orb-reloj-t">{`${m > 59 ? `${Math.floor(m / 60)}:` : ""}${String(m % 60).padStart(m > 59 ? 2 : 1, "0")}:${String(s % 60).padStart(2, "0")}`}</span>;
}

/* Lo que React dibuja de una esfera. Se vuelve a dibujar solo cuando cambia su `rev`
   (rótulos, cronómetro, si se puede tocar); todo lo demás lo mueve el motor */
const Esfera = memo(function Esfera({ id, bodies, registrar }) {
  const body = bodies.get(id);
  const wrap = useRef(null), scene = useRef(null), orb = useRef(null), shadow = useRef(null), label = useRef(null), spec = useRef(null), reloj = useRef(null);
  const lienzo = useRef(null);
  // Las que nacen chicas (las del menú) no pintan ni un cuadro el brillo desenfocado ni las
  // sombras grandes; después la clase la lleva el motor
  const [nacioChica] = useState(() => (body?.target?.s ?? 1) < 0.5);

  useEffect(() => {
    if (!wrap.current) return undefined;
    const c = lienzo.current;
    registrar({
      wrap: wrap.current,
      scene: scene.current,
      orb: orb.current,
      shadow: shadow.current,
      label: label.current,
      reloj: reloj.current,
      spec: spec.current,
      lienzo: c,
      ondas: prepararLienzo(c),
    });
    return () => {
      registrar(null);
      // Desmontada de verdad (no la segunda pasada del modo estricto): el lienzo ya salió del
      // documento y el worker lo suelta
      if (c.ondas.pintor && !c.isConnected) c.ondas.pintor.postMessage({ baja: c.ondas.clave });
    };
  }, [registrar]);

  if (!body) return null;
  return (
    <div ref={wrap} className={`orb-body${nacioChica ? " es-chica" : ""}`}>
      <div ref={scene} className="orb-scene">
        <div ref={shadow} className="orb-shadow" />
        {/* Las ondas (manchas y anillos) se dibujan en un lienzo: sin un <path> por onda que
            recalcular (estilos y caja) en cada cuadro */}
        <canvas ref={lienzo} className="orb-waves" />
        <div className="orb-backglow" />
        <div ref={orb} className={`orb-orbwrap${body.onClick ? " es-tocable" : ""}`} onClick={body.onClick}>
          <div className="orb-orb">
            <div className="orb-il il1" />
            <div className="orb-il il2" />
            <div ref={spec} className="orb-spec" />
          </div>
        </div>
      </div>
      <div ref={reloj} className={`orb-reloj${body.desde ? "" : " is-empty"}`} aria-hidden={!body.desde}>
        {body.desde && <Cronometro desde={body.desde} />}
      </div>
      <div ref={label} className={`orb-label${body.label ? "" : " is-empty"}`}>
        <span className="orb-label-name">{body.label}</span>
        {body.sub && <span className="orb-label-sub">{body.sub}</span>}
      </div>
    </div>
  );
});
