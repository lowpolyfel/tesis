import { useMemo, useRef } from "react";
import { Navigate, Route, Routes } from "react-router";
import OrbField from "./components/orb/OrbField";
import { createOrbController } from "./components/orb/controller";
import { OrbContext } from "./components/orb/useOrb";
import Shell from "./components/layout/Shell";
import Intro from "./pages/intro/Intro";
import Inicio from "./pages/Inicio";
import Analisis from "./pages/Analisis";
import BigPicture from "./pages/BigPicture";
import Flujo from "./pages/Flujo";
import Proyectos from "./pages/Proyectos";
import Proyecto from "./pages/Proyecto";
import Ambiguedades from "./pages/Ambiguedades";
import Cola from "./pages/Cola";
import DetalleRequisito from "./pages/DetalleRequisito";
import Validacion from "./pages/Validacion";
import Lel from "./pages/Lel";
import Catalogos from "./pages/Catalogos";
import Calibracion from "./pages/Calibracion";
import Evaluacion from "./pages/Evaluacion";

/*
 * La esfera vive aquí, por encima de las rutas: nunca se desmonta.
 * Cada pantalla solo le dice dónde estar y qué hacer.
 */
const raiz = { current: document.documentElement };

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
          <Route path="/inicio" element={<Inicio />} />
          <Route path="/analisis" element={<Analisis />} />
          <Route path="/big-picture" element={<BigPicture />} />
          <Route path="/flujo" element={<Flujo />} />
        </Route>
        <Route element={<Shell modo="herramienta" />}>
          <Route path="/proyectos" element={<Proyectos />} />
          <Route path="/proyectos/:id" element={<Proyecto />} />
          <Route path="/ambiguedades" element={<Ambiguedades />} />
          <Route path="/historial" element={<Cola />} />
          <Route path="/requisitos/:id" element={<DetalleRequisito />} />
          <Route path="/requisitos/:id/validacion" element={<Validacion />} />
          <Route path="/lel" element={<Lel />} />
          <Route path="/catalogos" element={<Navigate to="/catalogos/regionales" replace />} />
          <Route path="/catalogos/:tipo" element={<Catalogos />} />
          <Route path="/calibracion" element={<Calibracion />} />
          <Route path="/evaluacion" element={<Evaluacion />} />
        </Route>
        <Route path="/cola" element={<Navigate to="/historial" replace />} />
        {/* El LEL lo genera el Modelador al aprobar en Validación; ya no hay paso manual */}
        <Route path="/lel/generar" element={<Navigate to="/lel" replace />} />
        <Route path="/cargar" element={<Navigate to="/inicio" replace />} />
        <Route path="*" element={<Navigate to="/inicio" replace />} />
      </Routes>
    </OrbContext.Provider>
  );
}
