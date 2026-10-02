import { useEffect, useRef } from "react";
import { oklabToRgb, rgb, rgba } from "./color";
import { MOODS, MOODS_LAB, NUM_KEYS, COLOR_KEYS } from "./moods";
import { HARMONICS, BLOBS, RINGS, SHAPES, AMP_PX, N, COS, SIN, ANG, smoothClosedPath } from "./geometry";
import "./orb.css";

/* =========================================================================
   Orb — orbe blanco hueso con halo de ondas líquidas, vivo en toda la app.
   - Viaja por la pantalla con un resorte: rebasa un poco y se asienta
   - Al viajar describe un arco, se estira como gelatina y agita sus ondas
   - Mira al cursor; si lo dejas quieto, curiosea solo
   - Flota siempre, aunque nadie lo mueva
   ========================================================================= */

export default function Orb({ controller, rootRef }) {
  const sceneRef = useRef(null);
  const orbRef = useRef(null);
  const shadowRef = useRef(null);
  const svgRef = useRef(null);
  const pathRefs = useRef([]);

  useEffect(() => {
    const root = rootRef.current;
    const scene = sceneRef.current;
    const orb = orbRef.current;
    const shadow = shadowRef.current;
    const ctl = controller.state;
    const stops = [...svgRef.current.querySelectorAll("stop[data-c]")];
    const rotGrads = [...svgRef.current.querySelectorAll("[data-rot]")];
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const cur = Object.fromEntries(NUM_KEYS.map((k) => [k, MOODS.idle[k]]));
    const lab = Object.fromEntries(COLOR_KEYS.map((c) => [c, [...MOODS_LAB.idle[c]]]));
    const phases = SHAPES.map((s) => HARMONICS.map((_, j) => s.seed * (j + 1.3)));

    const cssCache = {};
    const setVar = (k, v) => {
      if (cssCache[k] !== v) { root.style.setProperty(k, v); cssCache[k] = v; }
    };
    let lastC1 = "", lastC2 = "";

    const mouse = { x: innerWidth / 2, y: innerHeight / 2, active: false };
    let lastMove = performance.now();
    const onMove = (e) => {
      mouse.x = e.clientX; mouse.y = e.clientY; mouse.active = true;
      lastMove = performance.now();
    };
    const onLeave = () => { mouse.active = false; };
    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerleave", onLeave);

    const xs = new Float64Array(N), ys = new Float64Array(N);
    let last = performance.now(), time = 0;
    let breathePh = 0, pulsePh = 0, gradAng = 0, pop = 0, popVel = 0;
    let gx = 0, gy = 0, svx = 0, svy = 0, stretch = 0;
    // Viaje por la pantalla (px desde el centro) y escala, ambos con resorte
    let px = 0, py = 0, vx = 0, vy = 0, sc = ctl.pose.s, vs = 0;
    let raf;

    const tick = (now) => {
      const dt = Math.max(Math.min((now - last) / 1000, 0.05), 1e-4);
      last = now;
      time += dt;

      const name = ctl.mood;
      const tgt = MOODS[name];
      const vw = innerWidth, vh = innerHeight;

      const kN = 1 - Math.exp(-dt * 2.4);
      const kC = 1 - Math.exp(-dt * 1.8);
      for (const k of NUM_KEYS) cur[k] += (tgt[k] - cur[k]) * kN;
      for (const c of COLOR_KEYS) {
        const a = lab[c], b = MOODS_LAB[name][c];
        for (let i = 0; i < 3; i++) a[i] += (b[i] - a[i]) * kC;
      }

      const c1 = oklabToRgb(lab.c1), c2 = oklabToRgb(lab.c2), bg = oklabToRgb(lab.bg);
      const c1s = rgb(c1), c2s = rgb(c2);
      setVar("--c1", c1s);
      setVar("--c2", c2s);
      setVar("--bg", rgb(bg));
      setVar("--glow", rgba(c1, 0.5));
      setVar("--glowSoft", rgba(c2, 0.22));
      setVar("--rim", rgba(c1, 0.42));
      setVar("--fog", cur.fog.toFixed(3));
      setVar("--glowOp", cur.glow.toFixed(3));
      if (c1s !== lastC1 || c2s !== lastC2) {
        for (const s of stops) s.setAttribute("stop-color", s.dataset.c === "c1" ? c1s : c2s);
        lastC1 = c1s; lastC2 = c2s;
      }

      /* ---- viaje: resortes algo subamortiguados para que rebase y se asiente ---- */
      const tx = ctl.pose.x * vw, ty = ctl.pose.y * vh;
      vx += (40 * (tx - px) - 10.5 * vx) * dt;
      vy += (30 * (ty - py) - 9.5 * vy) * dt;
      px += vx * dt;
      py += vy * dt;
      vs += (55 * (ctl.pose.s - sc) - 9 * vs) * dt;
      sc = Math.max(0, sc + vs * dt);

      const travel = Math.hypot(vx, vy);
      const travelN = Math.min(1, travel / 1600);
      // Al cruzar de lado a lado salta en arco, no en línea recta
      const lift = -Math.min(110, Math.abs(vx) * 0.045);
      // Flotación perpetua
      const fx = reduced ? 0 : Math.sin(time * 0.47) * 8 + Math.sin(time * 1.13 + 2) * 3;
      const fy = reduced ? 0 : Math.sin(time * 0.71 + 1) * 10 + Math.cos(time * 1.37) * 3;

      /* ---- mirada: hacia el cursor (relativo al propio orbe) o curioseando ---- */
      const ocx = vw / 2 + px, ocy = vh / 2 + py;
      const idleFor = (now - lastMove) / 1000;
      const wander = mouse.active ? Math.min(1, Math.max(0, (idleFor - 2.5) / 1.5)) : 1;
      const wanderX = Math.sin(time * 0.31) * 0.22 + Math.sin(time * 0.83 + 1.3) * 0.08;
      const wanderY = Math.cos(time * 0.27) * 0.14 + Math.sin(time * 0.61) * 0.06;
      const mx = Math.max(-0.55, Math.min(0.55, (mouse.x - ocx) / vw));
      const my = Math.max(-0.55, Math.min(0.55, (mouse.y - ocy) / vh));
      let lx = mx * (1 - wander) + wanderX * wander;
      let ly = my * (1 - wander) + wanderY * wander;
      // Tímido: aparta la mirada hacia arriba, lejos del cursor
      if (ctl.shy) { lx = -Math.sign(mx || 1) * 0.42; ly = -0.36; }

      const pgx = gx, pgy = gy;
      const km = 1 - Math.exp(-dt * 4);
      gx += (lx - gx) * km;
      gy += (ly - gy) * km;

      // Velocidad (mirada + viaje) → estiramiento gelatinoso en la dirección del movimiento
      const kv = 1 - Math.exp(-dt * 8);
      svx += ((gx - pgx) / dt - svx) * kv;
      svy += ((gy - pgy) / dt - svy) * kv;
      const vxT = svx + vx / 1300, vyT = svy + (vy + lift * 2) / 1300;
      const stretchTgt = Math.min(0.2, Math.hypot(vxT, vyT) * 0.09);
      stretch += (stretchTgt - stretch) * (1 - Math.exp(-dt * 10));
      const ang = Math.atan2(vyT, vxT);

      breathePh += dt * (1.2 + cur.speed * 0.25);
      pulsePh += dt * 2.6;
      const breath = Math.sin(breathePh) * cur.breathe;
      if (ctl.kick) { popVel += ctl.kick; ctl.kick = 0; }
      popVel += (-60 * pop - 7 * popVel) * dt;
      pop += popVel * dt;

      const wx = cur.wobble * (Math.sin(time * 6.1) * 3 + Math.sin(time * 9.7) * 1.5);
      const wy = cur.wobble * Math.cos(time * 7.3) * 2;

      const sx = px + fx + gx * 24 + wx;
      const sy = py + fy + lift + gy * 20 + wy;
      scene.style.transform =
        `translate3d(${sx.toFixed(2)}px, ${sy.toFixed(2)}px, 0) ` +
        `scale(${(sc * cur.scale).toFixed(4)}) rotateX(${(-gy * 3.5).toFixed(2)}deg) rotateY(${(gx * 4).toFixed(2)}deg) ` +
        `rotate(${(vx * 0.004).toFixed(2)}deg)`;
      setVar("--orbx", `${(vw / 2 + sx).toFixed(0)}px`);
      setVar("--orby", `${(vh / 2 + sy).toFixed(0)}px`);

      const s = 1 + breath + pop;
      orb.style.transform =
        `translate(${(gx * 12).toFixed(2)}px, ${(gy * 10).toFixed(2)}px) rotate(${ang.toFixed(3)}rad) ` +
        `scale(${(s * (1 + stretch)).toFixed(4)}, ${(s * (1 - stretch * 0.7)).toFixed(4)}) rotate(${(-ang).toFixed(3)}rad)`;
      orb.style.setProperty("--hx", `${(36 + gx * 34).toFixed(1)}%`);
      orb.style.setProperty("--hy", `${(28 + gy * 34).toFixed(1)}%`);

      gradAng = (gradAng + dt * (14 + cur.speed * 10)) % 360;
      const rot = `rotate(${gradAng.toFixed(2)} .5 .5)`;
      for (const g of rotGrads) g.setAttribute("gradientTransform", rot);

      shadow.style.transform =
        `translate(${(gx * 18).toFixed(2)}px, ${(-lift * 0.6).toFixed(2)}px) ` +
        `scale(${(1 - breath * 1.6 - pop * 0.8 + lift * 0.003).toFixed(4)}, 1)`;

      /* ---- ondas: concéntricas al orbe; se agitan mientras viaja ---- */
      const pulseMul = 1 + cur.pulse * 0.35 * (0.5 + 0.5 * Math.sin(pulsePh));
      const radScale = 1 + breath * 0.85 + pop * 0.9;
      const ampMul = 1 + travelN * 1.1;
      const speedMul = 1 + travelN * 1.6;
      const cx = 200 + gx * 12, cy = 200 + gy * 10;

      for (let si = 0; si < SHAPES.length; si++) {
        const shape = SHAPES[si], ph = phases[si];
        for (let h = 0; h < HARMONICS.length; h++) {
          ph[h] += dt * HARMONICS[h].rate * cur.speed * speedMul * shape.speedK;
        }
        const ampPx = AMP_PX * shape.ampK * cur.amp * pulseMul * ampMul;
        const turb = Math.min(1, cur.turbulence + travelN * 0.5);
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
        pathRefs.current[si]?.setAttribute("d", smoothClosedPath(xs, ys));
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

  return (
    <>
      <div className="orb-ambient" aria-hidden="true">
        <div className="orb-fog a" />
        <div className="orb-fog b" />
        <div className="orb-fog c" />
      </div>
      <div className="orb-vignette" aria-hidden="true" />

      <div className="orb-stage" aria-hidden="true">
        <div ref={sceneRef} className="orb-scene">
          <div ref={shadowRef} className="orb-shadow" />

          <svg ref={svgRef} className="orb-waves" viewBox="0 0 400 400">
            <defs>
              <linearGradient id="orbGradA" data-rot="">
                <stop offset="0" data-c="c1" />
                <stop offset=".5" data-c="c2" />
                <stop offset="1" data-c="c1" />
              </linearGradient>
              <linearGradient id="orbGradB" data-rot="">
                <stop offset="0" data-c="c2" />
                <stop offset=".5" data-c="c1" />
                <stop offset="1" data-c="c2" />
              </linearGradient>
              <linearGradient id="orbGradFill" data-rot="">
                <stop offset="0" data-c="c1" />
                <stop offset="1" data-c="c2" />
              </linearGradient>
              <filter id="orbGoo" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur in="SourceGraphic" stdDeviation="7" result="blur" />
                <feColorMatrix in="blur" mode="matrix"
                  values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -8" result="goo" />
                <feGaussianBlur in="goo" stdDeviation="1.2" />
              </filter>
              <filter id="orbSoft" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="2" />
              </filter>
            </defs>

            <g filter="url(#orbGoo)" opacity=".42">
              {BLOBS.map((_, i) => (
                <path key={`b${i}`} ref={(el) => (pathRefs.current[i] = el)} fill="url(#orbGradFill)" />
              ))}
            </g>
            <g>
              {RINGS.map((ring, i) => (
                <path
                  key={`r${i}`}
                  ref={(el) => (pathRefs.current[BLOBS.length + i] = el)}
                  fill="none"
                  stroke={`url(#orbGrad${ring.grad})`}
                  strokeWidth={ring.width}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity={ring.opacity}
                  filter={ring.soft ? "url(#orbSoft)" : undefined}
                />
              ))}
            </g>
          </svg>

          <div className="orb-backglow" />

          <div ref={orbRef} className="orb-orbwrap">
            <div className="orb-orb">
              <div className="orb-il il1" />
              <div className="orb-il il2" />
              <div className="orb-spec" />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
