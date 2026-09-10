# Étape 7 — `config.json` : décrire une installation, et s'en servir

← [TODO.md](../TODO.md)

Deux manques : le format ne sait décrire qu'un rack à slots, et `--config`
affiche puis quitte sur « La lecture automatique de ces slots n'est pas encore
branchée » ([cli.py:284](../ADAM/adam5000/cli.py#L284) — chemin d'avant le
renommage de l'étape 2).

## Le format visé

Un `slot` facultatif, absent pour un module autonome :

```json
{
  "modules": [
    {"slot": 0, "module": "5081", "vitesse": 38400, "checksum": true, "adresse": "01"},
    {"slot": 2, "module": "5050", "vitesse": 38400, "checksum": true, "adresse": "01"},
    {"module": "7070", "vitesse": 9600, "checksum": false, "adresse": "03"}
  ]
}
```

## Le travail

- [ ] Lire le nouveau format `modules`, avec `slot` facultatif.
- [ ] Accepter l'ancienne clé `slots` en lecture, pour ne pas casser le
      `config.json` existant ; écrire `modules` dans les exemples et dans
      `serie/config.json`.
- [ ] `read_module()` délègue au registre (`modules.trouver`) : plus de liste de
      références dans `settings.py`.
- [ ] Validation croisée : `slot` **obligatoire** si `module.famille.a_slot`,
      **refusé** sinon, et borné par `module.famille.slots`. L'unicité reste par
      slot ; pour les modules autonomes, l'unicité porte sur le couple
      (adresse, vitesse).
- [ ] `SlotSettings` devient `ModuleSettings`, avec `slot` pouvant valoir `None`.
- [ ] **Branchement réel :** une option qui construit les `Monitor` depuis le
      fichier et les interroge à tour de rôle sur un port unique, en respectant
      la vitesse et l'état de checksum de chaque bloc. Attention : changer de
      vitesse impose de refermer et rouvrir le port — regrouper les lectures par
      vitesse et laisser retomber le convertisseur entre deux, comme le fait déjà
      [diagnostic.py:101](../ADAM/adam5000/diagnostic.py#L101).
- [ ] Garder `--config` seul en affichage/validation : contrôler le fichier sans
      toucher à la liaison reste utile.
- [ ] Retirer la phrase « pas encore branchée » de `show_settings()`.

La case **Fin d'étape** est dans [TODO.md](../TODO.md), avec les autres.
