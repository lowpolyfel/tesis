import { useApp } from "../hooks/useApp";
import Button from "../components/ui/Button";

export default function Landing() {
  const { go } = useApp();

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
        Dudamel lee tus requisitos de software como lo haría un equipo: encuentra las palabras
        que admiten más de una lectura, deja que sus agentes las debatan y te entrega una sola
        interpretación, clara y documentada.
      </p>
      <div className="actions rise" style={{ "--i": 3 }}>
        <Button onClick={() => go("register", { poseKey: "register1" })}>Crear cuenta</Button>
        <Button variant="ghost" onClick={() => go("login")}>Iniciar sesión</Button>
      </div>
      <p className="fineprint rise" style={{ "--i": 4 }}>Prototipo de tesis · v0.1</p>
    </section>
  );
}
