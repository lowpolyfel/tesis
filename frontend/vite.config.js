import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/*
 * Para abrir Dudamel a otras personas por un túnel (Tailscale Funnel, ngrok…): la
 * interfaz y la API salen por el mismo origen. El navegador llama a /api/... y Vite lo
 * reenvía al backend en localhost:8000 sin el prefijo. Mismo origen: la cookie de
 * sesión (SameSite=Lax) viaja sin problema y no hace falta tocar CORS.
 * BACKEND_URL cambia a dónde se reenvía.
 */
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
const proxy = {
  "/api": {
    target: backend,
    changeOrigin: true,
    rewrite: (ruta) => ruta.replace(/^\/api/, ""),
  },
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // allowedHosts: Vite rechaza hosts desconocidos; el túnel llega con su propio dominio
  server: { proxy, allowedHosts: [".ts.net", ".ngrok-free.app", ".ngrok-free.dev", ".ngrok.app"] },
  preview: { proxy, allowedHosts: [".ts.net", ".ngrok-free.app", ".ngrok-free.dev", ".ngrok.app"] },
});
