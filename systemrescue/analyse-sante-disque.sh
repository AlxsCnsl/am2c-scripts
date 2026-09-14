#!/usr/bin/env bash
#
# analyse-sante-disque.sh — Lit les données SMART/NVMe d'un disque et propose
#                            un diagnostic selon son état (défaillance matérielle
#                            probable, ou disque sain — auquel cas le souci est
#                            ailleurs, ex. timing BIOS au démarrage à froid).
#                            Ne fait que lire : aucun test actif n'est lancé.
#
# Pensé pour être lancé depuis un live SystemRescue (smartmontools est déjà
# présent sur ces images) pour diagnostiquer un disque qui pose souci au boot.
#
# Usage :
#   ./analyse-sante-disque.sh [/dev/sdX|/dev/nvmeXnY]
#   ./analyse-sante-disque.sh              # liste les disques et demande lequel choisir
#
# By :
# > alexis consolo (alexis.consolo@outlook.com)
#

set -euo pipefail

info()  { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }
ok()    { printf '\033[1;32m  OK\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33m  !!\033[0m %s\n' "$1"; }
err()   { printf '\033[1;31m  !!\033[0m %s\n' "$1" >&2; }

case "${1:-}" in
    --help|-h)
        sed -n '3,15p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
esac

# ---------------------------------------------------------------------------
# Élévation de privilèges : smartctl a besoin d'un accès direct au disque
# ---------------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    if ! command -v sudo >/dev/null 2>&1; then
        err "Ce script doit être lancé en root (sudo introuvable)."
        exit 1
    fi
    exec sudo -- "$0" "$@"
fi

command -v smartctl >/dev/null 2>&1 || {
    err "smartctl introuvable (paquet « smartmontools »)."
    echo "    Sur une image SystemRescue il est normalement déjà installé." >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Choix du disque
# ---------------------------------------------------------------------------
DEV="${1:-}"
if [ -z "$DEV" ]; then
    info "Disques détectés :"
    lsblk -d -n -o NAME,SIZE,MODEL,TYPE | awk '$NF=="disk" {$NF=""; print "  /dev/"$0}'
    read -r -p $'\nQuel disque analyser ? (ex. /dev/sda) ' DEV < /dev/tty
fi

[ -b "$DEV" ] || { err "« $DEV » n'est pas un périphérique bloc valide."; exit 1; }

info "Analyse de $DEV"
SMART_OUT="$(mktemp)"
trap 'rm -f "$SMART_OUT"' EXIT
smartctl -a "$DEV" > "$SMART_OUT" 2>&1 || true

grep -q "SMART support is: Enabled\|NVMe Log" "$SMART_OUT" || {
    err "Impossible de lire les données SMART sur $DEV."
    echo "    (SMART peut-être désactivé, ou disque derrière un contrôleur RAID/USB non transparent.)" >&2
    cat "$SMART_OUT"
    exit 1
}

get_ata_attr() { awk -v name="$1" '$2==name {print $NF}' "$SMART_OUT"; }
get_nvme_val() { grep -m1 "^$1" "$SMART_OUT" | sed -E 's/^[^:]+:[[:space:]]*//'; }

CRITIQUE=0

# ---------------------------------------------------------------------------
# Disques NVMe
# ---------------------------------------------------------------------------
if [[ "$DEV" == *nvme* ]]; then
    HEALTH="$(get_nvme_val 'SMART overall-health self-assessment test result')"
    CRITICAL_WARNING="$(get_nvme_val 'Critical Warning')"
    MEDIA_ERRORS="$(get_nvme_val 'Media and Data Integrity Errors')"
    PCT_USED="$(get_nvme_val 'Percentage Used')"
    SPARE="$(get_nvme_val 'Available Spare' | head -1)"
    UNSAFE_SHUTDOWNS="$(get_nvme_val 'Unsafe Shutdowns')"

    info "Résultat SMART global : ${HEALTH:-inconnu}"
    [[ "$HEALTH" == *PASSED* ]] && ok "Auto-évaluation SMART : OK" || { warn "Auto-évaluation SMART en échec"; CRITIQUE=1; }

    [ "${CRITICAL_WARNING:-0x00}" = "0x00" ] && ok "Critical Warning : 0x00" || { warn "Critical Warning : $CRITICAL_WARNING"; CRITIQUE=1; }
    [ "${MEDIA_ERRORS:-0}" = "0" ] && ok "Erreurs media/intégrité : 0" || { warn "Erreurs media/intégrité : $MEDIA_ERRORS"; CRITIQUE=1; }
    echo "     Usure (Percentage Used)  : ${PCT_USED:-inconnu}"
    echo "     Réserve disponible       : ${SPARE:-inconnu}"
    echo "     Arrêts non propres       : ${UNSAFE_SHUTDOWNS:-inconnu}"

# ---------------------------------------------------------------------------
# Disques SATA/ATA (SSD ou HDD)
# ---------------------------------------------------------------------------
else
    HEALTH="$(get_nvme_val 'SMART overall-health self-assessment test result')"
    REALLOC="$(get_ata_attr Reallocated_Sector_Ct)"
    PENDING="$(get_ata_attr Current_Pending_Sector)"
    OFFLINE_UNC="$(get_ata_attr Offline_Uncorrectable)"
    CRC="$(get_ata_attr UDMA_CRC_Error_Count)"
    UNCORRECT="$(get_ata_attr Reported_Uncorrect)"

    info "Résultat SMART global : ${HEALTH:-inconnu}"
    [[ "$HEALTH" == *PASSED* ]] && ok "Auto-évaluation SMART : OK" || { warn "Auto-évaluation SMART en échec"; CRITIQUE=1; }

    [ "${REALLOC:-0}" = "0" ] && ok "Secteurs réalloués : 0" || { warn "Secteurs réalloués : $REALLOC"; CRITIQUE=1; }
    [ "${PENDING:-0}" = "0" ] && ok "Secteurs en attente de réallocation : 0" || { warn "Secteurs en attente de réallocation : $PENDING"; CRITIQUE=1; }
    [ "${OFFLINE_UNC:-0}" = "0" ] && ok "Secteurs illisibles (offline) : 0" || { warn "Secteurs illisibles (offline) : $OFFLINE_UNC"; CRITIQUE=1; }
    [ "${UNCORRECT:-0}" = "0" ] && ok "Erreurs non corrigées rapportées : 0" || { warn "Erreurs non corrigées rapportées : $UNCORRECT"; CRITIQUE=1; }

    if [ "${CRC:-0}" = "0" ]; then
        ok "Erreurs CRC (câble/connexion) : 0"
    else
        warn "Erreurs CRC (câble/connexion) : $CRC"
        echo "     → signe de câble/connecteur SATA défectueux, pas forcément le disque lui-même."
    fi
fi

# ---------------------------------------------------------------------------
# Synthèse et propositions
# ---------------------------------------------------------------------------
info "Diagnostic"
if [ "$CRITIQUE" -eq 1 ]; then
    warn "Des indicateurs SMART sont anormaux."
    echo "  → Sauvegardez les données de ce disque sans attendre."
    if [ -n "${CRC:-}" ] && [ "${CRC:-0}" != "0" ] && [ "${REALLOC:-0}" = "0" ] && [ "${PENDING:-0}" = "0" ]; then
        echo "  → Seules les erreurs CRC sont élevées : essayez d'abord un autre câble/port SATA"
        echo "    avant de remplacer le disque."
    else
        echo "  → Les autres indicateurs pointent vers une usure/défaillance du disque : prévoyez"
        echo "    son remplacement."
    fi
else
    ok "Aucun indicateur SMART anormal."
    echo "  Le disque semble matériellement sain. Si le symptôme est « le disque n'apparaît"
    echo "  pas au démarrage à froid sauf si une clé USB est branchée », la piste la plus"
    echo "  probable est un délai d'initialisation du contrôleur au boot, pas une panne :"
    echo "    - mettre à jour le firmware du SSD (utilitaire du fabricant) ;"
    echo "    - mettre à jour le BIOS/UEFI de la carte mère ;"
    echo "    - désactiver Fast Boot / Ultra Fast Boot dans le BIOS ;"
    echo "    - vérifier que le mode CSM/UEFI est cohérent (pas en « auto » hybride)."
fi
