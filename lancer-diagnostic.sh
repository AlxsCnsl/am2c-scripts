#!/usr/bin/env bash
#
# lancer-diagnostic.sh — Vérifie que ADAM/lancer_diagnostic.sh existe, puis le lance.
#
# Usage :
#   ./lancer-diagnostic.sh
#
# By :
# > alexis consolo (alexis.consolo@outlook.com)
#

set -euo pipefail

info()  { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33m  ..\033[0m %s\n' "$1" >&2; }
err()   { printf '\033[1;31m  !!\033[0m %s\n' "$1" >&2; }

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TARGET="$SCRIPT_DIR/ADAM/lancer_diagnostic.sh"

if [ ! -f "$TARGET" ]; then
    err "Fichier introuvable : $TARGET"
    warn "Il est possible que le dossier ADAM ne soit pas téléchargé."
    exit 1
fi

info "Lancement de $TARGET..."
exec sh "$TARGET"
