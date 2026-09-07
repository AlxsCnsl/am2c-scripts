#!/usr/bin/env bash
#
# Fenix-usb-crochetage.sh — Débloque temporairement les périphériques de stockage USB,
#                            puis les rebloque automatiquement après un délai donné.
#
# Usage :
#   sudo ./Fenix-usb-crochetage.sh <minutes>   # débloque, attend <minutes> minutes, puis rebloque
#   ./Fenix-usb-crochetage.sh <minutes>        # demande le mot de passe sudo une seule fois
#   ./Fenix-usb-crochetage.sh                  # demande le nombre de minutes de façon interactive
#
# Exemple : ./Fenix-usb-crochetage.sh 60   # ouvre les ports USB pendant 1 heure
#
# By : 
# > alexis consolo (alexis.consolo@outlook.com)
# > 

set -euo pipefail

CONF="/etc/modprobe.d/usb-storage.conf"
BLOCK_LINE="install usb-storage /bin/true"

# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
info()  { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }
ok()    { printf '\033[1;32m  OK\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33m  !!\033[0m %s\n' "$1"; }
err()   { printf '\033[1;31m  !!\033[0m %s\n' "$1" >&2; }

# Vrai si l'on peut poser une question à l'utilisateur
can_ask() { [ -r /dev/tty ] || [ -t 0 ]; }

# Lit une réponse même si le script est lancé via un pipe
ask() {
    local prompt="$1" reply=""
    if [ -r /dev/tty ]; then
        read -r -p "$prompt" reply < /dev/tty || reply=""
    else
        read -r -p "$prompt" reply || reply=""
    fi
    printf '%s' "$reply"
}

# ---------------------------------------------------------------------------
# Analyse des arguments : nombre de minutes avant refermeture (obligatoire)
# ---------------------------------------------------------------------------
case "${1:-}" in
    --help|-h)
        sed -n '3,12p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
esac

MINUTES="${1:-}"
while ! [[ "$MINUTES" =~ ^[1-9][0-9]*$ ]]; do
    if [ -n "$MINUTES" ]; then
        echo "Nombre invalide : « $MINUTES ». Indiquez un nombre entier de minutes (> 0)." >&2
    fi
    MINUTES="$(ask 'Après combien de minutes refermer les ports USB ? ')"
done

# ---------------------------------------------------------------------------
# Élévation de privilèges : un seul sudo pour tout le script
# ---------------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    if ! command -v sudo >/dev/null 2>&1; then
        echo "Ce script doit être lancé en root (sudo introuvable)." >&2
        exit 1
    fi
    echo "Élévation des privilèges nécessaire (une seule fois)..."
    exec sudo -- "$0" "$MINUTES"
fi

backup_conf() {
    [ -f "$CONF" ] || return 0
    local stamp
    stamp="$(date +%Y%m%d-%H%M%S)"
    cp -a "$CONF" "${CONF}.bak-${stamp}"
    ok "Sauvegarde : ${CONF}.bak-${stamp}"
}

# Décharge usb-storage en réessayant tant que le module reste chargé.
# Renvoie 0 si le module a fini par être déchargé, 1 si l'utilisateur abandonne
# (ou si aucune interaction n'est possible après plusieurs tentatives).
unload_module() {
    local attempt=0 reply=""

    while ! modprobe -r usb-storage 2>/dev/null; do
        attempt=$((attempt + 1))

        warn "Module non déchargé — ATTENTION : une clé USB est peut-être encore insérée."
        echo "     Retirez tout périphérique de stockage USB (démontez-le d'abord si besoin)."

        if [ "$attempt" -ge 3 ]; then
            warn "Si le problème persiste, redémarrez l'ordinateur, puis essayez de rebrancher la clé."
        fi

        if ! can_ask; then
            if [ "$attempt" -ge 5 ]; then
                warn "Aucune interaction possible — abandon des tentatives"
                return 1
            fi
            warn "Aucune interaction possible — nouvelle tentative dans 10 s"
            sleep 10
            continue
        fi

        reply="$(ask 'Retirez la clé USB, puis appuyez sur Entrée pour réessayer (« q » pour abandonner)... ')"
        case "$reply" in
            q|Q|quit|abandon) return 1 ;;
        esac
    done

    return 0
}

reload_module() {
    info "Rechargement du module usb-storage"
    if modprobe -r usb-storage 2>/dev/null; then
        ok "Module déchargé"
    else
        warn "Module non déchargé (probablement en cours d'utilisation) — on continue"
    fi
    if modprobe usb-storage 2>/dev/null; then
        ok "Module chargé"
    else
        warn "Impossible de charger le module maintenant — un redémarrage sera nécessaire"
    fi
}

# ---------------------------------------------------------------------------
# OPEN : commente la ligne de blocage
# ---------------------------------------------------------------------------
do_open() {
    info "Déblocage du stockage USB"

    if [ ! -f "$CONF" ]; then
        warn "$CONF est absent : le stockage USB n'est probablement pas bloqué"
    else
        if grep -Eq '^[[:space:]]*install[[:space:]]+usb-storage[[:space:]]+/bin/true' "$CONF"; then
            backup_conf
            sed -i -E 's|^([[:space:]]*install[[:space:]]+usb-storage[[:space:]]+/bin/true.*)$|# \1|' "$CONF"
            ok "Ligne de blocage commentée dans $CONF"
        else
            ok "Aucune ligne de blocage active dans $CONF"
        fi
    fi

    # Autres fichiers modprobe.d susceptibles de bloquer usb-storage
    local f
    for f in /etc/modprobe.d/*.conf; do
        [ -e "$f" ] || continue
        [ "$f" = "$CONF" ] && continue
        if grep -Eq '^[[:space:]]*(install[[:space:]]+usb-storage[[:space:]]+/bin/true|blacklist[[:space:]]+usb-storage)' "$f"; then
            warn "Blocage également présent dans $f"
        fi
    done

    reload_module

    info "Stockage USB débloqué"
    echo "  Branchez la clé USB, elle doit être détectée."
}

# ---------------------------------------------------------------------------
# CLOSE : réactive la ligne de blocage
# ---------------------------------------------------------------------------
do_close() {
    info "Blocage du stockage USB"

    if [ -f "$CONF" ]; then
        backup_conf
        # Décommente la ligne si elle existe
        sed -i -E 's|^[[:space:]]*#[[:space:]]*(install[[:space:]]+usb-storage[[:space:]]+/bin/true.*)$|\1|' "$CONF"
    fi

    if ! grep -Eq '^[[:space:]]*install[[:space:]]+usb-storage[[:space:]]+/bin/true' "$CONF" 2>/dev/null; then
        printf '%s\n' "$BLOCK_LINE" >> "$CONF"
        ok "Ligne de blocage ajoutée dans $CONF"
    else
        ok "Ligne de blocage réactivée dans $CONF"
    fi

    info "Déchargement du module usb-storage"
    if unload_module; then
        ok "Module déchargé"
        info "Stockage USB bloqué"
    else
        warn "Module toujours chargé — le blocage ne sera effectif qu'au redémarrage"
        warn "ATTENTION : une clé USB est peut-être encore insérée. Retirez-la, puis redémarrez l'ordinateur."
        if can_ask; then
            ask "Appuyez sur Entrée pour continuer... " >/dev/null
        fi
    fi
}

# ---------------------------------------------------------------------------
# Point d'entrée : ouverture, attente, puis refermeture automatique
# ---------------------------------------------------------------------------
do_open

info "Fermeture automatique programmée dans ${MINUTES} minute(s)"
sleep "$((MINUTES * 60))"

do_close
info "Redémarrer le PC pour désactiver"Coved valors 3 e st germain suur moine  