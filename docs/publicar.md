# Publicar Dudamel gratis (Render + Google AI Studio)

Un solo contenedor en el plan gratuito de Render, sin tarjeta y sin Ollama:

- **Agentes y embeddings** por la API de Google AI Studio (`LLM_PROVEEDOR=google`,
  `EMBEDDING_PROVEEDOR=google`). Una cuenta que ponga su propia clave en Configuración usa
  la suya.
- **Interfaz y API en el mismo origen** (`app.api.publico`): la interfaz compilada en `/` y
  la API en `/api`. La cookie de sesión funciona sin tocar CORS.
- **Datos y grafos pausados en MongoDB Atlas** (`CHECKPOINTS=mongo`): Render no tiene disco
  persistente, así que nada importante vive en el contenedor.
- **Correo por Brevo en el puerto 2525**: Render bloquea 25, 465 y 587.

Lo que hay que saber del plan gratuito: 512 MB de RAM y 0.1 de CPU (Dudamel usa unos
260 MB en reposo); se duerme a los 15 minutos sin visitas y tarda alrededor de un minuto en
despertar (la primera persona ve una pantalla de carga); 750 horas al mes.

## 1. Cuentas (todas gratis, sin tarjeta)

1. **Google AI Studio** → <https://aistudio.google.com/apikey> → *Create API key*. Esa es
   `LLM_API_KEY`.
2. **MongoDB Atlas** (si no tienes ya el cluster): un cluster M0. En *Network Access* agrega
   `0.0.0.0/0` (Render no tiene IP fija). Copia la cadena `mongodb+srv://…` con la
   contraseña codificada para URL. Esa es `MONGO_URI`.
3. **Brevo** → <https://www.brevo.com>:
   - *Senders & IP → Senders*: agrega tu correo como remitente y confírmalo con el enlace que
     te llega. Ese es `SMTP_REMITENTE` (p. ej. `Dudamel <tu-correo@gmail.com>`).
   - *SMTP & API → SMTP*: copia el **login** (`SMTP_USUARIO`) y genera una **SMTP key**
     (`SMTP_CONTRASENA`; no es la API key).
   - Plan gratuito: 300 correos al día. Como el remitente es un Gmail sin dominio propio,
     avisa a los testers que revisen spam.
4. **Render** → <https://render.com>, entra con GitHub.

## 2. Desplegar

En Render: **New → Blueprint** → elige el repo `lowpolyfel/tesis`. Render lee `render.yaml`
(rama `publicar`) y te pide los valores secretos:

| Variable | Valor |
|---|---|
| `LLM_API_KEY` | la clave de AI Studio |
| `MONGO_URI` | la cadena de Atlas |
| `CLAVE_CIFRADO` | genera una y **no la cambies** después: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SMTP_USUARIO`, `SMTP_CONTRASENA`, `SMTP_REMITENTE` | los de Brevo |

La primera compilación tarda unos minutos. La URL queda como `https://dudamel.onrender.com`
(o con un sufijo si el nombre está tomado). Cada `git push` a `publicar` vuelve a desplegar.

## 3. Comprobar

1. Abre la URL, crea una cuenta y confirma el código que llega por correo.
2. En la escena de preparación, los modelos deben salir como Google y disponibles.
3. Si algo falla: Render → el servicio → *Logs*.

### El modelo

`LLM_MODELO` pone el mismo modelo a todos los agentes. Google retira modelos cada pocos
meses: si un análisis falla con «model not found», en la app ve a **Configuración**, pon la
clave de Google y usa *Listar modelos* para ver los vigentes; luego cambia `LLM_MODELO` en
Render (*Environment*) y guarda. Lo mismo con `EMBEDDING_MODEL` (`gemini-embedding-001`).

## Límites que importan

- **Cuota de Gemini.** Con la clave del servidor, todos los testers comparten la cuota
  gratuita de esa clave (peticiones por minuto y por día). Si se acaba, que cada quien ponga
  su propia clave de AI Studio en Configuración.
- **Gemini saturado (503) o sin cuota (429).** Cada llamada a Gemini se reintenta hasta
  `GEMINI_REINTENTOS` veces (5) con espera exponencial y jitter (≈1, 2, 4, 8, 16 s, tope
  `GEMINI_BACKOFF_MAX_S`), solo ante esos dos errores. Si se agotan y hay
  `GEMINI_FALLBACK_MODEL`, se intenta una vez con ese modelo; la entrevista guarda en
  `modelos_usados` y `respaldos` qué modelo respondió en cada corrida. Si aun así falla,
  **«Volver a procesar» retoma desde la etapa que falló**: la salida de cada etapa queda en
  Mongo (`etapas_entrevista`), y lo que ya salió bien no se vuelve a pedir.
- **Una cola, un trabajador.** Los análisis van de uno en uno; con varios testers a la vez,
  esperan turno.
- **El umbral de divergencia** (`SIMILARITY_THRESHOLD=0.75`) se calibró con
  `nomic-embed-text`. Con `gemini-embedding-001` las similitudes cambian: los resultados de
  esta prueba no son comparables con la calibración original. Si los vas a reportar,
  recalibra con el módulo de calibración y ajusta el umbral.

## Correrlo en otro lado

- Local con el mismo contenedor: `docker build -t dudamel . && docker run -p 10000:10000 --env-file .env dudamel`
- Sin Docker: `npm run build -- --mode publico` en `frontend/` y
  `uvicorn app.api.publico:app --port 10000` en `backend/`.
- En una VM con disco (Oracle, etc.): `scripts/servidor/instalar.sh`.
