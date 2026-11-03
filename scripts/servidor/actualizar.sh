#!/usr/bin/env bash
# Trae lo último de la rama, reinstala lo que cambió y reinicia los servicios.
# Uso en la VM:  bash ~/tesis/scripts/servidor/actualizar.sh
set -euo pipefail
DIR="${DIR:-$HOME/tesis}"

git -C "$DIR" pull --ff-only
"$DIR/backend/.venv/bin/pip" install -q -r "$DIR/backend/requirements.txt"
(cd "$DIR/frontend" && npm ci --no-audit --no-fund && npx vite build --mode publico)
sudo systemctl restart dudamel-backend dudamel-web
systemctl --no-pager --lines=0 status dudamel-backend dudamel-web
