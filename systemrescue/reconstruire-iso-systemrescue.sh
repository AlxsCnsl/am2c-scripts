#!/usr/bin/env bash
#
# reconstruire-iso-systemrescue.sh — Injecte le contenu du dossier
#                                    « personnalisation/ » de la clé dans une
#                                    ISO SystemRescue et produit une ISO
#                                    « -perso » amorçable à l'identique.
#
# Pourquoi : démarrée depuis Ventoy, SystemRescue considère l'ISO elle-même
# comme son média de démarrage. C'est donc dans l'ISO — et nulle part ailleurs —
# qu'il va chercher sa configuration (sysrescue.d/) et ses scripts de démarrage
# (autorun/). Ventoy ne sait remplacer que les fichiers lus par GRUB, pas ceux
# que le système lit une fois Linux démarré : il faut les mettre dans l'image.
#
# L'ISO d'origine n'est jamais modifiée : elle reste la source des
# reconstructions suivantes, à refaire à chaque mise à jour de SystemRescue.
#
# Usage :
#   ./reconstruire-iso-systemrescue.sh                 # détecte l'ISO la plus récente
#   ./reconstruire-iso-systemrescue.sh /chemin/vers.iso
#   ./reconstruire-iso-systemrescue.sh source.iso destination.iso
#
# Dépendance : xorriso  (Debian/Ubuntu : sudo apt install xorriso)
#
# By :
# > alexis consolo (alexis.consolo@outlook.com)
#

set -euo pipefail

info()  { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }
ok()    { printf '\033[1;32m  OK\033[0m %s\n' "$1"; }
err()   { printf '\033[1;31m  !!\033[0m %s\n' "$1" >&2; }

case "${1:-}" in
    --help|-h)
        sed -n '3,26p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
esac

# Racine de la clé : le dossier parent de celui qui contient ce script.
RACINE="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
PERSO="$RACINE/personnalisation"

command -v xorriso >/dev/null 2>&1 || {
    err "xorriso introuvable."
    echo "    Installez-le puis relancez :  sudo apt install xorriso" >&2
    exit 1
}

[ -d "$PERSO" ] || { err "Dossier introuvable : $PERSO"; exit 1; }

# ---------------------------------------------------------------------------
# ISO source et destination
# ---------------------------------------------------------------------------
SRC="${1:-}"
if [ -z "$SRC" ]; then
    # La plus récente des ISO SystemRescue d'origine (on écarte les « -perso »).
    SRC="$(find "$RACINE/ISO" -maxdepth 1 -type f -name 'systemrescue-*.iso' \
           ! -name '*-perso.iso' -printf '%T@ %p\n' 2>/dev/null \
           | sort -rn | head -1 | cut -d' ' -f2-)"
    [ -n "$SRC" ] || { err "Aucune ISO SystemRescue trouvée dans $RACINE/ISO."; exit 1; }
fi
[ -f "$SRC" ] || { err "ISO source introuvable : $SRC"; exit 1; }

DST="${2:-${SRC%.iso}-perso.iso}"
[ "$SRC" != "$DST" ] || { err "La destination doit différer de la source."; exit 1; }

if [ -e "$DST" ]; then
    printf 'Écraser « %s » ? [o/N] ' "$DST"
    read -r reponse < /dev/tty
    case "$reponse" in
        [oO]*) rm -f "$DST" ;;
        *) echo "Abandon."; exit 0 ;;
    esac
fi

# ---------------------------------------------------------------------------
# Construction de la liste des fichiers à injecter
#
# Chaque fichier de personnalisation/ est placé dans l'ISO au chemin qu'il
# occupe sous ce dossier : personnalisation/autorun/autorun -> /autorun/autorun.
# Ajouter un fichier ici suffit à le voir apparaître dans l'ISO reconstruite.
# ---------------------------------------------------------------------------
MAPPAGES=()
NB=0
while IFS= read -r -d '' fichier; do
    MAPPAGES+=( -map "$fichier" "/${fichier#"$PERSO"/}" )
    NB=$((NB + 1))
done < <(find "$PERSO" -type f -print0 | sort -z)

[ "$NB" -gt 0 ] || { err "Aucun fichier à injecter dans $PERSO."; exit 1; }

info "Reconstruction de l'ISO"
echo "     source      : $SRC"
echo "     destination : $DST"
echo "     fichiers    : $NB injecté(s) depuis $PERSO"

# ---------------------------------------------------------------------------
# Reconstruction
#
# « -boot_image any replay » reproduit à l'identique l'amorçage de l'ISO source
# (El Torito BIOS + UEFI, MBR hybride) ; le nom de volume est conservé, ce qui
# est vital : les lignes de boot référencent archisolabel=RESCUE1302.
# Le bit exécutable est forcé sur le script, exFAT ne sachant pas le porter.
# ---------------------------------------------------------------------------
xorriso -indev "$SRC" \
        -outdev "$DST" \
        -boot_image any replay \
        "${MAPPAGES[@]}" \
        -chmod 0755 /autorun/autorun -- \
        -commit

info "Vérification du contenu injecté"
xorriso -indev "$DST" -lsl '/autorun/*' '/sysrescue.d/*' -- 2>&1 \
    | grep -E '^-' || true

ok "ISO reconstruite : $DST"
echo
echo "  Au prochain démarrage, choisissez cette ISO dans le menu Ventoy."
echo "  L'ISO d'origine est conservée : c'est la source des reconstructions"
echo "  suivantes, à refaire après chaque mise à jour de SystemRescue."
