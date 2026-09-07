#!/usr/bin/env bash
#
# start-gamatrack.sh — Redémarre Docker et laisse Docker relancer automatiquement
#                       les conteneurs Gamatrack (politique restart=always /
#                       unless-stopped sur les conteneurs concernés).
#
# Usage :
#   ./start-gamatrack.sh          # demande le mot de passe sudo si nécessaire
#   sudo ./start-gamatrack.sh
#
# By :
# > alexis consolo (alexis.consolo@outlook.com)
#

set -euo pipefail

info()  { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }
ok()    { printf '\033[1;32m  OK\033[0m %s\n' "$1"; }

info "Démarrage de Docker ..."
sudo systemctl start docker
ok "Docker est démarré."

info "Conteneurs en cours d'exécution :"
docker ps
