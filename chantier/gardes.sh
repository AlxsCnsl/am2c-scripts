#!/bin/sh
# Gardes mécaniques du chantier. Aucun jugement : des constats.
#
#   sh chantier/gardes.sh <numéro d'étape>
#     sortie 0 → l'étape est franchissable
#     sortie 1 → arrêt, les motifs sont écrits sur la sortie standard
#
# Règle qui porte tout le dispositif : ce script est le SEUL à pouvoir dire
# « on continue ». Un agent ne peut qu'arrêter la boucle (chantier/etat.env),
# jamais la relancer. Aucune valeur écrite par une IA n'ouvre cette porte.

set -u
set -f   # pas de développement des motifs contre le disque :
         # « @PAQ@/*.py » doit rester un motif, pas devenir une liste.
RACINE=$(cd "$(dirname "$0")/.." && pwd)
cd "$RACINE" || exit 1

ETAPE=${1:-}
[ -n "$ETAPE" ] || { echo "usage : sh chantier/gardes.sh <numéro d'étape>" >&2; exit 1; }

ECHECS=0
refus() { echo "REFUS   $*"; ECHECS=$((ECHECS + 1)); }
ok()    { echo "ok      $*"; }

# --- Où est le paquet -------------------------------------------------------
# Le renommage de l'étape 2 déplace tout : on le détecte au lieu de le figer.
if [ -d serie/dcon ]; then
    PAQ=serie/dcon; BASE=serie
elif [ -d ADAM/adam5000 ]; then
    PAQ=ADAM/adam5000; BASE=ADAM
else
    echo "REFUS   paquet introuvable : ni serie/dcon ni ADAM/adam5000."
    exit 1
fi

LIGNE=$(sed -n "s/^$ETAPE|//p" chantier/etapes.conf)
[ -n "$LIGNE" ] || { refus "étape $ETAPE absente de chantier/etapes.conf"; exit 1; }
MOTIFS=$(printf '%s' "$LIGNE" | cut -d'|' -f1 | sed "s|@PAQ@|$PAQ|g; s|@BASE@|$BASE|g")
# Sorties que tout agent doit pouvoir écrire, à toutes les étapes.
MOTIFS="$MOTIFS chantier/etape-courante chantier/etat.env chantier/traces/* chantier/JOURNAL.md chantier/cliquet-tests TODO.md TODO/*"

# --- 1. Périmètre -----------------------------------------------------------
# Constat après coup. La prévention, elle, est dans le hook PreToolUse.
autorise() {
    for m in $MOTIFS; do
        case "$1" in $m) return 0 ;; esac
    done
    return 1
}
HORS=""
for f in $(git status --porcelain | sed 's/^...//; s/.* -> //'); do
    autorise "$f" || HORS="$HORS $f"
done
if [ -n "$HORS" ]; then
    refus "hors périmètre de l'étape $ETAPE :$HORS"
else
    ok "périmètre respecté"
fi

# --- 2. Le plan ne se réécrit pas -------------------------------------------
# TODO.md ne change que par des cases et des lignes de tableau de bord.
OFFENSES=$(git diff -U0 -- TODO.md TODO/ 2>/dev/null \
    | grep '^[+-]' | grep -v '^+++' | grep -v '^---' \
    | grep -Ev '^[+-] *- \[[ x]\]' \
    | grep -Ev '^[+-]\|')
if [ -n "$OFFENSES" ]; then
    refus "TODO.md modifié ailleurs que sur une case ou le tableau :"
    printf '%s\n' "$OFFENSES" | sed 's/^/        /'
else
    ok "plan intact (cases et tableau seulement)"
fi

# --- 3. La mesure ne se réécrit pas -----------------------------------------
# Sans cette garde, la boucle peut passer au vert en affaiblissant ses tests.
# Interdire toute retouche serait faux : un renommage déplace légitimement des
# imports. Ce qu'on interdit, c'est que le filet RÉTRÉCISSE — un cliquet.
COMPTE=0
if [ -d "$BASE/tests" ]; then
    COMPTE=$(grep -rhc 'def test_' "$BASE/tests" 2>/dev/null | awk '{s+=$1} END {print s+0}')
fi
PRECEDENT=$(cat chantier/cliquet-tests 2>/dev/null || echo 0)
if [ "$COMPTE" -lt "$PRECEDENT" ]; then
    refus "le filet a rétréci : $COMPTE tests contre $PRECEDENT à l'étape précédente"
else
    ok "cliquet des tests : $COMPTE (jamais moins de $PRECEDENT)"
fi

# --- 4. Invariants ----------------------------------------------------------
# Les invariants du TODO, en prose, ne survivent pas à une boucle. Ceux qui
# se mécanisent sont ici. Les autres sont listés dans chantier/MISE-EN-PLACE.md
# comme restant à ta charge — mieux vaut une garde honnête qu'une garde qui
# rassure à tort.

# I2 — diagnostic et monitor n'émettent jamais de trame de configuration.
TRAMES=$(grep -rln "['\"]%[0-9]" "$PAQ" 2>/dev/null \
    | grep -Ev "(configuration|protocol)\.py$" | grep -v "/familles/" || true)
if [ -n "$TRAMES" ]; then
    refus "trame « % » hors de configuration.py / protocol.py / familles/ :"
    printf '%s\n' "$TRAMES" | sed 's/^/        /'
else
    ok "I2  aucune trame de configuration hors de sa couche"
fi

# I4 — aucun affichage dans les couches basses.
BAS=$(find "$PAQ" -name '*.py' ! -name 'cli.py' ! -path '*/cli/*' 2>/dev/null)
BAVARDS=$(grep -ln '^\s*print(' $BAS 2>/dev/null || true)
if [ -n "$BAVARDS" ]; then
    refus "print() dans une couche basse :"
    printf '%s\n' "$BAVARDS" | sed 's/^/        /'
else
    ok "I4  aucun affichage sous la couche cli"
fi

# I6 — aucune dépendance externe. Liste blanche du standard utilisé ici.
STD="$(basename "$PAQ") argparse collections datetime enum fcntl json os pathlib re select struct sys termios time typing unittest dataclasses itertools math"
ETRANGERS=""
for mod in $(grep -rhE '^\s*(import|from) [a-zA-Z]' $(find "$PAQ" "$BASE/tests" -name '*.py' 2>/dev/null) 2>/dev/null \
        | sed -E 's/^\s*(import|from) ([a-zA-Z_][a-zA-Z0-9_]*).*/\2/' | sort -u); do
    case " $STD " in *" $mod "*) ;; *) ETRANGERS="$ETRANGERS $mod" ;; esac
done
if [ -n "$ETRANGERS" ]; then
    refus "import hors bibliothèque standard :$ETRANGERS"
else
    ok "I6  aucune dépendance externe"
fi

# I5 — HUPCL effacé et tcdrain après écriture.
if [ "$(grep -c 'HUPCL\|tcdrain' "$PAQ/serial_port.py" 2>/dev/null || echo 0)" -lt 2 ]; then
    refus "I5  HUPCL ou tcdrain a disparu de serial_port.py"
else
    ok "I5  HUPCL et tcdrain en place"
fi

# I3 — pas de purge du tampon dans la boucle de mesure.
if grep -q 'flush_input' "$PAQ/monitor.py" 2>/dev/null; then
    refus "I3  flush_input() est revenu dans monitor.py"
else
    ok "I3  aucune purge dans la boucle de mesure"
fi

# I7 — --scan passe avant tout dans le dispatch.
CLI=$(ls "$PAQ/cli.py" "$PAQ/cli/__init__.py" 2>/dev/null | head -1)
if [ -n "$CLI" ]; then
    L_SCAN=$(grep -n 'args\.scan\b' "$CLI" | tail -1 | cut -d: -f1)
    L_AUTRE=$(grep -n 'args\.enable_checksum\|args\.raw' "$CLI" | head -1 | cut -d: -f1)
    if [ -n "$L_SCAN" ] && [ -n "$L_AUTRE" ] && [ "$L_SCAN" -gt "$L_AUTRE" ]; then
        refus "I7  --scan n'est plus en tête du dispatch"
    else
        ok "I7  --scan en tête du dispatch"
    fi
fi

# I8 — le port série n'entre pas dans le fichier de réglages.
if grep -q '"port"' "$BASE/config.json" 2>/dev/null; then
    refus "I8  « port » est entré dans config.json"
else
    ok "I8  le port reste hors du fichier de réglages"
fi

# --- 5. La suite de tests ---------------------------------------------------
if [ -d "$BASE/tests" ]; then
    if (cd "$BASE" && python3 -m unittest discover -s tests -q >/dev/null 2>&1); then
        ok "suite de tests verte"
    else
        refus "suite de tests rouge — relance : cd $BASE && python3 -m unittest discover -s tests"
    fi
elif [ "$ETAPE" -gt 1 ]; then
    refus "aucune suite de tests dans $BASE/tests : le filet de l'étape 1 a disparu"
fi

# --- 6. Critère propre à l'étape --------------------------------------------
case "$ETAPE" in
2)
    # chantier/ et TODO* décrivent la migration : ils citent forcément les deux
    # noms, et les gardes elles-mêmes doivent détecter l'avant comme l'après.
    RESTES=$(grep -rl 'adam5000' --include='*.py' --include='*.sh' --include='*.md' . 2>/dev/null \
        | grep -v '^\./chantier/' | grep -v '^\./TODO' | grep -v 'perimetre-garde\.py$' || true)
    [ -n "$RESTES" ] && { refus "le nom « adam5000 » subsiste :"; printf '%s\n' "$RESTES" | sed 's/^/        /'; } \
                     || ok "plus aucune trace du nom adam5000 hors des fichiers de migration"
    ;;
3)
    grep -qi 'slot\|5050\|5081' "$PAQ/protocol.py" 2>/dev/null \
        && refus "protocol.py mentionne encore un slot ou une référence de module" \
        || ok "protocol.py ne parle que d'enveloppe"
    ;;
5)
    grep -qi '5050\|5081' "$PAQ/monitor.py" 2>/dev/null \
        && refus "monitor.py mentionne encore un modèle précis" \
        || ok "monitor.py est agnostique du modèle"
    ;;
6)
    LONG=$(find "$PAQ/cli" -name '*.py' 2>/dev/null | xargs wc -l 2>/dev/null \
        | awk '$2 != "total" && $1 > 170 {print $2" ("$1" lignes)"}')
    [ -n "$LONG" ] && { refus "fichier de cli/ trop long :"; printf '%s\n' "$LONG" | sed 's/^/        /'; } \
                   || ok "aucun fichier de cli/ ne dépasse 170 lignes"
    ;;
esac

# --- Verdict ----------------------------------------------------------------
echo
if [ "$ECHECS" -eq 0 ]; then
    printf '%s\n' "$COMPTE" > chantier/cliquet-tests
    echo "GARDES OK — étape $ETAPE franchissable."
    exit 0
fi
echo "GARDES EN ÉCHEC ($ECHECS) — étape $ETAPE bloquée."
exit 1
