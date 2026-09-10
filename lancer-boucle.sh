#!/usr/bin/env bash
#
# lancer-boucle.sh — Contrôle avant vol, puis lance chantier/boucle.sh.
#
# La boucle tourne seule pendant des heures. Ce qui coûte cher, ce n'est pas
# qu'elle s'arrête : c'est qu'elle s'arrête à l'étape 7 pour une raison qu'on
# pouvait constater en dix secondes avant de partir. D'où ce contrôle.
#
# Usage :
#   ./lancer-boucle.sh                 étapes 3 à 11, au premier plan
#   ./lancer-boucle.sh 3 5             étapes 3 à 5
#   ./lancer-boucle.sh --verifier      contrôle seul, ne lance rien
#   ./lancer-boucle.sh --essai         contrôle + un vrai appel d'agent à blanc
#   ./lancer-boucle.sh --fond [3 11]   détaché : survit à la fermeture du terminal
#
# By :
# > alexis consolo (alexis.consolo@outlook.com)
#

set -uo pipefail

info() { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m  ok\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m  ..\033[0m %s\n' "$1" >&2; }
err()  { printf '\033[1;31m  !!\033[0m %s\n' "$1" >&2; }

RACINE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$RACINE" || exit 1

MODE=lancer
case "${1:-}" in
    --verifier) MODE=verifier; shift ;;
    --essai)    MODE=essai;    shift ;;
    --fond)     MODE=fond;     shift ;;
    -h|--help)  sed -n '3,20p' "$0"; exit 0 ;;
esac
DEBUT=${1:-3}
FIN_=${2:-11}

ECHECS=0
recale() { err "$1"; ECHECS=$((ECHECS + 1)); }

# --- Contrôle avant vol -----------------------------------------------------
info "Contrôle avant vol"

# 1. L'exécutable claude. C'est le préalable qui manque le plus souvent : sur ce
#    poste Claude Code est une extension VS Code, son binaire n'est pas dans le
#    PATH d'un terminal ordinaire.
# shellcheck source=chantier/trouver-claude.sh
. "$RACINE/chantier/trouver-claude.sh"
if CLAUDE=$(trouver_claude); then
    ok "claude : $CLAUDE ($("$CLAUDE" --version 2>/dev/null | head -1))"
else
    recale "exécutable « claude » introuvable. Force-le : CLAUDE=/chemin ./lancer-boucle.sh"
fi

# 2. Les permissions de la boucle. Sans ce fichier, les agents tournent en mode
#    -p sans droit d'exécuter quoi que ce soit — pas même la suite de tests.
if [ -f chantier/permissions-boucle.json ] \
   && grep -q '"allow"' chantier/permissions-boucle.json; then
    ok "permissions de la boucle : chantier/permissions-boucle.json"
else
    recale "chantier/permissions-boucle.json absent ou sans liste « allow »"
fi

# 3. L'arbre de travail. boucle.sh refuse de démarrer sale, et il a raison :
#    elle commite et pose un tag par étape, donc elle a besoin d'un point zéro.
if [ -z "$(git status --porcelain)" ]; then
    ok "arbre de travail propre"
else
    recale "arbre de travail sale — commite ou remise avant de lancer :"
    git status --short | sed 's/^/       /' >&2
fi

# 4. Le filet. Toute la sûreté du dispositif repose dessus.
if [ -d serie/tests ] || [ -d ADAM/tests ]; then
    BASE=serie; [ -d ADAM/tests ] && BASE=ADAM
    if (cd "$BASE" && python3 -m unittest discover -s tests -q >/dev/null 2>&1); then
        N_TESTS=$(grep -rhc 'def test_' "$BASE/tests" 2>/dev/null | awk '{s+=$1} END {print s+0}')
        ok "suite de tests verte ($N_TESTS tests, cliquet à $(cat chantier/cliquet-tests 2>/dev/null || echo 0))"
    else
        recale "suite de tests rouge — cd $BASE && python3 -m unittest discover -s tests"
    fi
else
    recale "aucune suite de tests : l'étape 1 se fait et se relit à la main d'abord"
fi

# 5. Les hooks de périmètre doivent être exécutables, sinon ils ne mordent pas.
for h in .claude/hooks/perimetre-garde.py .claude/hooks/documenter-garde.py; do
    if [ -x "$h" ]; then ok "hook exécutable : $h"
    else recale "hook non exécutable : $h  (chmod +x $h)"; fi
done

# 6. Les agents que la boucle appelle par leur nom.
for a in developpeur todo documenter; do
    [ -f ".claude/agents/$a.md" ] || recale "sous-agent absent : .claude/agents/$a.md"
done
[ "$ECHECS" -eq 0 ] && ok "sous-agents developpeur, todo, documenter présents"

# 7. Le périmètre de chaque étape demandée doit exister.
for n in $(seq "$DEBUT" "$FIN_"); do
    grep -q "^$n|" chantier/etapes.conf || recale "étape $n absente de chantier/etapes.conf"
done

echo
if [ "$ECHECS" -ne 0 ]; then
    err "$ECHECS point(s) à régler avant de lancer."
    exit 1
fi
ok "tout est en place pour les étapes $DEBUT à $FIN_."

[ "$MODE" = verifier ] && exit 0

# --- Essai à blanc ----------------------------------------------------------
# Un vrai appel d'agent, qui n'écrit qu'une trace jetable. Il prouve d'un coup
# que le binaire répond, que le fichier de permissions est accepté, que le
# sous-agent est trouvé et que le hook de périmètre est branché.
if [ "$MODE" = essai ]; then
    info "Essai à blanc (un appel d'agent, aucune modification du code)"
    printf '%s\n' "$DEBUT" > chantier/etape-courante
    rm -f chantier/traces/etape-0.md
    "$CLAUDE" -p "Utilise le sous-agent \`developpeur\` pour lire TODO.md et chantier/CONVENTIONS.md, puis écrire uniquement chantier/traces/etape-0.md : dix lignes décrivant ce que tu ferais à l'étape $DEBUT. Ne modifie aucun autre fichier, n'écris pas chantier/etat.env." \
        --settings chantier/permissions-boucle.json --permission-mode acceptEdits
    rm -f chantier/etape-courante
    echo
    if [ -s chantier/traces/etape-0.md ]; then
        ok "l'agent a répondu et sa trace est arrivée : chantier/traces/etape-0.md"
        warn "supprime-la avant de lancer : rm chantier/traces/etape-0.md"
    else
        err "aucune trace écrite — lis la sortie ci-dessus avant de lancer la boucle."
        exit 1
    fi
    exit 0
fi

# --- Lancement --------------------------------------------------------------
if [ "$MODE" = fond ]; then
    JOURNAL="chantier/traces/boucle-$(date '+%Y%m%d-%H%M').log"
    nohup sh chantier/boucle.sh "$DEBUT" "$FIN_" > "$JOURNAL" 2>&1 &
    PID=$!
    info "Boucle détachée (PID $PID), étapes $DEBUT à $FIN_."
    echo "  Suivre :  tail -f $JOURNAL"
    echo "  Arrêter : kill $PID"
    echo "  Où ça en est : cat chantier/JOURNAL.md"
    exit 0
fi

info "Lancement des étapes $DEBUT à $FIN_"
exec sh chantier/boucle.sh "$DEBUT" "$FIN_"
