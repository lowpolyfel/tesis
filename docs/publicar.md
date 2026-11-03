# Abrir Dudamel a un grupo de prueba (gratis, desde tu PC)

Dudamel corre en tu máquina como siempre (backend, Ollama, Mongo/Atlas) y un túnel le da
una URL pública con HTTPS. La interfaz y la API salen por el **mismo origen**: el navegador
llama a `/api/...` y Vite lo reenvía a uvicorn en `localhost:8000`. Así la cookie de sesión
funciona sin tocar CORS y los eventos en vivo (SSE) pasan.

Mientras la PC esté encendida, con los tres procesos corriendo, la URL funciona.

## Antes de abrirla (una vez)

1. **Correo (obligatorio para gente de fuera).** Sin SMTP, el código de registro sale en tu
   consola y nadie más lo ve. En el `.env` de la raíz pon `SMTP_HOST=smtp.gmail.com`,
   `SMTP_USUARIO`, `SMTP_CONTRASENA` (contraseña de aplicación de Google) y
   `SMTP_REMITENTE`. Pruébalo con `python scripts\probar_correo.py otra@correo.com`.
2. **Cookie segura.** El túnel sirve por HTTPS: `SESION_COOKIE_SEGURA=true`.
3. **Modelos.** Con la configuración por omisión todos los agentes usan Ollama en tu PC y
   la cola tiene un solo trabajador: con varias personas a la vez, esperan turno. Pide a
   cada quien que en **Configuración** ponga una clave gratuita de Google AI Studio (Gemini)
   o Groq para sus agentes. Los embeddings (`nomic-embed-text`) siguen en tu Ollama, son
   ligeros.
4. **Tailscale.** Instálalo (<https://tailscale.com/download>) e inicia sesión. La primera
   vez que corras `tailscale funnel`, te da un enlace para activar HTTPS y Funnel en tu
   tailnet; ábrelo y acepta.

## Cada vez que abras la prueba (tres terminales, PowerShell)

```powershell
# 1. Backend, desde backend/ (sin --reload)
.venv\Scripts\Activate.ps1
uvicorn app.api.main:app --host 127.0.0.1 --port 8000

# 2. Interfaz, desde frontend/: compila en modo «publico» y la sirve en 4173 con /api → 8000
npm run publico

# 3. Túnel
tailscale funnel 4173
```

`tailscale funnel` imprime la URL, del tipo `https://<tu-pc>.<tu-tailnet>.ts.net`. Esa es la
que compartes; no cambia entre reinicios. Para dejar el túnel en segundo plano:
`tailscale funnel --bg 4173`; para cerrarlo: `tailscale funnel reset`.

## Alternativa: ngrok

Si Tailscale no te deja activar Funnel, `ngrok http 4173` (cuenta gratuita) da un dominio
fijo `*.ngrok-free.app`. Límites del plan gratuito: 1 GB de transferencia y 20 000
peticiones al mes, y la primera visita de cada persona muestra un aviso de ngrok
(«Visit Site»). El bundle de la interfaz pesa varios MB por carga, así que con 10 personas
el GB se puede acabar en la semana; por eso Tailscale va primero.

No uses los Quick Tunnels de Cloudflare (`trycloudflare.com`): no soportan SSE y la escena
en vivo dejaría de actualizarse.

## Al terminar

Cierra el túnel (`tailscale funnel reset`). Mientras está abierto, cualquiera con la URL
llega a tu backend (incluidas `/docs` y `/sandbox`); los proyectos sí quedan protegidos por
cuenta.
