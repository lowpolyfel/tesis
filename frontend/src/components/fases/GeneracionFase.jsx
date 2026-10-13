import { useEffect, useState } from "react";
import { useOrb } from "../orb/useOrb";
import { isMobile } from "../orb/poses";
import { poseSeccion } from "../orb/secciones";
import Pasos from "../../escena/Pasos";
import { generarFase } from "../../services/backend";

/*
 * Pantalla de carga de una fase que genera el Modelador (mapa, metas o requisitos; ADR 0024),
 * como la del mapa de la versión 1 (ADR 0020). Un velo cubre el proyecto y la esfera sube al
 * centro con el tono de la fase; debajo, los pasos que manda el backend conforme ocurren
 * (POST /proyectos/{id}/fases/{fase}/generar, NDJSON). Al terminar vuelve a su margen.
 */
const SALIDA_MS = 700;
const espera = (ms) => new Promise((r) => setTimeout(r, ms));
let bajada = null;

const TEXTOS = {
  mapa: { titulo: "Mapa conceptual", listo: (d) => `${d.contenido.conceptos.length} conceptos` },
  metas: { titulo: "Metas", listo: (d) => `${d.contenido.metas.length} metas` },
  requisitos: { titulo: "Requisitos", listo: (d) => `${d.contenido.requisitos.length} requisitos` },
};

export default function GeneracionFase({ proyectoId, fase, seccionId, moodGenerando, moodSeccion, onListo, onCancelar }) {
  const orb = useOrb();
  const [pasos, setPasos] = useState([]);
  const [error, setError] = useState(null);
  const [saliendo, setSaliendo] = useState(false);
  const [intento, setIntento] = useState(0);
  const t = TEXTOS[fase];

  useEffect(() => {
    clearTimeout(bajada);
    orb.setElevada(true, "fase");
    return () => {
      orb.setPose(poseSeccion(seccionId));
      orb.setMood(moodSeccion);
      orb.update("core", { label: null, sub: null, active: false, desde: null });
      bajada = setTimeout(() => orb.setElevada(false, "fase"), SALIDA_MS);
    };
  }, [orb, seccionId, moodSeccion]);

  useEffect(() => {
    const control = new AbortController();
    let vivo = true;
    const colocar = () => orb.setPose(isMobile() ? { x: 0, y: -0.2, s: 0.8 } : { x: 0, y: -0.12, s: 1.15 });
    colocar();
    addEventListener("resize", colocar);
    orb.setMood(moodGenerando);
    orb.update("core", { label: t.titulo, sub: "", active: true, desde: Date.now() });
    setPasos([]);
    setError(null);

    const vistos = [];
    let documento = null;
    const alEvento = (e) => {
      if (!vivo) return;
      if (e.tipo === "paso") {
        const i = vistos.findIndex((p) => p.id === e.id);
        if (i === -1) vistos.push(e); else vistos[i] = e;
        setPasos(vistos.map((p) => ({ ...p })));
        if (e.estado === "curso") orb.update("core", { sub: e.texto });
        orb.poke(0.3);
      } else if (e.tipo === "resultado") documento = e.documento;
      else if (e.tipo === "error") throw new Error(e.mensaje);
    };

    generarFase(proyectoId, fase, { onEvento: alEvento, senal: control.signal })
      .then(async () => {
        if (!vivo) return;
        if (!documento) throw new Error("El servidor cerró la conexión antes de terminar.");
        orb.setMood("success");
        orb.update("core", { label: "Listo", sub: t.listo(documento), desde: null });
        await espera(700);
        if (!vivo) return;
        setSaliendo(true);
        orb.setPose(poseSeccion(seccionId));
        orb.setMood(moodSeccion);
        orb.update("core", { label: null, sub: null, active: false });
        await espera(SALIDA_MS * 0.6);
        if (vivo) onListo(documento);
      })
      .catch((e) => {
        if (!vivo || e.name === "AbortError") return;
        orb.setMood("error");
        orb.update("core", { label: "No se pudo", sub: "revisa los pasos", active: false, desde: null });
        setError(e.message);
      });

    return () => {
      vivo = false;
      control.abort();
      removeEventListener("resize", colocar);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intento]);

  return (
    <>
      <div className={`velo velo-denso fixed inset-0 z-40 ${saliendo ? "se-va" : ""}`} aria-hidden="true" />
      <section className={`fixed inset-x-0 bottom-[6vh] z-50 px-6 ${saliendo ? "se-va" : "aparece"}`} aria-live="polite"
        aria-label={`Generando: ${t.titulo}`}>
        <Pasos pasos={error ? [...pasos, { texto: "No se pudo terminar", estado: "error", detalle: error }] : pasos} />
        <div className="mx-auto mt-6 flex max-w-lg flex-wrap gap-2">
          {error && <button className="pill sm" onClick={() => setIntento((n) => n + 1)}>Reintentar</button>}
          <button className={error ? "pill ghost sm" : "mono px-1 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]"} onClick={onCancelar}>
            {error ? "Cerrar" : "seguir en segundo plano"}
          </button>
        </div>
      </section>
    </>
  );
}
