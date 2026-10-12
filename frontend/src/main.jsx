import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import App from "./App";
import { aplicarTema } from "./components/tema";
import "./index.css";
import "./styles/dudamel.css";

aplicarTema(); // antes del primer render: sin destello del otro tema

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);
