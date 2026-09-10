#!/bin/sh
# Avancement du chantier, en direct. À lancer dans un volet.
#
#   sh chantier/suivi.sh [secondes]     défaut 5
#   sh chantier/suivi.sh -1             une fois, puis rend la main
#
# Recompte les cases de TODO.md et des TODO/part*.md qu'il référence, au lieu
# de recopier le tableau de bord : le tableau est tenu par un agent, les cases
# sont le fait. L'écart entre les deux est ce qu'on veut voir.

set -u
cd "$(dirname "$0")/.." || exit 1
DELAI=${1:-5}

etapes() {
    awk '
    /^## Étape [0-9]+/ {
        l = $0; sub(/^## Étape /, "", l); n = l + 0
        sub(/^[0-9]+ /, "", l); sub(/^[^ ]* /, "", l); gsub(/`/, "", l)
        if (length(l) > 34) l = substr(l, 1, 33) "…"
        while (length(l) < 34) l = l " "
        e = n; nom[n] = l; if (!vu[n]++) ordre[++k] = n
        next
    }
    /^## / { e = 0; next }
    e && /→ Détail/ { f = $0; sub(/.*\]\(/, "", f); sub(/\).*/, "", f); det[e] = f }
    e && /^[ \t]*- \[/ {
        tot[e]++
        if ($0 ~ /- \[x\]/) { fait[e]++; if ($0 ~ /Fin d/) fin[e] = 1 }
    }
    END {
        for (i = 1; i <= k; i++) {
            n = ordre[i]; mort = 0
            if (det[n] != "") {
                if ((getline l < det[n]) < 0) mort = 1
                else { do { if (l ~ /^[ \t]*- \[/) { tot[n]++; if (l ~ /- \[x\]/) fait[n]++ } }
                       while ((getline l < det[n]) > 0); close(det[n]) }
            }
            printf "%d|%d|%d|%d|%s|%s\n", n, fait[n]+0, tot[n]+0, fin[n]+0, \
                   (mort ? det[n] : ""), nom[n]
        }
    }' TODO.md
}

afficher() {
    COURANTE=$(cat chantier/etape-courante 2>/dev/null)
    ETAT=$(sed -n 's/^ETAT=//p' chantier/etat.env 2>/dev/null | tail -1)
    TESTS=$(grep -rhc 'def test_' serie/tests 2>/dev/null | awk '{s+=$1} END {print s+0}')

    printf '  CHANTIER   %s   étape %s   frein %s   %s tests\n\n' \
           "$(date '+%H:%M:%S')" "${COURANTE:-—}" "${ETAT:-—}" "$TESTS"

    etapes | while IFS='|' read -r n fait tot fin mort titre; do
        b=0; [ "$tot" -gt 0 ] && b=$((fait * 12 / tot))
        i=0
        barre=''
        while [ "$i" -lt 12 ]; do
            if [ "$i" -lt "$b" ]; then barre="$barre#"; else barre="$barre."; fi
            i=$((i + 1))
        done
        if   [ -n "$mort" ];       then etat="lien mort : $mort"
        elif [ "$fin" = 1 ];       then etat="faite"
        elif [ "$n" = "$COURANTE" ]; then etat="en cours"
        elif [ "$fait" -gt 0 ];    then etat="entamée"
        else                            etat=""
        fi
        printf '  %2s %s %s %2s/%-3s %s\n' "$n" "$titre" "$barre" "$fait" "$tot" "$etat"
    done
}

[ "$DELAI" = "-1" ] && { afficher; exit 0; }
while :; do
    printf '\033[H\033[J'
    afficher
    sleep "$DELAI"
done
