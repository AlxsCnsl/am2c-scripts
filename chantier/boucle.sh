#!/bin/sh
# Pilote du chantier. Déroule les étapes du TODO tant que rien ne s'y oppose.
#
#   sh chantier/boucle.sh [première] [dernière]      (défaut : 3 11)
#
# Une étape se déroule ainsi :
#   1. le frein est effacé  — un OK périmé ne peut pas être hérité
#   2. l'agent « developpeur » fait le travail et écrit sa trace
#   3. les gardes mécaniques constatent          → échec = arrêt
#   4. le frein est lu                           → autre chose que OK = arrêt
#   5. l'agent « todo » coche, l'agent « documenter » suit
#   6. les gardes reconstatent, puis commit + tag etape-<N>
#
# Rien dans cette chaîne ne permet à une IA de dire « continue ». Elle peut
# seulement dire « arrête », par etat.env, ou faire échouer une garde.

set -u
RACINE=$(cd "$(dirname "$0")/.." && pwd)
cd "$RACINE" || exit 1

DEBUT=${1:-3}
FIN=${2:-11}
CLAUDE=${CLAUDE:-claude}

arret() {
    echo
    echo "═══ ARRÊT à l'étape $1 ═══"
    echo "$2"
    echo
    echo "Trace  : chantier/traces/etape-$1.md"
    echo "Retour : git reset --hard etape-$((1 - 1))   (si le commit a eu lieu)"
    printf '%s | étape %s | ARRÊT | %s\n' "$(date '+%Y-%m-%d %H:%M')" "$1" "$2" >> chantier/JOURNAL.md
    exit 1
}

# --- Préalables -------------------------------------------------------------
[ -n "$(git status --porcelain)" ] && {
    echo "L'arbre de travail n'est pas propre. Commite ou remise avant de lancer."
    git status --short
    exit 1
}
command -v "$CLAUDE" >/dev/null 2>&1 || { echo "« $CLAUDE » introuvable dans le PATH."; exit 1; }
[ -d ADAM/tests ] || [ -d serie/tests ] || {
    echo "Aucune suite de tests. L'étape 1 se fait et se relit à la main avant"
    echo "de lancer la boucle : tout le dispositif repose sur la qualité de ce filet."
    exit 1
}

N=$DEBUT
while [ "$N" -le "$FIN" ]; do
    echo
    echo "═══ Étape $N ═══"

    # 0. Publier l'étape courante : le hook de périmètre la lit.
    printf '%s\n' "$N" > chantier/etape-courante

    # 1. Effacer le frein. Sans ça, un agent qui plante laisse l'état précédent.
    printf 'ETAT=ABSENT\nRAISON=l agent n a rien ecrit\n' > chantier/etat.env

    # 2. Le développeur
    "$CLAUDE" -p "Utilise le sous-agent \`developpeur\` pour exécuter l'étape $N du chantier décrit dans TODO.md. Lis d'abord chantier/CONVENTIONS.md." \
        --permission-mode acceptEdits >> chantier/traces/sortie-etape-$N.log 2>&1

    # 3. Les gardes
    if ! sh chantier/gardes.sh "$N" > chantier/traces/gardes-etape-$N.log 2>&1; then
        cat chantier/traces/gardes-etape-$N.log
        arret "$N" "gardes en échec (voir chantier/traces/gardes-etape-$N.log)"
    fi

    # 4. Le frein
    ETAT=$(sed -n 's/^ETAT=//p' chantier/etat.env | tail -1)
    RAISON=$(sed -n 's/^RAISON=//p' chantier/etat.env | tail -1)
    [ "$ETAT" = "OK" ] || arret "$N" "$ETAT — $RAISON"

    # 5. Le plan, puis la documentation
    "$CLAUDE" -p "Utilise le sous-agent \`todo\` pour constater l'état de l'étape $N et mettre TODO.md d'aplomb." \
        --permission-mode acceptEdits >> chantier/traces/sortie-etape-$N.log 2>&1
    "$CLAUDE" -p "Utilise le sous-agent \`documenter\` après le travail de l'étape $N du chantier." \
        --permission-mode acceptEdits >> chantier/traces/sortie-etape-$N.log 2>&1

    # 6. Reconstat, puis on grave
    if ! sh chantier/gardes.sh "$N" > chantier/traces/gardes-etape-$N-apres.log 2>&1; then
        cat chantier/traces/gardes-etape-$N-apres.log
        arret "$N" "gardes en échec après le passage de todo/documenter"
    fi

    git add -A
    git commit -q -F - <<COMMIT
chantier : étape $N

$(sed -n '1,40p' chantier/traces/etape-$N.md 2>/dev/null)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
COMMIT
    git tag -f "etape-$N" >/dev/null
    printf '%s | étape %s | franchie | %s\n' "$(date '+%Y-%m-%d %H:%M')" "$N" "$(git rev-parse --short HEAD)" >> chantier/JOURNAL.md
    echo "étape $N franchie et gravée (tag etape-$N)"

    N=$((N + 1))
done

echo
rm -f chantier/etape-courante
echo "Toutes les étapes de $DEBUT à $FIN sont franchies."
echo "Il reste à relire le diff complet : git diff etape-$((DEBUT - 1))..HEAD"
