import { useOrb } from "../orb/useOrb";
import { seccion } from "../orb/secciones";
import { FASES, seccionDeFase } from "../../constants/fases";

/*
 * El camino del proyecto (ADR 0024): las cinco fases en orden, cada una con su esfera
 * pequeña en el tono de la fase. Una fase hecha (validada) lleva ✓; una que todavía no se
 * abre se ve apagada y dice por qué. Al pasar el cursor, la esfera grande toma el tono de
 * la fase, como con las pestañas: solo la esfera (`ambiente: false`); el fondo sigue siendo
 * el de la fase actual.
 *   fases: [{id, disponible, hecho, motivo, …}] de GET /proyectos/{id}/fases
 */
export function estadoCorto(f) {
  if (!f) return "";
  if (f.id === "entrevista") {
    if (!f.total) return "Sube la entrevista";
    return `${f.listas} lista${f.listas === 1 ? "" : "s"}${f.en_proceso ? ` · ${f.en_proceso} procesando` : ""}`;
  }
  if (f.id === "lexico") {
    if (!f.disponible) return "Espera la entrevista";
    if (f.hecho) return `${f.vigentes} términos validados`;
    return f.propuesto ? `${f.propuesto} por validar` : "Por validar";
  }
  if (!f.disponible) return "Bloqueada";
  if (!f.existe) return "Por generar";
  if (!f.al_dia) return "Cambió lo de antes";
  if (f.estado === "validado") return "Validada";
  return `${f.pendientes ?? 0} por validar`;
}

export default function Camino({ fases, actual, onElegir }) {
  const orb = useOrb();
  const porId = Object.fromEntries((fases ?? []).map((f) => [f.id, f]));
  const moodActual = seccion(seccionDeFase(actual)).mood;
  return (
    <nav aria-label="Fases del proyecto" onPointerLeave={() => orb.setMood(moodActual, { ambiente: false })}>
      <ol className="camino">
        {FASES.map((f, i) => {
          const info = porId[f.id];
          const hecho = info?.hecho;
          const abierta = info?.disponible ?? f.id === "entrevista";
          const elegida = f.id === actual;
          return (
            <li key={f.id} className="min-w-0">
              <button
                className={`camino-paso ${elegida ? "elegido" : ""} ${abierta ? "" : "cerrada"}`}
                aria-current={elegida ? "step" : undefined}
                title={!abierta ? info?.motivo ?? "" : f.que}
                onClick={() => onElegir(f.id)}
                onPointerEnter={() => { orb.setMood(seccion(seccionDeFase(f.id)).mood, { ambiente: false }); orb.poke(0.25); }}
                style={{ "--tono": f.tono }}
              >
                <span className={`esferita ${hecho ? "hecha" : ""}`} aria-hidden="true">{hecho ? "✓" : i + 1}</span>
                <span className="block truncate text-[13.5px] leading-tight">{f.id === "mapa" ? "Mapa" : f.nombre}</span>
                <span className="mono hidden truncate text-[9px] text-[var(--bone-faint)] sm:block">{estadoCorto(info)}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
