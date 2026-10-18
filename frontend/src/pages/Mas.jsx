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
    titulo: "Requisitos sueltos (versión 1)",
    soloConProyecto: true,
    items: [
      { a: "/v1", texto: "Requisitos del proyecto", que: "La vista de la versión 1: requisitos analizados uno por uno, su especificación, léxico y mapa.", mood: "clasificador" },
      { a: "/analizar", texto: "Analizar requisitos", que: "Pegar o subir requisitos ya escritos para que los agentes busquen su ambigüedad (versión 1).", mood: "listening" },
    ],
  },
  {
    titulo: "Análisis del proyecto (versión 1)",
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
      { a: "/calibracion", texto: "Calibración", que: "El umbral sobre las entrevistas y la prueba de modelos (Ollama, Gemini…) con un banco de 50 términos ambiguos y revisión humana.", mood: "extractor" },
      { a: "/evaluacion", texto: "Evaluación", que: "Corridas contra el corpus y comparación con un solo agente.", mood: "listening" },
      { a: "/catalogos/regionales", texto: "Catálogos", que: "Las expresiones regionales y vagas que el sistema reconoce.", mood: "thinking" },
    ],
  },
  {
    titulo: "Tu cuenta",
    items: [
      { a: "/configuracion", texto: "Configuración", que: "Qué proveedor y modelo usa cada agente (Ollama, Gemini, OpenAI, Claude…) y sus claves.", mood: "clasificador" },
    ],
  },
  {
    titulo: "Servidor",
    items: [
      { a: "/conexion", texto: "Conexión", que: "A qué base de datos está conectado el backend (Atlas, local o JSON) y si puede escribir.", mood: "sistema" },
    ],
  },
];

export default function Mas() {
  const [params] = useSearchParams();
  const orb = useOrb();
  const pid = params.get("proyecto");
  const con = (a) => {
    if (a === "/v1" || a === "/analizar") return `/proyectos/${pid}${a}`;
    return pid && !a.startsWith("/catalogos") && a !== "/evaluacion" ? `${a}?proyecto=${pid}` : a;
  };

  return (
    <div className="space-y-10">
      <Encabezado volver={<Volver a={pid ? `/proyectos/${pid}` : "/proyectos"}>{pid ? "Proyecto" : "Proyectos"}</Volver>} titulo="Más" />
      {GRUPOS.filter((g) => pid || !g.soloConProyecto).map((g) => (
        <section key={g.titulo} className="space-y-3">
          <h2>{g.titulo}</h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {g.items.map((x) => (
              <li key={x.a}>
                <Link to={con(x.a)} onPointerEnter={() => orb.setMood(x.mood, { ambiente: false })} onPointerLeave={() => orb.setMood("sistema", { ambiente: false })}
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
