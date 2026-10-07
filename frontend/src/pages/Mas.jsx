import { Link, useSearchParams } from "react-router";
import { useOrb } from "../components/orb/useOrb";
import { Encabezado, Volver } from "../components/ui";

/*
 * Lo que no hace falta para el trabajo diario: análisis del proyecto para la
 * tesis y la experimentación con el método. Fuera de la vista principal, a un
 * clic, cada cosa con una línea que dice para qué sirve.
 */
const GRUPOS = [
  {
    titulo: "Análisis del proyecto",
    items: [
      { a: "/ambiguedades", texto: "Ambigüedades", que: "Qué términos fueron ambiguos, de qué tipo y cómo se resolvieron.", mood: "clasificador" },
      { a: "/comparaciones", texto: "Comparaciones", que: "Requisitos que se contradicen, se repiten o usan palabras distintas (exploratorio).", mood: "critico" },
      { a: "/flujo", texto: "Flujo KMoS-SSA", que: "Por qué fases del marco pasó cada carga de requisitos.", mood: "modelador" },
      { a: "/historial", texto: "Historial", que: "Todos los requisitos de todos los proyectos y la cola de trabajo.", mood: "sistema" },
    ],
  },
  {
    titulo: "Experimentación",
    items: [
      { a: "/calibracion", texto: "Calibración", que: "Qué pasaría con otro umbral de similitud (no cambia nada).", mood: "extractor" },
      { a: "/evaluacion", texto: "Evaluación", que: "Corridas contra el corpus y comparación con un solo agente.", mood: "listening" },
      { a: "/catalogos/regionales", texto: "Catálogos", que: "Las expresiones regionales y vagas que el sistema reconoce.", mood: "thinking" },
    ],
  },
];

export default function Mas() {
  const [params] = useSearchParams();
  const orb = useOrb();
  const pid = params.get("proyecto");
  const con = (a) => (pid && !a.startsWith("/catalogos") && a !== "/evaluacion" ? `${a}?proyecto=${pid}` : a);

  return (
    <div className="space-y-10">
      <Encabezado volver={<Volver a={pid ? `/proyectos/${pid}` : "/proyectos"}>{pid ? "Proyecto" : "Proyectos"}</Volver>} titulo="Más" />
      {GRUPOS.map((g) => (
        <section key={g.titulo} className="space-y-3">
          <h2>{g.titulo}</h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {g.items.map((x) => (
              <li key={x.a}>
                <Link to={con(x.a)} onPointerEnter={() => orb.setMood(x.mood)} onPointerLeave={() => orb.setMood("sistema")}
                  className="tarjeta tarjeta-viva block h-full p-5">
                  <p className="serif text-[24px] leading-tight">{x.texto}</p>
                  <p className="mt-1.5 text-[14px] leading-relaxed text-[var(--bone-dim)]">{x.que}</p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
