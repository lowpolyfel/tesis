import { useEffect, useId, useRef, useState } from "react";
import { oklabToRgb, rgb, rgba } from "./color";
import { MOODS, MOODS_LAB, NUM_KEYS, COLOR_KEYS } from "./moods";
import { HARMONICS, BLOBS, RINGS, SHAPES, AMP_PX, N, COS, SIN, ANG, smoothClosedPath } from "./geometry";
import "./orb.css";

/* =========================================================================
   OrbField — todas las esferas de Dudamel, vivas en toda la app.
   - La esfera principal viaja con resortes: rebasa un poco y se asienta
   - Al viajar describe un arco, se estira como gelatina y agita sus ondas
   - Mira al cursor; si lo dejas quieto, curiosea solo; flota siempre
   - Mitosis: una esfera se divide en otras que nacen dentro de ella; una
     membrana (capa "goo") las une mientras se separan y cuando se fusionan
   ========================================================================= */

const lerpK = (dt, rate) => 1 - Math.exp(-dt * rate);

function nuevaFisica(body, desde) {
  const mood = body.mood in MOODS ? body.mood : "idle";
  return {
    px: desde ? desde.px : body.target.x * innerWidth,
    py: desde ? desde.py : body.target.y * innerHeight,
    // Al nacer de otra esfera sale disparada hacia su lugar: la mitosis se siente decidida
    vx: desde ? (body.target.x * innerWidth - desde.px) * 2.6 : 0,
    vy: desde ? (body.target.y * innerHeight - desde.py) * 2.6 : 0,
    sc: desde ? Math.max(0.15, desde.sc * 0.7) : body.target.s,
    edad: 0,
    cuadro: 0,
    vs: 0,
    cur: Object.fromEntries(NUM_KEYS.map((k) => [k, MOODS[mood][k]])),
    lab: Object.fromEntries(COLOR_KEYS.map((c) => [c, [...MOODS_LAB[mood][c]]])),
    phases: SHAPES.map((s) => HARMONICS.map((_, j) => s.seed * (j + 1.3) + Math.random() * 6)),
    gx: 0, gy: 0, svx: 0, svy: 0, stretch: 0,
    pop: 0, popVel: 0,
    breathePh: Math.random() * 6, pulsePh: 0, gradAng: Math.random() * 360,
    seed: Math.random() * 100,
    op: desde ? 1 : 1,
    cache: {},
  };
}

export default function OrbField({ controller, rootRef }) {
  const [ids, setIds] = useState(() => [...controller.state.bodies.keys()]);
  const nodes = useRef(new Map()); // id -> refs DOM
  const gooRefs = useRef(new Map());
  const membranaRef = useRef(null);
  const nieblaRef = useRef(null);

  useEffect(() => controller.subscribe(() => setIds([...controller.state.bodies.keys()])), [controller]);

  useEffect(() => {
    const root = rootRef.current;
    const bodies = controller.state.bodies;
    const fis = new Map();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const amb = {
      lab: Object.fromEntries(COLOR_KEYS.map((c) => [c, [...MOODS_LAB.idle[c]]])),
      fog: 1,
      cache: {},
    };
    const setVar = (el, cache, k, v) => {
      if (cache[k] !== v) { el.style.setProperty(k, v); cache[k] = v; }
    };

    const mouse = { x: innerWidth / 2, y: innerHeight / 2, active: false };
    let lastMove = performance.now();
    const onMove = (e) => { mouse.x = e.clientX; mouse.y = e.clientY; mouse.active = true; lastMove = performance.now(); };
    const onLeave = () => { mouse.active = false; };
    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerleave", onLeave);

    const xs = new Float64Array(N), ys = new Float64Array(N);
    let last = performance.now(), time = 0, raf;

    const tick = (now) => {
      const dt = Math.max(Math.min((now - last) / 1000, 0.05), 1e-4);
      // La membrana (filtro a pantalla completa) solo existe mientras hay mitosis o fusión
      const membrana = membranaRef.current;
      if (membrana) {
        const visible = now < (controller.state.membranaHasta ?? 0);
        if (membrana.style.display !== (visible ? "" : "none")) membrana.style.display = visible ? "" : "none";
      }
      last = now;
      time += dt;
      const vw = innerWidth, vh = innerHeight;

      /* ---- ambiente (fondo y niebla) ---- */
      const ambName = controller.state.ambient in MOODS ? controller.state.ambient : "idle";
      const kA = lerpK(dt, 1.6);
      for (const c of COLOR_KEYS) {
        const a = amb.lab[c], b = MOODS_LAB[ambName][c];
        for (let i = 0; i < 3; i++) a[i] += (b[i] - a[i]) * kA;
      }
      amb.fog += (MOODS[ambName].fog - amb.fog) * kA;
      const a1 = oklabToRgb(amb.lab.c1), a2 = oklabToRgb(amb.lab.c2);
      setVar(root, amb.cache, "--bg", rgb(oklabToRgb(amb.lab.bg)));
      setVar(root, amb.cache, "--c1", rgb(a1));
      setVar(root, amb.cache, "--c2", rgb(a2));
      setVar(root, amb.cache, "--glow", rgba(a1, 0.5));
      setVar(root, amb.cache, "--glowSoft", rgba(a2, 0.22));
      setVar(root, amb.cache, "--fog", amb.fog.toFixed(3));

      const idleFor = (now - lastMove) / 1000;
      const wander = mouse.active ? Math.min(1, Math.max(0, (idleFor - 2.5) / 1.5)) : 1;

      for (const [id, body] of bodies) {
        let f = fis.get(id);
        if (!f) {
          f = nuevaFisica(body, body.spawnFrom ? fis.get(body.spawnFrom) : null);
          fis.set(id, f);
        }
        const el = nodes.current.get(id);
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

        const kN = lerpK(dt, 2.4), kC = lerpK(dt, 1.8);
        for (const k of NUM_KEYS) f.cur[k] += (tgt[k] - f.cur[k]) * kN;
        for (const c of COLOR_KEYS) {
          const a = f.lab[c], b = MOODS_LAB[mood][c];
          for (let i = 0; i < 3; i++) a[i] += (b[i] - a[i]) * kC;
        }

        // Resortes algo subamortiguados para que rebase y se asiente
        f.edad += dt;
        const joven = f.edad < 0.9;
        const k = body.fuseInto ? 120 : joven ? 95 : 40;
        const c = body.fuseInto ? 20 : joven ? 15 : 10.5;
        f.vx += (k * (tx - f.px) - c * f.vx) * dt;
        f.vy += (k * 0.8 * (ty - f.py) - c * 0.95 * f.vy) * dt;
        f.px += f.vx * dt;
        f.py += f.vy * dt;
        f.vs += ((joven || body.fuseInto ? 110 : 55) * (ts - f.sc) - (joven || body.fuseInto ? 14 : 9) * f.vs) * dt;
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
        const chica = escala < 0.5;
        if (f.cache.chica !== chica) { el.wrap.classList.toggle("es-chica", chica); f.cache.chica = chica; }
        el.scene.style.transform =
          `scale(${escala.toFixed(4)}) rotateX(${(-f.gy * 3.5).toFixed(2)}deg) rotateY(${(f.gx * 4).toFixed(2)}deg) rotate(${(f.vx * 0.004).toFixed(2)}deg)`;
        if (el.label) el.label.style.transform = `translate(-50%, ${(escala * 128 + 14).toFixed(1)}px)`;

        const s = 1 + breath + f.pop;
        el.orb.style.transform =
          `translate(${(f.gx * 12).toFixed(2)}px, ${(f.gy * 10).toFixed(2)}px) rotate(${ang.toFixed(3)}rad) ` +
          `scale(${(s * (1 + f.stretch)).toFixed(4)}, ${(s * (1 - f.stretch * 0.7)).toFixed(4)}) rotate(${(-ang).toFixed(3)}rad)`;
        el.orb.style.setProperty("--hx", `${(36 + f.gx * 34).toFixed(1)}%`);
        el.orb.style.setProperty("--hy", `${(28 + f.gy * 34).toFixed(1)}%`);

        // Colores propios de esta esfera
        const c1 = oklabToRgb(f.lab.c1), c2 = oklabToRgb(f.lab.c2);
        const c1s = rgb(c1), c2s = rgb(c2);
        setVar(el.wrap, f.cache, "--c1", c1s);
        setVar(el.wrap, f.cache, "--c2", c2s);
        setVar(el.wrap, f.cache, "--glow", rgba(c1, 0.5));
        setVar(el.wrap, f.cache, "--glowSoft", rgba(c2, 0.22));
        setVar(el.wrap, f.cache, "--rim", rgba(c1, 0.42));
        setVar(el.wrap, f.cache, "--glowOp", (cur.glow + (body.active ? 0.15 : 0)).toFixed(3));
        if (f.cache.stops !== c1s + c2s) {
          for (const st of el.stops) st.setAttribute("stop-color", st.dataset.c === "c1" ? c1s : c2s);
          f.cache.stops = c1s + c2s;
        }
        f.gradAng = (f.gradAng + dt * (14 + cur.speed * 10)) % 360;
        const rot = `rotate(${f.gradAng.toFixed(2)} .5 .5)`;
        for (const g of el.rotGrads) g.setAttribute("gradientTransform", rot);

        el.shadow.style.transform =
          `translate(${(f.gx * 18).toFixed(2)}px, ${(-lift * 0.6).toFixed(2)}px) scale(${(1 - breath * 1.6 - f.pop * 0.8 + lift * 0.003).toFixed(4)}, 1)`;

        // Membrana de la mitosis
        const goo = gooRefs.current.get(id);
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
        const pulseMul = 1 + cur.pulse * 0.35 * (0.5 + 0.5 * Math.sin(f.pulsePh));
        const radScale = 1 + breath * 0.85 + f.pop * 0.9;
        const activo = body.active ? 0.5 : 0;
        const ampMul = 1 + travelN * 1.1 + activo;
        const speedMul = 1 + travelN * 1.6 + activo * 1.6;
        const cx = 200 + f.gx * 12, cy = 200 + f.gy * 10;
        f.cuadro++;
        const saltar = body.dim && f.cuadro % 2;
        for (let si = 0; si < SHAPES.length && !saltar; si++) {
          const shape = SHAPES[si], ph = f.phases[si];
          for (let h = 0; h < HARMONICS.length; h++) ph[h] += dt * HARMONICS[h].rate * cur.speed * speedMul * shape.speedK;
          const ampPx = AMP_PX * shape.ampK * cur.amp * pulseMul * ampMul;
          const turb = Math.min(1, cur.turbulence + travelN * 0.5 + activo * 0.4);
          const base = shape.r * radScale;
          for (let i = 0; i < N; i++) {
            let r = base;
            for (let h = 0; h < HARMONICS.length; h++) {
              const H = HARMONICS[h];
              const w = H.turb ? H.w * turb : H.w;
              if (w > 0.001) r += Math.sin(ANG[i] * H.k + ph[h]) * ampPx * w;
            }
            xs[i] = cx + COS[i] * r;
            ys[i] = cy + SIN[i] * r;
          }
          el.paths[si]?.setAttribute("d", smoothClosedPath(xs, ys));
        }
      }
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
      <div className="orb-ambient" aria-hidden="true">
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
          <Esfera key={id} body={bodies.get(id)} registrar={(refs) => (refs ? nodes.current.set(id, refs) : nodes.current.delete(id))} />
        ))}
      </div>
    </>
  );
}

/* ---------------------------------------------------------------- */

function Esfera({ body, registrar }) {
  const uid = useId().replace(/:/g, "");
  const wrap = useRef(null), scene = useRef(null), orb = useRef(null), shadow = useRef(null), label = useRef(null);
  const paths = useRef([]);
  const svg = useRef(null);

  useEffect(() => {
    registrar({
      wrap: wrap.current,
      scene: scene.current,
      orb: orb.current,
      shadow: shadow.current,
      label: label.current,
      paths: paths.current,
      stops: [...svg.current.querySelectorAll("stop[data-c]")],
      rotGrads: [...svg.current.querySelectorAll("[data-rot]")],
    });
    return () => registrar(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!body) return null;
  const g = (n) => `${uid}${n}`;
  return (
    <div ref={wrap} className="orb-body">
      <div ref={scene} className="orb-scene">
        <div ref={shadow} className="orb-shadow" />
        <svg ref={svg} className="orb-waves" viewBox="0 0 400 400">
          <defs>
            <linearGradient id={g("A")} data-rot="">
              <stop offset="0" data-c="c1" /><stop offset=".5" data-c="c2" /><stop offset="1" data-c="c1" />
            </linearGradient>
            <linearGradient id={g("B")} data-rot="">
              <stop offset="0" data-c="c2" /><stop offset=".5" data-c="c1" /><stop offset="1" data-c="c2" />
            </linearGradient>
            <linearGradient id={g("F")} data-rot="">
              <stop offset="0" data-c="c1" /><stop offset="1" data-c="c2" />
            </linearGradient>
            <filter id={g("Goo")} x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="7" result="blur" />
              <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -8" result="goo" />
              <feGaussianBlur in="goo" stdDeviation="1.2" />
            </filter>
            <filter id={g("Soft")} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2" />
            </filter>
          </defs>
          <g filter={`url(#${g("Goo")})`} opacity=".42">
            {BLOBS.map((_, i) => (
              <path key={`b${i}`} ref={(el) => (paths.current[i] = el)} fill={`url(#${g("F")})`} />
            ))}
          </g>
          <g>
            {RINGS.map((ring, i) => (
              <path
                key={`r${i}`}
                ref={(el) => (paths.current[BLOBS.length + i] = el)}
                fill="none"
                stroke={`url(#${g(ring.grad)})`}
                strokeWidth={ring.width}
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={ring.opacity}
                filter={ring.soft ? `url(#${g("Soft")})` : undefined}
              />
            ))}
          </g>
        </svg>
        <div className="orb-backglow" />
        <div ref={orb} className={`orb-orbwrap${body.onClick ? " es-tocable" : ""}`} onClick={body.onClick}>
          <div className="orb-orb">
            <div className="orb-il il1" />
            <div className="orb-il il2" />
            <div className="orb-spec" />
          </div>
        </div>
      </div>
      <div ref={label} className={`orb-label${body.label ? "" : " is-empty"}`}>
        <span className="orb-label-name">{body.label}</span>
        {body.sub && <span className="orb-label-sub">{body.sub}</span>}
      </div>
    </div>
  );
}
