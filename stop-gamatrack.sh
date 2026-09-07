#!/usr/bin/env bash
#
# stop-gamatrack.sh — Arrête Docker (et donc tous les conteneurs Gamatrack).
#
# Usage :
#   ./stop-gamatrack.sh          # demande le mot de passe sudo si nécessaire
#   sudo ./stop-gamatrack.sh
#
# By :
# > alexis consolo (alexis.consolo@outlook.com)
#

set -euo pipefail

info()  { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }
ok()    { printf '\033[1;32m  OK\033[0m %s\n' "$1"; }

info "Arrêt de Docker (docker.socket, docker.service)..."
sudo systemctl stop docker.socket docker.service
ok "Docker est arrêté."
