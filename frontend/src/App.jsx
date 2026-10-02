import { Navigate, Route, Routes } from "react-router";
import Layout from "./components/layout/Layout";
import Intro from "./pages/intro/Intro";
import CargaRequisitos from "./pages/CargaRequisitos";
import Cola from "./pages/Cola";
import DetalleRequisito from "./pages/DetalleRequisito";
import Validacion from "./pages/Validacion";
import Lel from "./pages/Lel";
import Catalogos from "./pages/Catalogos";
import Calibracion from "./pages/Calibracion";
import Evaluacion from "./pages/Evaluacion";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Intro />} />
      <Route element={<Layout />}>
        <Route path="/cargar" element={<CargaRequisitos />} />
        <Route path="/cola" element={<Cola />} />
        <Route path="/requisitos/:id" element={<DetalleRequisito />} />
        <Route path="/requisitos/:id/validacion" element={<Validacion />} />
        <Route path="/lel" element={<Lel />} />
        <Route path="/catalogos" element={<Navigate to="/catalogos/mexicanismos" replace />} />
        <Route path="/catalogos/:tipo" element={<Catalogos />} />
        <Route path="/calibracion" element={<Calibracion />} />
        <Route path="/evaluacion" element={<Evaluacion />} />
        <Route path="*" element={<Navigate to="/cola" replace />} />
      </Route>
    </Routes>
  );
}
