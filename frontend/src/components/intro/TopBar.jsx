import { useApp } from "./useApp";
import { BotonTema } from "../tema";

const STATUS = {
  welcome: "En espera",
  landing: "Bienvenida",
};

export default function TopBar({ screen }) {
  const { go, orb } = useApp();
  const home = () => {
    orb.poke(0.8);
    go("landing");
  };

  return (
    <header className="topbar rise-soft">
      <button type="button" className="brand" onClick={home} aria-label="Dudamel, ir al inicio">
        <span className="dot" />
        Dudamel
      </button>
      <div className="flex items-center gap-5">
        <div key={screen} className="status fade">
          <span className="dot sm" />
          {STATUS[screen]}
        </div>
        <BotonTema className="pointer-events-auto" />
      </div>
    </header>
  );
}
