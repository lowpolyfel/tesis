import { useApp } from "../../components/intro/useApp";
import Button from "../../components/intro/Button";
import { useSesion } from "../../components/sesion";

/* Con sesión, a los proyectos; sin sesión, entrar o crear la cuenta */
export default function Landing() {
  const { enter } = useApp();
  const { usuario } = useSesion();

  return (
    <section className="panel panel-left">
      <div className="eyebrow rise" style={{ "--i": 0 }}>
        <span className="idx">01</span>
        <span className="rule" />
        Requisitos sin ambigüedad
      </div>
      <h1 className="rise" style={{ "--i": 1 }}>
        Toda <em>duda</em> merece una respuesta.
      </h1>
      <p className="lead rise" style={{ "--i": 2 }}>
        Dudamel lee tus requisitos como lo haría un equipo: encuentra las palabras que admiten
        más de una interpretación, deja que sus agentes las debatan y los reescribe completos.
        Solo te pregunta cuando no se ponen de acuerdo.
      </p>
      <div className="actions rise" style={{ "--i": 3 }}>
        {usuario ? (
          <Button onClick={() => enter("/proyectos")}>Continuar como {usuario.nombre}</Button>
        ) : (
          <>
            <Button onClick={() => enter("/entrar")}>Entrar</Button>
            <Button variant="ghost" onClick={() => enter("/registro")}>Crear cuenta</Button>
          </>
        )}
      </div>
      <p className="fineprint rise" style={{ "--i": 4 }}>Prototipo de tesis · v0.2 · tus proyectos se guardan en tu cuenta</p>
    </section>
  );
}
