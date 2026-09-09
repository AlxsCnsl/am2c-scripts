#!/usr/bin/env python3
"""Garde de périmètre des agents du chantier.

Branché en hook `PreToolUse` dans le frontmatter des agents `developpeur` et
`todo`, donc actif seulement pendant qu'ils tournent.

Il refuse toute écriture hors des chemins que l'étape courante autorise. La
source est `chantier/etapes.conf` — la même que celle que lit
`chantier/gardes.sh`, pour qu'il n'y ait jamais deux définitions du périmètre.

Différence avec le constat de `gardes.sh` : ici on **empêche** au lieu de
constater après coup. L'agent reçoit le refus et son motif, il se corrige dans
le tour, et l'utilisateur n'a rien à arbitrer.

Ce hook ne filtre pas les commandes shell, délibérément. Un interpréteur
généraliste ne se rend pas inoffensif par expression régulière, et l'agent de
développement a besoin de lancer du Python. Le périmètre porte sur ce qui est
vérifiable — les chemins écrits — et pas sur ce qui ne l'est pas.

Refus = code de sortie 2 + motif sur stderr. Code 0 = on ne décide rien.
"""

import fnmatch
import json
import os
import sys

TOUJOURS = (
    "chantier/etat.env",
    "chantier/traces/*",
    "chantier/JOURNAL.md",
    "chantier/cliquet-tests",
    "TODO.md",
    "TODO/*",
)


def refuser(motif):
    print("périmètre : " + motif, file=sys.stderr)
    sys.exit(2)


def paquet(racine):
    """Le renommage de l'étape 2 déplace tout : on détecte au lieu de figer."""
    if os.path.isdir(os.path.join(racine, "serie", "dcon")):
        return "serie/dcon", "serie"
    if os.path.isdir(os.path.join(racine, "ADAM", "adam5000")):
        return "ADAM/adam5000", "ADAM"
    return None, None


def motifs(racine):
    """Les chemins autorisés à l'étape courante, ou None si on ne sait pas."""
    try:
        with open(os.path.join(racine, "chantier", "etape-courante")) as f:
            etape = f.read().strip()
    except OSError:
        return None  # hors boucle : on ne décide rien
    if not etape.isdigit():
        return None

    paq, base = paquet(racine)
    if paq is None:
        refuser("paquet introuvable : ni serie/dcon ni ADAM/adam5000.")

    try:
        with open(os.path.join(racine, "chantier", "etapes.conf")) as f:
            lignes = f.readlines()
    except OSError:
        return None

    for ligne in lignes:
        if ligne.startswith(etape + "|"):
            bruts = ligne.split("|", 1)[1].split("|")[0].split()
            return [
                m.replace("@PAQ@", paq).replace("@BASE@", base) for m in bruts
            ] + list(TOUJOURS)

    refuser("l'étape %s ne figure pas dans chantier/etapes.conf." % etape)


def verifier(chemin, racine, cwd, permis):
    if not chemin:
        refuser("écriture demandée sans file_path.")
    if not os.path.isabs(chemin):
        chemin = os.path.join(cwd, chemin)
    cible = os.path.realpath(chemin)
    racine = os.path.realpath(racine)
    if cible != racine and not cible.startswith(racine + os.sep):
        refuser("« %s » est hors du dépôt." % cible)

    relatif = os.path.relpath(cible, racine)
    for m in permis:
        if fnmatch.fnmatch(relatif, m) or fnmatch.fnmatch(relatif, m.rstrip("/") + "/*"):
            return

    refuser(
        "« %s » est hors du périmètre de cette étape.\n"
        "Autorisé ici : %s\n"
        "Si le travail demandé exige vraiment ce fichier, ne contourne pas : "
        "arrête-toi avec ETAT=PLAN_FAUX dans chantier/etat.env et dis pourquoi "
        "dans ta trace." % (relatif, " ".join(permis))
    )


def main():
    try:
        entree = json.load(sys.stdin)
    except (ValueError, OSError):
        sys.exit(0)
    if not isinstance(entree, dict):
        sys.exit(0)
    outil = entree.get("tool_name") or ""
    if outil not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        sys.exit(0)

    arguments = entree.get("tool_input") or {}
    if not isinstance(arguments, dict):
        arguments = {}
    cwd = entree.get("cwd") or os.getcwd()
    racine = os.environ.get("CLAUDE_PROJECT_DIR") or cwd

    permis = motifs(racine)
    if permis is None:
        sys.exit(0)  # pas de boucle en cours : le flux normal reprend la main
    verifier(arguments.get("file_path") or "", racine, cwd, permis)
    sys.exit(0)


if __name__ == "__main__":
    main()
