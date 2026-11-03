#!/usr/bin/env bash
# Instala Dudamel en una VM Ubuntu 24.04 (Oracle Cloud Always Free, Ampere A1/ARM).
# Deja tres servicios que arrancan solos con la VM:
#   ollama           - embeddings (nomic-embed-text) y un modelo local chico de respaldo
#   dudamel-backend  - FastAPI en 127.0.0.1:8000
#   dudamel-web      - la interfaz compilada en 127.0.0.1:4173, con /api → 8000
# y Tailscale Funnel publicando 4173 en https://<vm>.<tailnet>.ts.net
#
# Uso (como el usuario «ubuntu», no root):
#   curl -fsSL https://raw.githubusercontent.com/lowpolyfel/tesis/publicar/scripts/servidor/instalar.sh -o instalar.sh
#   bash instalar.sh            # rama por omisión: publicar
#   RAMA=main bash instalar.sh
set -euo pipefail

RAMA="${RAMA:-publicar}"
REPO="${REPO:-https://github.com/lowpolyfel/tesis}"
DIR="${DIR:-$HOME/tesis}"
MODELO_LOCAL="${MODELO_LOCAL:-qwen2.5:3b}"   # respaldo en CPU; lo normal es que cada cuenta use Gemini/Groq
USUARIO="$(id -un)"

paso() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

paso "Paquetes del sistema"
sudo apt-get update -y
sudo apt-get install -y git curl build-essential python3.12 python3.12-venv python3-dev

if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 22 ]; then
  paso "Node.js 22"
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

if ! command -v ollama >/dev/null; then
  paso "Ollama"
  curl -fsSL https://ollama.com/install.sh | sh
fi
sudo systemctl enable --now ollama
paso "Modelos de Ollama (nomic-embed-text y $MODELO_LOCAL)"
ollama pull nomic-embed-text
ollama pull "$MODELO_LOCAL"

paso "Código ($RAMA)"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch origin "$RAMA" && git -C "$DIR" checkout "$RAMA" && git -C "$DIR" pull --ff-only
else
  git clone --branch "$RAMA" "$REPO" "$DIR"
fi

paso "Backend (venv + requirements)"
python3.12 -m venv "$DIR/backend/.venv"
"$DIR/backend/.venv/bin/pip" install --upgrade pip
"$DIR/backend/.venv/bin/pip" install -r "$DIR/backend/requirements.txt"

if [ ! -f "$DIR/.env" ]; then
  paso "Creando .env a partir de .env.example"
  cp "$DIR/.env.example" "$DIR/.env"
  # Valores para el servidor; lo demás (MONGO_URI, SMTP_*) lo completas tú
  sed -i \
    -e "s|^EXTRACTOR_MODEL=.*|EXTRACTOR_MODEL=$MODELO_LOCAL|" \
    -e "s|^CLASIFICADOR_MODEL=.*|CLASIFICADOR_MODEL=$MODELO_LOCAL|" \
    -e "s|^MODELADOR_MODEL=.*|MODELADOR_MODEL=$MODELO_LOCAL|" \
    -e "s|^CRITICO_MODEL=.*|CRITICO_MODEL=$MODELO_LOCAL|" \
    -e "s|^REVISOR_MODEL=.*|REVISOR_MODEL=$MODELO_LOCAL|" \
    -e "s|^COMPARADOR_MODEL=.*|COMPARADOR_MODEL=$MODELO_LOCAL|" \
    -e "s|^AGENTE_UNICO_MODEL=.*|AGENTE_UNICO_MODEL=$MODELO_LOCAL|" \
    -e "s|^SESION_COOKIE_SEGURA=.*|SESION_COOKIE_SEGURA=true|" \
    -e "s|^OLLAMA_TIMEOUT_S=.*|OLLAMA_TIMEOUT_S=900|" \
    "$DIR/.env"
  CLAVE="$("$DIR/backend/.venv/bin/python" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  sed -i "s|^CLAVE_CIFRADO=.*|CLAVE_CIFRADO=$CLAVE|" "$DIR/.env"
  chmod 600 "$DIR/.env"
fi

paso "Interfaz (npm ci + build en modo publico)"
(cd "$DIR/frontend" && npm ci --no-audit --no-fund && npx vite build --mode publico)

paso "Servicios systemd"
sudo tee /etc/systemd/system/dudamel-backend.service >/dev/null <<EOF
[Unit]
Description=Dudamel backend (FastAPI)
After=network-online.target ollama.service
Wants=network-online.target

[Service]
User=$USUARIO
WorkingDirectory=$DIR/backend
ExecStart=$DIR/backend/.venv/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/dudamel-web.service >/dev/null <<EOF
[Unit]
Description=Dudamel interfaz (vite preview, /api -> 8000)
After=dudamel-backend.service

[Service]
User=$USUARIO
WorkingDirectory=$DIR/frontend
ExecStart=$DIR/frontend/node_modules/.bin/vite preview --mode publico --host 127.0.0.1 --port 4173 --strictPort
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now dudamel-backend dudamel-web

if ! command -v tailscale >/dev/null; then
  paso "Tailscale"
  curl -fsSL https://tailscale.com/install.sh | sh
fi

cat <<EOF

Listo. Falta:
  1. Edita $DIR/.env: MONGO_URI (Atlas) y SMTP_* (Gmail, contraseña de aplicación).
     Luego: sudo systemctl restart dudamel-backend
  2. sudo tailscale up          (abre el enlace que imprime e inicia sesión)
  3. sudo tailscale funnel --bg 4173
     (la primera vez te da un enlace para activar HTTPS/Funnel; ábrelo y vuelve a correrlo)
  4. tailscale funnel status    → la URL pública https://...ts.net

Registros: journalctl -u dudamel-backend -f
EOF
