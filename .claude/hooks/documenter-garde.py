#!/usr/bin/env python3
"""Garde-fou du sous-agent « documenter ».

Branché en hook `PreToolUse` dans le frontmatter de `.claude/agents/documenter.md`,
donc actif seulement pendant que cet agent tourne.

Il applique mécaniquement les deux limites que le prompt de l'agent énonce :

  1. toute écriture (`Write`, `Edit`) doit viser un chemin sous `docs/` ;
  2. `Bash` est un outil d'inspection : liste blanche de commandes en lecture
     seule, aucune redirection vers un fichier.

Refus = code de sortie 2 + motif sur stderr, ce qui bloque l'appel et rend le
motif à l'agent. Code 0 = on ne décide rien, le flux de permissions normal
reprend la main.
"""

import json
import os
import re
import sys

# Commandes d'inspection tolérées comme premier mot d'un segment de shell.
# Tout ce qui n'est pas dans cette liste est refusé : une liste blanche se
# relit, une liste noire s'oublie.
AUTORISEES = {
    "awk", "basename", "cat", "cd", "column", "cut", "date", "diff", "dirname",
    "echo", "egrep", "env", "false", "fgrep", "file", "find", "git", "grep",
    "head", "ls", "nl", "od", "printf", "pwd", "python", "python3", "readlink",
    "realpath", "rg", "sed", "sort", "stat", "tail", "test", "tr", "true",
    "uniq", "wc", "which", "xxd",
}

# Sous-commandes `git` qui ne modifient ni l'arbre de travail ni l'index.
GIT_LECTURE = {
    "blame", "cat-file", "describe", "diff", "grep", "log", "ls-files",
    "ls-tree", "rev-parse", "shortlog", "show", "status",
}

# Marqueurs d'écriture cherchés dans un `python3 -c "..."`.
PYTHON_ECRITURE = re.compile(
    r"""open\s*\([^)]*['"][rwax+bt]*[wax+][rwax+bt]*['"]"""
    r"""|\bos\.(remove|unlink|rename|replace|mkdir|makedirs|rmdir)"""
    r"""|\bshutil\."""
    r"""|\.write_text\s*\(|\.write_bytes\s*\(|\.write\s*\(|\.writelines\s*\("""
    r"""|\bsubprocess\.|\bos\.system\s*\(""",
    re.IGNORECASE,
)

# Options de `find` qui exécutent ou effacent.
FIND_ECRITURE = re.compile(r"(?<![\w-])-(delete|exec|execdir|ok|okdir|fprint\w*|fls)(?![\w-])")

# `sed` qui réécrit le fichier sur place.
SED_ECRITURE = re.compile(r"(?<![\w-])(-i|--in-place)(?![\w-])")


def refuser(motif):
    print("documenter : " + motif, file=sys.stderr)
    sys.exit(2)


def squelette(commande):
    """Rend la commande avec le contenu des guillemets remplacé par des « _ ».

    Les indices restent alignés sur la chaîne d'origine. Le but est de repérer
    les opérateurs du shell (`>`, `;`, `|`…) sans se faire piéger par un motif
    de recherche entre guillemets — `grep -rn "a > b" docs/` n'est pas une
    redirection.
    """
    sortie = []
    guillemet = None
    i = 0
    while i < len(commande):
        c = commande[i]
        if guillemet:
            if c == "\\" and guillemet == '"':
                sortie.append("__")
                i += 2
                continue
            sortie.append("_")
            if c == guillemet:
                guillemet = None
        elif c in ("'", '"'):
            guillemet = c
            sortie.append("_")
        elif c == "\\":
            sortie.append("__")
            i += 2
            continue
        else:
            sortie.append(c)
        i += 1
    return "".join(sortie)


def verifier_redirections(sq, commande):
    """Refuse toute redirection de sortie, sauf vers /dev/null ou un autre flux."""
    for m in re.finditer(r">", sq):
        reste = sq[m.start():]
        if re.match(r">>?\s*(&\s*\d?|/dev/null)", reste):
            continue
        refuser(
            "Bash est en lecture seule ici : la redirection dans « %s » écrirait "
            "un fichier. Les documents passent par Write et Edit." % commande.strip()
        )


def verifier_segment(segment, commande):
    mots = segment.split()
    while mots and re.match(r"^[A-Za-z_][A-Za-z_0-9]*=", mots[0]):
        mots.pop(0)  # affectation d'environnement en préfixe
    if not mots:
        return
    programme = os.path.basename(mots[0])
    if programme not in AUTORISEES:
        refuser(
            "Bash est en lecture seule ici : « %s » n'est pas une commande "
            "d'inspection autorisée. Pour écrire dans docs/, utilise Write ou Edit."
            % programme
        )
    if programme == "git":
        sous = next((m for m in mots[1:] if not m.startswith("-")), "")
        if sous not in GIT_LECTURE:
            refuser("« git %s » modifie le dépôt ; seule la lecture est autorisée." % sous)
    elif programme == "sed" and SED_ECRITURE.search(segment):
        refuser("« sed -i » réécrit le fichier ; passe par Edit.")
    elif programme == "find" and FIND_ECRITURE.search(segment):
        refuser("cette option de « find » exécute ou efface ; seule la lecture est autorisée.")
    elif programme in ("python", "python3") and PYTHON_ECRITURE.search(commande):
        refuser(
            "ce python3 écrit ou exécute quelque chose ; il ne sert qu'à vérifier "
            "une valeur (par exemple parse_5050)."
        )


def verifier_commande(commande):
    if not commande.strip():
        return
    sq = squelette(commande)
    verifier_redirections(sq, commande)
    for debut, fin in decouper(sq):
        verifier_segment(commande[debut:fin], commande)


def decouper(sq):
    """Découpe le squelette aux séparateurs de commandes et rend les bornes."""
    bornes = []
    debut = 0
    for m in re.finditer(r"(\|\||&&|[;|&\n()`]|\$\()", sq):
        bornes.append((debut, m.start()))
        debut = m.end()
    bornes.append((debut, len(sq)))
    return bornes


def verifier_chemin(chemin, racine, cwd):
    if not chemin:
        refuser("écriture demandée sans file_path.")
    if not os.path.isabs(chemin):
        chemin = os.path.join(cwd, chemin)
    cible = os.path.realpath(chemin)
    docs = os.path.realpath(os.path.join(racine, "docs"))
    if cible != docs and not cible.startswith(docs + os.sep):
        refuser(
            "tu n'écris que dans docs/ ; « %s » est en dehors. Si un fichier source "
            "doit changer, dis-le dans ton rapport et laisse-le tel quel." % cible
        )


def main():
    try:
        entree = json.load(sys.stdin)
    except (ValueError, OSError):
        sys.exit(0)  # entrée illisible : on ne décide rien
    if not isinstance(entree, dict):
        sys.exit(0)
    outil = entree.get("tool_name") or ""
    arguments = entree.get("tool_input") or {}
    if not isinstance(arguments, dict):
        arguments = {}
    cwd = entree.get("cwd") or os.getcwd()
    racine = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)

    if outil in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        verifier_chemin(arguments.get("file_path") or "", racine, cwd)
    elif outil == "Bash":
        verifier_commande(arguments.get("command") or "")
    sys.exit(0)


if __name__ == "__main__":
    main()
