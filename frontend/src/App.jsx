import { useMemo, useRef } from "react";
import { Navigate, Route, Routes, useSearchParams } from "react-router";
import OrbField from "./components/orb/OrbField";
import { createOrbController } from "./components/orb/controller";
import { OrbContext } from "./components/orb/useOrb";
import Shell from "./components/layout/Shell";
import { proyectoRecordado } from "./components/proyectoRecordado";
import Intro from "./pages/intro/Intro";
import Proyectos from "./pages/Proyectos";
import Proyecto from "./pages/proyecto/Proyecto";
import Analizar from "./pages/Analizar";
import Analisis from "./pages/Analisis";
import DetalleRequisito from "./pages/DetalleRequisito";
import Validacion from "./pages/Validacion";
import Mas from "./pages/Mas";
import Ambiguedades from "./pages/Ambiguedades";
import Comparaciones from "./pages/Comparaciones";
import Flujo from "./pages/Flujo";
import Cola from "./pages/Cola";
import Lel from "./pages/Lel";
import Catalogos from "./pages/Catalogos";
import Calibracion from "./pages/Calibracion";
import Evaluacion from "./pages/Evaluacion";

/*
 * La esfera vive aquí, por encima de las rutas: nunca se desmonta.
 * Cada pantalla solo le dice dónde estar y qué hacer.
 *
 *   /proyectos                      todos los proyectos
 *   /proyectos/:id?vista=           un proyecto: requisitos, especificación, léxico o mapa
 *   /proyectos/:id/analizar         cargar requisitos (escena)
 *   /analisis?proyecto=&ids=        la escena en vivo de un lote
 *   /requisitos/:id[/validacion]    un requisito y su revisión
 *   /mas                            análisis y experimentación
 */
const raiz = { current: document.documentElement };

/* Rutas anteriores: llevan a su lugar nuevo */
function AAnalizar() {
  const [params] = useSearchParams();
  const p = params.get("proyecto") ?? proyectoRecordado();
  return <Navigate to={p ? `/proyectos/${p}/analizar` : "/proyectos"} replace />;
}
function AlMapa() {
  const [params] = useSearchParams();
  const p = params.get("proyecto") ?? proyectoRecordado();
  return <Navigate to={p ? `/proyectos/${p}?vista=mapa` : "/proyectos"} replace />;
}

export default function App() {
  const orb = useMemo(() => createOrbController(), []);
  const rootRef = useRef(raiz.current);

  return (
    <OrbContext.Provider value={orb}>
      <OrbField controller={orb} rootRef={rootRef} />
      <div className="grain" aria-hidden="true" />
      <Routes>
        <Route path="/" element={<Intro />} />
        <Route element={<Shell modo="escena" />}>
          <Route path="/proyectos/:id/analizar" element={<Analizar />} />
          <Route path="/analisis" element={<Analisis />} />
        </Route>
        <Route element={<Shell modo="herramienta" />}>
          <Route path="/proyectos" element={<Proyectos />} />
          <Route path="/proyectos/:id" element={<Proyecto />} />
          <Route path="/requisitos/:id" element={<DetalleRequisito />} />
          <Route path="/requisitos/:id/validacion" element={<Validacion />} />
          <Route path="/mas" element={<Mas />} />
          <Route path="/ambiguedades" element={<Ambiguedades />} />
          <Route path="/comparaciones" element={<Comparaciones />} />
          <Route path="/flujo" element={<Flujo />} />
          <Route path="/historial" element={<Cola />} />
          <Route path="/lel" element={<Lel />} />
          <Route path="/catalogos" element={<Navigate to="/catalogos/regionales" replace />} />
          <Route path="/catalogos/:tipo" element={<Catalogos />} />
          <Route path="/calibracion" element={<Calibracion />} />
          <Route path="/evaluacion" element={<Evaluacion />} />
        </Route>
        <Route path="/inicio" element={<AAnalizar />} />
        <Route path="/cargar" element={<AAnalizar />} />
        <Route path="/big-picture" element={<AlMapa />} />
        <Route path="/cola" element={<Navigate to="/historial" replace />} />
        <Route path="/lel/generar" element={<Navigate to="/lel" replace />} />
        <Route path="*" element={<Navigate to="/proyectos" replace />} />
      </Routes>
    </OrbContext.Provider>
  );
}
