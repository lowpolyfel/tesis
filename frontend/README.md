# frontend

Interfaz en React (Vite) de **Dudamel**. Por ahora solo cubre la entrada al sitio:
pantalla de carga, “clic para empezar”, bienvenida, registro en tres pasos, inicio de
sesión y un espacio de usuario provisional. La autenticación está simulada en el
navegador (`src/services/auth.js`, localStorage) hasta que exista la API.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # salida en dist/
```

## El orbe

El orbe vive en `src/components/orb/` y está montado una sola vez para toda la app;
las páginas no lo vuelven a crear, solo le dicen qué hacer a través del controlador
(`useApp().orb`):

| Llamada | Efecto |
|---|---|
| `pose(clave)` / `go(pantalla)` | Viaja a la posición definida en `src/poses.js` (resorte, arco y estiramiento) |
| `orb.setMood("listening" \| "thinking" \| "success" \| "error" \| "idle")` | Cambia color, ondas y ritmo |
| `orb.poke(n)` | Pequeño salto elástico |
| `orb.setShy(true)` | Aparta la mirada (campos de contraseña) |

Además mira al cursor, curiosea solo si el mouse se queda quieto y flota siempre.
