import { useApp } from "../../components/intro/useApp";
import Button from "../../components/intro/Button";

/* Sin cuentas: el prototipo es de un solo usuario y la validación no registra autor */
export default function Landing() {
  const { enter } = useApp();

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
        <Button onClick={enter}>Empezar</Button>
      </div>
      <p className="fineprint rise" style={{ "--i": 4 }}>Prototipo de tesis · v0.1 · sin cuentas: un solo usuario, en esta máquina</p>
    </section>
  );
}
