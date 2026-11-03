# Abrir Dudamel a un grupo de prueba (gratis, en Oracle Cloud)

Dudamel corre en una VM gratuita de Oracle Cloud (Always Free, ARM): backend, Ollama
para los embeddings y la interfaz, igual que en tu PC. La VM no se apaga, tiene disco
persistente (el SQLite de checkpoints y la clave de cifrado sobreviven reinicios) y Tailscale
Funnel le da una URL fija con HTTPS sin abrir puertos.

La interfaz y la API salen por el **mismo origen**: el navegador llama a `/api/...` y Vite
lo reenvía a uvicorn en `127.0.0.1:8000`. La cookie de sesión funciona sin tocar CORS y
los eventos en vivo (SSE) pasan.

## 1. Crear la VM (≈20 min)

1. Crea la cuenta en <https://signup.oraclecloud.com>. Pide tarjeta solo para verificar
   (no cobra mientras uses recursos Always Free). La **región de inicio** no se puede
   cambiar después: elige Querétaro o Monterrey.
2. Compute → Instances → Create instance:
   - Image: **Canonical Ubuntu 24.04** (aarch64).
   - Shape: **Ampere → VM.Standard.A1.Flex**, 2 OCPU y 12 GB (todo el cupo gratuito).
   - Boot volume: 50 GB está bien.
   - Sube o descarga la llave SSH.
3. Si sale «Out of capacity for shape VM.Standard.A1.Flex», prueba otro *availability
   domain* o vuelve a intentar en unas horas; es común en la cuenta gratuita.
4. Entra: `ssh -i tu_llave ubuntu@<ip-publica>`.

No hace falta abrir puertos en la *security list*: Tailscale sale hacia fuera.

## 2. Instalar (≈15 min, un comando)

```bash
curl -fsSL https://raw.githubusercontent.com/lowpolyfel/tesis/publicar/scripts/servidor/instalar.sh -o instalar.sh
bash instalar.sh
```

Instala Python 3.12, Node 22, Ollama (`nomic-embed-text` y `qwen2.5:3b` como respaldo),
el backend y la interfaz, y los deja como servicios que arrancan solos
(`dudamel-backend`, `dudamel-web`). Crea `~/tesis/.env` con una `CLAVE_CIFRADO` nueva y
`SESION_COOKIE_SEGURA=true`.

## 3. Completar el .env

```bash
nano ~/tesis/.env
sudo systemctl restart dudamel-backend
```

- **`MONGO_URI`**: tu cluster de Atlas (M0 gratis). En Atlas → Network Access agrega la IP
  pública de la VM. Con Atlas, `MONGO_TIMEOUT_MS=10000`. Sin Mongo, el backend usa el
  respaldo JSON en `data/resultados/`, que también persiste en el disco de la VM.
- **`SMTP_*`** (obligatorio para gente de fuera): sin correo, el código de registro solo
  sale en `journalctl` y nadie podría crear cuenta. Gmail: `smtp.gmail.com`, 587,
  `starttls` y una contraseña de aplicación. Prueba:
  `cd ~/tesis && backend/.venv/bin/python scripts/probar_correo.py otra@correo.com`.

## 4. Publicar

```bash
sudo tailscale up                 # abre el enlace que imprime e inicia sesión
sudo tailscale funnel --bg 4173   # la primera vez te da un enlace para activar Funnel
tailscale funnel status           # la URL: https://<vm>.<tailnet>.ts.net
```

Esa URL es la que compartes. Funnel queda configurado y vuelve solo si la VM se reinicia.

## Para los testers

La VM tiene 2 núcleos sin GPU: los modelos locales sirven de respaldo pero son lentos, y la
cola tiene un solo trabajador. Que cada persona, al crear su cuenta, vaya a
**Configuración** y ponga una clave gratuita de Google AI Studio (Gemini) o Groq para sus
agentes. Los embeddings siguen en Ollama de la VM y son ligeros.

## Mantenimiento

- Actualizar tras un `git push`: `bash ~/tesis/scripts/servidor/actualizar.sh`
- Registros: `journalctl -u dudamel-backend -f`
- Oracle puede reclamar una VM Always Free si pasa 7 días casi sin uso (CPU, red y memoria
  por debajo del 20 %). Durante la prueba no pasa; si quieres dejarla meses, cambia la
  cuenta a *Pay As You Go* (sigue sin costo dentro del cupo gratuito).
- Mientras Funnel está activo, cualquiera con la URL llega al backend (incluidas `/docs` y
  `/sandbox`); los proyectos sí quedan protegidos por cuenta. Para cerrarlo:
  `sudo tailscale funnel reset`.

## Correrlo desde tu PC (alternativa)

Con los mismos cambios también funciona en local: `uvicorn` en 8000, `npm run publico` en
`frontend/` y `tailscale funnel 4173`. No uses los Quick Tunnels de Cloudflare
(`trycloudflare.com`): no soportan SSE.
