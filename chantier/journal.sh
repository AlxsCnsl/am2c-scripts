#!/bin/sh
# Le frein et le journal, en direct. À lancer dans un volet.
#
#   sh chantier/journal.sh [secondes]   défaut 5
#   sh chantier/journal.sh -1           une fois, puis rend la main
#
# etat.env est ce qui arrête la boucle, JOURNAL.md est ce qui s'est passé.

set -u
cd "$(dirname "$0")/.." || exit 1
DELAI=${1:-5}

afficher() {
    COURANTE=$(cat chantier/etape-courante 2>/dev/null)
    ETAT=$(sed -n 's/^ETAT=//p' chantier/etat.env 2>/dev/null | tail -1)
    RAISON=$(sed -n 's/^RAISON=//p' chantier/etat.env 2>/dev/null | tail -1)

    printf '  FREIN      %s\n' "$(date '+%H:%M:%S')"
    printf '  ÉTAT       %s\n' "${ETAT:-—}"
    printf '  RAISON     %s\n' "${RAISON:-—}"
    printf '  ÉTAPE      %s\n' "${COURANTE:-—}"
    [ -n "$COURANTE" ] && [ -f "chantier/traces/etape-$COURANTE.md" ] \
        && printf '  TRACE      chantier/traces/etape-%s.md\n' "$COURANTE"

    printf '\n  JOURNAL\n'
    if grep -q '|' chantier/JOURNAL.md 2>/dev/null; then
        grep '|' chantier/JOURNAL.md | grep -v '^#' | tail -15 | sed 's/^/    /'
    else
        printf '    —\n'
    fi
}

[ "$DELAI" = "-1" ] && { afficher; exit 0; }
while :; do
    printf '\033[H\033[J'
    afficher
    sleep "$DELAI"
done
