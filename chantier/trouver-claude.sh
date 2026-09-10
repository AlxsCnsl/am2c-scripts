#!/bin/sh
# Où est l'exécutable « claude ». Fichier à sourcer, pas à lancer.
#
#   . chantier/trouver-claude.sh
#   CLAUDE=$(trouver_claude) || { echo introuvable; exit 1; }
#
# Pourquoi ce détour : sur ce poste, Claude Code tourne comme extension VS Code,
# et son binaire vit dans le dossier de l'extension — pas dans le PATH. Un
# terminal ordinaire ne trouve donc rien à appeler « claude », et boucle.sh
# s'arrêtait avant d'avoir commencé. On cherche aux endroits connus plutôt que
# d'exiger une installation supplémentaire.
#
# La variable d'environnement CLAUDE reste prioritaire : elle permet de forcer
# une autre version sans toucher au script.

trouver_claude() {
    if [ -n "${CLAUDE:-}" ]; then
        if command -v "$CLAUDE" >/dev/null 2>&1 || [ -x "$CLAUDE" ]; then
            printf '%s\n' "$CLAUDE"
            return 0
        fi
        return 1
    fi

    if command -v claude >/dev/null 2>&1; then
        printf '%s\n' claude
        return 0
    fi

    for c in "$HOME/.local/bin/claude" "$HOME/.claude/local/claude" \
             /usr/local/bin/claude /opt/claude/claude; do
        if [ -x "$c" ]; then
            printf '%s\n' "$c"
            return 0
        fi
    done

    # Binaire embarqué dans l'extension VS Code. Le numéro de version change à
    # chaque mise à jour : on prend la plus récente au lieu de figer un chemin.
    for d in "$HOME/.var/app/com.visualstudio.code/data/vscode/extensions" \
             "$HOME/.vscode/extensions" \
             "$HOME/.vscode-server/extensions" \
             "$HOME/.vscode-oss/extensions"; do
        [ -d "$d" ] || continue
        c=$(ls -d "$d"/anthropic.claude-code-*/resources/native-binary/claude \
            2>/dev/null | sort -V | tail -1)
        if [ -n "$c" ] && [ -x "$c" ]; then
            printf '%s\n' "$c"
            return 0
        fi
    done

    return 1
}
