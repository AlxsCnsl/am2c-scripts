#!/usr/bin/env bash
#
# lancer-adam.sh — Vérifie que serie/lancer_adam.sh existe, puis le lance.
#
# Usage :
#   ./lancer-adam.sh
#
# By :
# > alexis consolo (alexis.consolo@outlook.com)
#

set -euo pipefail

info()  { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }
err()   { printf '\033[1;31m  !!\033[0m %s\n' "$1" >&2; }

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TARGET="$SCRIPT_DIR/serie/lancer_adam.sh"

if [ ! -f "$TARGET" ]; then
    err "Fichier introuvable : $TARGET"
    warn "Il est possible que le dossier serie ne sois pas Télecharger"
    exit 1
fi

info "Lancement de $TARGET..."
exec sh "$TARGET"
