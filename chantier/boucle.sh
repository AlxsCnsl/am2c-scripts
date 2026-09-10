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

# Où est « claude ». Sur un poste où Claude Code tourne comme extension VS Code,
# le binaire n'est pas dans le PATH : on va le chercher là où il vit.
. "$RACINE/chantier/trouver-claude.sh"
CLAUDE=$(trouver_claude) || CLAUDE=claude

# Permissions des agents pendant la boucle. Indispensable : en mode -p personne
# ne répond aux demandes de permission, donc tout appel Bash non listé dans ce
# fichier est refusé d'office — y compris la suite de tests. Passé par
# --settings, il ne bride que la boucle, jamais tes sessions interactives.
REGLAGES="$RACINE/chantier/permissions-boucle.json"

# Garde-temps par agent. Un agent qui ne rend jamais la main figerait la boucle
# sans rien écrire dans etat.env : le frein reste ABSENT et l'étape s'arrête.
DELAI=${DELAI:-3600}
if command -v timeout >/dev/null 2>&1; then
    borner() { timeout "$DELAI" "$@"; }
else
    borner() { "$@"; }
fi

# Lance un agent et donne à voir ce qu'il fait, pendant qu'il le fait.
#
# En -p, le format de sortie par défaut n'émet que le message final : la boucle
# restait muette pendant toute une étape. « stream-json » émet un objet par
# ligne au fil de l'eau, que chantier/deroule.py traduit en lignes lisibles.
#
# Le JSON brut est conservé à côté (etape-<N>.jsonl) : c'est la seule trace
# complète si l'affichage se trompe. Le filtre, lui, ne peut rien avaler — une
# ligne qu'il ne comprend pas est recopiée telle quelle.
#
#   agent <numéro d'étape> <consigne>
agent() {
    _n=$1
    borner "$CLAUDE" -p "$2" \
        --settings "$REGLAGES" --permission-mode acceptEdits \
        --output-format stream-json --verbose 2>&1 \
        | tee -a "chantier/traces/etape-$_n.jsonl" \
        | python3 "$RACINE/chantier/deroule.py" \
        | tee -a "chantier/traces/sortie-etape-$_n.log"
}

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
command -v "$CLAUDE" >/dev/null 2>&1 || [ -x "$CLAUDE" ] || {
    echo "Exécutable « claude » introuvable — ni dans le PATH, ni dans les"
    echo "emplacements connus (voir chantier/trouver-claude.sh)."
    echo "Force-le au besoin :  CLAUDE=/chemin/vers/claude sh chantier/boucle.sh"
    exit 1
}
[ -f "$REGLAGES" ] || { echo "Fichier de permissions absent : $REGLAGES"; exit 1; }
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
    agent "$N" "Utilise le sous-agent \`developpeur\` pour exécuter l'étape $N du chantier décrit dans TODO.md. Lis d'abord chantier/CONVENTIONS.md."

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
    agent "$N" "Utilise le sous-agent \`todo\` pour constater l'état de l'étape $N et mettre TODO.md d'aplomb."
    agent "$N" "Utilise le sous-agent \`documenter\` après le travail de l'étape $N du chantier."

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
