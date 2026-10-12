import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useOrb } from "../components/orb/useOrb";
import { isMobile } from "../components/orb/poses";
import { cargarModelo, prepararAnalisis, salud } from "../services/backend";

/*
 * Antes de la escena: la esfera grande al centro revisa, paso a paso, que todo esté
 * listo (el servidor, la base de datos, Ollama y cada modelo del análisis) y deja en
 * memoria los modelos que no lo estaban (GET /preparacion, POST /preparacion/cargar).
 * Si algo falla lo dice: se puede reintentar o seguir de todos modos.
 */
const MIN_MS = 380; // cada paso se alcanza a leer, aunque responda al instante
const espera = (ms) => new Promise((r) => setTimeout(r, ms));
const BASE = { atlas: "MongoDB Atlas", local: "Mongo local", otro: "MongoDB", json: "archivos JSON" };
const ROL = { extractor: "Extractor", clasificador: "Clasificador", critico: "Crítico", modelador: "Modelador", embeddings: "similitud" };
const lista = (xs) => (xs.length > 1 ? `${xs.slice(0, -1).join(", ")} y ${xs.at(-1)}` : xs[0] ?? "");
const segundos = (ms) => (ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`);

export default function Preparacion({ proyecto, onListo }) {
  const orb = useOrb();
  const [pasos, setPasos] = useState([]);
  const [fallo, setFallo] = useState(false);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let vivo = true;
    const hechos = [];
    const pintar = () => { if (vivo) setPasos(hechos.map((p) => ({ ...p }))); };
    const nuevo = (texto) => {
      const p = { texto, estado: "curso", detalle: null };
      hechos.push(p);
      pintar();
      orb.update("core", { sub: texto });
      return p;
    };
    const cerrar = (p, estado, detalle = null) => { p.estado = estado; p.detalle = detalle; pintar(); };
    // [resultado, ms que tardó la operación]; el paso dura al menos MIN_MS
    const medir = async (op) => {
      const t0 = performance.now();
      let ms = 0;
      const [r] = await Promise.all([op().then((x) => { ms = performance.now() - t0; return x; }), espera(MIN_MS)]);
      return [r, ms];
    };

    const colocar = () => orb.setPose(isMobile() ? { x: 0, y: -0.22, s: 0.8 } : { x: 0, y: -0.14, s: 1.15 });
    colocar();
    addEventListener("resize", colocar);
    orb.setMood("thinking");
    orb.update("core", { label: "Preparando", sub: "", active: true });
    setFallo(false);

    (async () => {
      let bloqueado = false;
      const red = nuevo("Conectando con el servidor");
      try {
        const [, ms] = await medir(salud);
        cerrar(red, "ok", segundos(ms));
      } catch (e) {
        cerrar(red, "error", e.message);
        return true;
      }

      const base = nuevo("Conectando con la base de datos");
      let estado;
      try {
        [estado] = await medir(prepararAnalisis);
      } catch (e) {
        cerrar(base, "error", e.message);
        return true;
      }
      const b = estado.base;
      if (!b.ok) { cerrar(base, "error", b.error); bloqueado = true; } else if (b.tipo === "json") cerrar(base, "aviso", b.aviso);
      else cerrar(base, "ok", [BASE[b.tipo] ?? b.tipo, b.host, b.ms != null && segundos(b.ms)].filter(Boolean).join(" · "));

      if (estado.ollama) {
        const o = nuevo("Conectando con Ollama");
        await espera(MIN_MS);
        if (!estado.ollama.ok) { cerrar(o, "error", estado.ollama.error); return true; }
        cerrar(o, "ok", `${estado.ollama.url} · ${segundos(estado.ollama.ms)}`);
      }

      for (const m of estado.modelos) {
        const para = lista(m.roles.map((r) => ROL[r] ?? r));
        const p = nuevo(`Cargando ${m.modelo}`);
        if (!m.disponible) { await espera(MIN_MS); cerrar(p, "error", m.error); bloqueado = true; continue; }
        if (m.proveedor !== "ollama") { await espera(MIN_MS); cerrar(p, "ok", `${m.proveedor} · ${para}`); continue; }
        if (m.cargado) { await espera(MIN_MS); cerrar(p, "ok", `ya estaba en memoria · ${para}`); continue; }
        p.detalle = "la primera vez tarda: Ollama lo lee del disco";
        pintar();
        try {
          const [r] = await medir(() => cargarModelo(m.modelo));
          cerrar(p, "ok", `${segundos(r.ms)} · ${para}`);
        } catch (e) {
          cerrar(p, "error", e.message);
          bloqueado = true;
        }
      }
      return bloqueado;
    })().then(async (bloqueado) => {
      if (!vivo) return;
      if (bloqueado) {
        orb.setMood("error");
        orb.update("core", { label: "Falta algo", sub: "revisa los pasos", active: false });
        setFallo(true);
        return;
      }
      nuevo("Listo para analizar");
      cerrar(hechos.at(-1), "ok");
      orb.setMood("success");
      orb.update("core", { label: "Listo", sub: "", active: false });
      await espera(650);
      if (vivo) onListo();
    });

    return () => {
      vivo = false;
      removeEventListener("resize", colocar);
      orb.update("core", { active: false });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intento]);

  return (
    <section className="aparece fixed inset-x-0 bottom-[6vh] z-10 px-6" aria-live="polite">
      <ol className="mx-auto max-w-lg space-y-2.5">
        {pasos.map((p, i) => (
          <li key={i} className="flex items-start gap-3">
            <Marca estado={p.estado} />
            <span className="min-w-0 flex-1">
              <span className={`block text-[14.5px] ${p.estado === "curso" ? "text-[var(--bone)]" : "text-[var(--bone-dim)]"}`}>{p.texto}</span>
              {p.detalle && (
                <span className={`block break-words text-[12px] ${p.estado === "error" ? "text-[var(--danger)]" : p.estado === "aviso" ? "text-[var(--aviso)]" : "text-[var(--bone-faint)]"}`}>
                  {p.detalle}
                </span>
              )}
            </span>
          </li>
        ))}
      </ol>
      {fallo && (
        <div className="mx-auto mt-6 flex max-w-lg flex-wrap gap-2">
          <button className="pill sm" onClick={() => setIntento((n) => n + 1)}>Reintentar</button>
          <button className="pill ghost sm" onClick={onListo} title="Los requisitos pueden terminar con error">Continuar de todos modos</button>
          <Link className="pill ghost sm" to={`/proyectos/${proyecto}`}>Volver al proyecto</Link>
        </div>
      )}
    </section>
  );
}

function Marca({ estado }) {
  if (estado === "curso") return <span className="gira mt-1 shrink-0" aria-label="en curso" />;
  const [signo, color, nombre] = {
    ok: ["✓", "var(--ok)", "listo"], aviso: ["!", "var(--aviso)", "aviso"], error: ["✕", "var(--danger)", "falló"],
  }[estado];
  return <span className="mono mt-0.5 w-3 shrink-0 text-center text-[12px]" style={{ color }} aria-label={nombre}>{signo}</span>;
}
