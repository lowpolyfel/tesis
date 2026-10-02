import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import Orb from "../../components/orb/Orb";
import { createOrbController } from "../../components/orb/controller";
import TopBar from "../../components/intro/TopBar";
import { AppContext } from "../../components/intro/useApp";
import { poseFor } from "./poses";
import Loader from "./Loader";
import Welcome from "./Welcome";
import Landing from "./Landing";
import Login from "./Login";
import Register from "./Register";
import "./intro.css";

/*
 * Portada de Dudamel: carga en blanco, clic para empezar, bienvenida,
 * login y registro. El acceso no valida nada (monousuario local):
 * entrar o registrarse lleva directo a la cola de requisitos.
 */
const PAGES = { welcome: Welcome, landing: Landing, login: Login, register: Register };
const EXIT_MS = 420;

export default function Intro() {
  const rootRef = useRef(null);
  const navigate = useNavigate();
  const orb = useMemo(() => createOrbController(), []);
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
    exitTimer.current = setTimeout(() => navigate("/cola"), EXIT_MS + 200);
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
      <div ref={rootRef} className="app">
        <Orb controller={orb} rootRef={rootRef} />
        <div className="grain" aria-hidden="true" />

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
