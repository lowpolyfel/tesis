import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Orb from "./components/orb/Orb";
import { createOrbController } from "./components/orb/controller";
import TopBar from "./components/ui/TopBar";
import { AppContext } from "./hooks/useApp";
import { poseFor } from "./poses";
import { currentSession } from "./services/auth";
import Loader from "./pages/Loader";
import Welcome from "./pages/Welcome";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Home from "./pages/Home";

const PAGES = { welcome: Welcome, landing: Landing, login: Login, register: Register, home: Home };
const EXIT_MS = 420;

export default function App() {
  const rootRef = useRef(null);
  const orb = useMemo(() => createOrbController(), []);
  const [booting, setBooting] = useState(true);
  const [screen, setScreen] = useState("loading");
  const [leaving, setLeaving] = useState(false);
  const [session, setSession] = useState(() => currentSession());
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

  useEffect(() => {
    const onResize = () => orb.setPose(poseFor(poseKey.current));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [orb]);

  const ctx = useMemo(() => ({ orb, go, pose, session, setSession }), [orb, go, pose, session]);
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
