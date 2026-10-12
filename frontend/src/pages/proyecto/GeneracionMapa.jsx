import { useEffect, useState } from "react";
import { useOrb } from "../../components/orb/useOrb";
import { isMobile } from "../../components/orb/poses";
import { poseSeccion } from "../../components/orb/secciones";
import Pasos from "../../escena/Pasos";
import { generarMapaConceptual } from "../../services/backend";

/*
 * Pantalla de carga del mapa conceptual (ADR 0020). Un velo cubre el proyecto y la
 * esfera sube por encima: va al centro con el color del mapa y dice debajo qué paso
 * hace; los pasos llegan del backend conforme ocurren (POST /proyectos/{id}/mapa-conceptual).
 * Al terminar la esfera vuelve a su lugar en el margen, el velo se va y queda el mapa.
 */
const SALIDA_MS = 700; // lo que tarda la esfera en volver a su lugar
const espera = (ms) => new Promise((r) => setTimeout(r, ms));
// bajar la esfera se retrasa SALIDA_MS; si la pantalla se vuelve a montar antes (React lo hace
// en desarrollo, o al regenerar) hay que cancelarlo, o la esfera queda detrás del velo
let bajada = null;

export default function GeneracionMapa({ proyectoId, seleccion, nuevo, onListo, onCancelar }) {
  const orb = useOrb();
  const [pasos, setPasos] = useState([]);
  const [error, setError] = useState(null);
  const [saliendo, setSaliendo] = useState(false);
  const [intento, setIntento] = useState(0);

  // la esfera al frente mientras dure la pantalla; al irse, de vuelta a su lugar
  useEffect(() => {
    clearTimeout(bajada);
    orb.setElevada(true, "mapa");
    return () => {
      orb.setPose(poseSeccion("mapa"));
      orb.setMood("mapa");
      orb.update("core", { label: null, sub: null, active: false, desde: null });
      bajada = setTimeout(() => orb.setElevada(false, "mapa"), SALIDA_MS);
    };
  }, [orb]);

  useEffect(() => {
    const control = new AbortController();
    let vivo = true;
    const colocar = () => orb.setPose(isMobile() ? { x: 0, y: -0.2, s: 0.8 } : { x: 0, y: -0.12, s: 1.15 });
    colocar();
    addEventListener("resize", colocar);
    orb.setMood("mapa_generando");
    orb.update("core", { label: "Mapa conceptual", sub: "", active: true, desde: Date.now() });
    setPasos([]);
    setError(null);

    const vistos = [];
    let mapa = null;
    const alEvento = (e) => {
      if (!vivo) return;
      if (e.tipo === "paso") {
        const i = vistos.findIndex((p) => p.id === e.id);
        if (i === -1) vistos.push(e); else vistos[i] = e;
        setPasos(vistos.map((p) => ({ ...p })));
        if (e.estado === "curso") orb.update("core", { sub: e.texto });
      } else if (e.tipo === "mapa") mapa = e.mapa;
      else if (e.tipo === "error") throw new Error(e.mensaje);
    };

    generarMapaConceptual(proyectoId, seleccion, { nuevo: nuevo || intento > 0, onEvento: alEvento, senal: control.signal })
      .then(async () => {
        if (!vivo) return;
        if (!mapa) throw new Error("El servidor cerró la conexión antes de terminar el mapa.");
        if (vistos.length) { // si estaba guardado, no hay pantalla de carga que cerrar con calma
          orb.setMood("success");
          orb.update("core", { label: "Listo", sub: `${mapa.conceptos.length} conceptos`, desde: null });
          await espera(650);
          if (!vivo) return;
        }
        setSaliendo(true);
        orb.setPose(poseSeccion("mapa"));
        orb.setMood("mapa");
        orb.update("core", { label: null, sub: null, active: false });
        await espera(SALIDA_MS * 0.6);
        if (vivo) onListo(mapa);
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
      <section className={`fixed inset-x-0 bottom-[6vh] z-50 px-6 ${saliendo ? "se-va" : "aparece"}`}
        aria-live="polite" aria-label="Generando el mapa conceptual">
        <Pasos pasos={error ? [...pasos, { texto: "No se pudo terminar el mapa", estado: "error", detalle: error }] : pasos} />
        <div className="mx-auto mt-6 flex max-w-lg flex-wrap gap-2">
          {error && <button className="pill sm" onClick={() => setIntento((n) => n + 1)}>Reintentar</button>}
          <button className={error ? "pill ghost sm" : "mono px-1 text-[10px] text-[var(--bone-faint)] hover:text-[var(--bone)]"} onClick={onCancelar}>
            {error ? "Cerrar" : "cancelar"}
          </button>
        </div>
      </section>
    </>
  );
}
