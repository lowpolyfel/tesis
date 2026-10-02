import { useEffect } from "react";
import { useApp } from "../../components/intro/useApp";

/* Pantalla de “clic para empezar”: cualquier clic o tecla despierta al orbe */
export default function Welcome() {
  const { go, orb } = useApp();

  useEffect(() => {
    const start = (e) => {
      if (e.type === "keydown" && ["Tab", "Shift", "Alt", "Control", "Meta"].includes(e.key)) return;
      orb.poke(1.4);
      orb.setMood("listening", { revertAfter: 900 });
      go("landing");
      window.removeEventListener("pointerdown", start);
      window.removeEventListener("keydown", start);
    };
    window.addEventListener("pointerdown", start);
    window.addEventListener("keydown", start);
    return () => {
      window.removeEventListener("pointerdown", start);
      window.removeEventListener("keydown", start);
    };
  }, [go, orb]);

  return (
    <div className="welcome">
      <h1 className="welcome-title rise" style={{ "--i": 0 }}>
        Duda<em>mel</em>
      </h1>
      <p className="welcome-cta rise" style={{ "--i": 2 }}>
        <span className="pulse" />
        <span>Haz clic para empezar</span>
      </p>
    </div>
  );
}
