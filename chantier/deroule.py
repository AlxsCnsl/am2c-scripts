#!/usr/bin/env python3
"""Rend lisible le flux « stream-json » d'un agent lancé en -p.

En mode -p, le format de sortie par défaut (« text ») n'émet que le message
final : impossible de suivre ce que l'agent fabrique pendant qu'il travaille.
Avec --output-format stream-json --verbose, il émet un objet JSON par ligne,
au fil de l'eau. Ce filtre les traduit en lignes courtes :

    · Read      serie/dcon/protocol.py
    · Edit      serie/dcon/familles/__init__.py
    · Bash      python3 -m unittest discover -s tests
    ▸ (le texte que l'agent écrit)
    ═ fin : succès — 41 outils, 2 min 14

Il lit l'entrée standard et écrit sur la sortie standard, sans rien garder en
mémoire : chaque ligne est affichée dès qu'elle arrive (flush explicite, sinon
le tube bufferise et l'affichage arrive par paquets, ce qui ruine l'intérêt).

Toute ligne non-JSON, ou d'une forme inattendue, est laissée telle quelle :
mieux vaut un affichage imparfait qu'un filtre qui avale une erreur.
"""
import json
import sys

# Ce qui identifie le mieux un appel d'outil, par outil. Premier champ présent.
INTERESSANT = ("file_path", "command", "pattern", "path", "prompt",
               "url", "description", "skill", "subagent_type")


def resume_outil(nom, entree):
    """Une ligne : le nom de l'outil, puis ce sur quoi il porte."""
    if not isinstance(entree, dict):
        return nom, ""
    for champ in INTERESSANT:
        valeur = entree.get(champ)
        if isinstance(valeur, str) and valeur.strip():
            valeur = " ".join(valeur.split())
            return nom, valeur[:120] + ("…" if len(valeur) > 120 else "")
    return nom, ""


def duree(ms):
    if not isinstance(ms, (int, float)):
        return ""
    s = int(ms // 1000)
    return f"{s // 60} min {s % 60:02d}" if s >= 60 else f"{s} s"


def main():
    outils = 0
    for ligne in sys.stdin:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            ev = json.loads(ligne)
        except ValueError:
            print(ligne, flush=True)
            continue
        if not isinstance(ev, dict):
            continue

        genre = ev.get("type")

        if genre == "system" and ev.get("subtype") == "init":
            modele = ev.get("model", "?")
            print(f"═ démarrage — modèle {modele}", flush=True)

        elif genre == "assistant":
            contenu = (ev.get("message") or {}).get("content") or []
            for bloc in contenu:
                if not isinstance(bloc, dict):
                    continue
                if bloc.get("type") == "text":
                    texte = (bloc.get("text") or "").strip()
                    for para in texte.splitlines():
                        if para.strip():
                            print(f"  ▸ {para.strip()}", flush=True)
                elif bloc.get("type") == "tool_use":
                    outils += 1
                    nom, quoi = resume_outil(bloc.get("name", "?"),
                                             bloc.get("input"))
                    print(f"  · {nom:<10} {quoi}", flush=True)

        elif genre == "result":
            issue = ev.get("subtype", "?")
            issue = "succès" if issue == "success" else issue
            bouts = [b for b in (f"{outils} outils", duree(ev.get("duration_ms"))) if b]
            print(f"═ fin : {issue} — {', '.join(bouts)}", flush=True)
            resultat = ev.get("result")
            if isinstance(resultat, str) and resultat.strip():
                print(resultat.strip(), flush=True)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
    except KeyboardInterrupt:
        pass
