import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useOrb } from "../../components/orb/useOrb";
import TopBar from "../../components/intro/TopBar";
import { AppContext } from "../../components/intro/useApp";
import { poseFor } from "../../components/orb/poses";
import Loader from "./Loader";
import Welcome from "./Welcome";
import Landing from "./Landing";
import "./intro.css";

/*
 * Portada de Dudamel: carga en blanco, clic para empezar y bienvenida, que
 * lleva directo a «Analizar». No hay cuentas (monousuario local): una pantalla
 * de registro o de inicio de sesión mostraría algo que el sistema no tiene.
 */
const PAGES = { welcome: Welcome, landing: Landing };
const EXIT_MS = 420;

export default function Intro() {
  const navigate = useNavigate();
  const orb = useOrb();
  const [booting, setBooting] = useState(true);
  const [screen, setScreen] = useState("loading");
  const [leaving, setLeaving] = useState(false);
  const poseKey = useRef("loading");
  const exitTimer = useRef();

  const pose = useCallback((key) => {
    poseKey.current = key;
    orb.setPose(poseFor(key));
  }, [orb]);

  // El orbe sale hacia su nuevo sitio mientras el contenido actual se desvanece
  const go = useCallback((next, { poseKey: key = next } = {}) => {
    clearTimeout(exitTimer.current);
    pose(key);
    orb.setShy(false);
    setLeaving(true);
    exitTimer.current = setTimeout(() => {
      setScreen(next);
      setLeaving(false);
    }, EXIT_MS);
  }, [orb, pose]);

  // Salida de la portada hacia la aplicación
  const enter = useCallback(() => {
    pose("welcome");
    setLeaving(true);
    exitTimer.current = setTimeout(() => navigate("/inicio"), EXIT_MS + 200);
  }, [navigate, pose]);

  useEffect(() => {
    const onResize = () => orb.setPose(poseFor(poseKey.current));
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      clearTimeout(exitTimer.current);
    };
  }, [orb]);

  const ctx = useMemo(() => ({ orb, go, pose, enter }), [orb, go, pose, enter]);
  const Page = PAGES[screen];

  return (
    <AppContext.Provider value={ctx}>
      <div className="app">

        {screen !== "loading" && <TopBar screen={screen} />}
        {Page && (
          <main key={screen} className={`page page-${screen}${leaving ? " is-leaving" : ""}`}>
            <Page />
          </main>
        )}

        {booting && (
          <Loader
            onReveal={() => {
              pose("bloom");
              setTimeout(() => go("welcome"), 900);
            }}
            onFinished={() => setBooting(false)}
          />
        )}
      </div>
    </AppContext.Provider>
  );
}
