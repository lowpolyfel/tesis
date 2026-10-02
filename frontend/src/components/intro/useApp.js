import { createContext, useContext } from "react";

/* Navegación entre pantallas, sesión y control del orbe */
export const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);
