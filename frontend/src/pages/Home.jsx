import { useApp } from "../hooks/useApp";
import Button from "../components/ui/Button";
import { logout } from "../services/auth";

export default function Home() {
  const { go, orb, session, setSession } = useApp();
  const first = session?.name?.split(" ")[0] ?? "";

  const exit = () => {
    logout();
    setSession(null);
    orb.setMood("idle");
    go("landing");
  };

  return (
    <section className="panel panel-center">
      <div className="eyebrow rise" style={{ "--i": 0 }}>
        <span className="rule" />
        Tu espacio
        <span className="rule" />
      </div>
      <h1 className="rise" style={{ "--i": 1 }}>
        Hola, <em>{first}</em>.
      </h1>
      <p className="lead rise" style={{ "--i": 2 }}>
        Tu cuenta está lista. Muy pronto podrás escribir un requisito aquí y ver cómo los agentes
        lo interpretan, lo debaten y lo convierten en una entrada del léxico.
      </p>
      <div className="actions rise" style={{ "--i": 3 }}>
        <Button disabled title="Disponible pronto">Nuevo análisis</Button>
        <Button variant="ghost" onClick={exit}>Cerrar sesión</Button>
      </div>
    </section>
  );
}
