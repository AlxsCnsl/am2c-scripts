# Étape 3 — `protocol.py` générique et les familles de protocole

← [TODO.md](../TODO.md)

Aujourd'hui `protocol.py` prétend être « indépendant du module d'E/S » mais
contient `#<addr>S<slot>` et `$<addr>S<slot>6`, qui sont la grammaire du fond de
panier ADAM-5000. Un ADAM-4000 ou un I-7000 lit par `#<addr>`, sans slot.

On ne peut pas vider `protocol.py` sans donner une destination à ce qui en sort :
cette étape crée donc les familles **et** déménage. Le registre de modèles, lui,
attend l'étape 4.

## La structure visée

```
serie/dcon/
    protocol.py           enveloppe ASCII seule
    familles/
        __init__.py       REGISTRE_FAMILLES, trouver()
        base.py           Famille, et rien d'autre
        adam5000.py       rack 4 slots : #aaSn (>) / $aaSn6 (!)
        autonome.py       DCON direct : #aa (>) / $aa6 (!)
```

## Le descripteur de famille

Une **famille** dit *comment on demande* — grammaire de lecture, notion de slot,
commandes générales de sonde. Un **modèle** (étape 4) dit *comment on lit la
réponse*.

| Champ | Rôle |
|---|---|
| `nom` | « adam5000 », « autonome » — la clé du registre |
| `a_slot` | occupe un emplacement de fond de panier, ou module autonome |
| `slots` | nombre d'emplacements (4 pour l'ADAM-5000), `None` sinon |
| `commande_lecture(module, adresse, slot)` | construit la requête, sans habillage |
| `commande_checksum(adresse)` | la trame `%` d'activation, propre à la famille |
| `sondes(adresse)` | commandes générales pour le diagnostic (`$aaM`, `$aaF`, `$aa2`) |

`commande_lecture` consultera `module.nature` pour choisir entre la forme
analogique (`#`, accusé `>`) et la forme tout ou rien (`$…6`, accusé `!`). Tant
que l'étape 4 n'a pas créé `ModuleType`, elle prend le strict nécessaire —
la nature en paramètre — et l'étape 4 lui passera le descripteur.

## Le travail

- [ ] Garder dans `protocol.py` uniquement ce qui est vrai pour toute la famille
      ASCII Advantech/DCON : `TERMINATOR`, `ACK`, `CONFIG_ACK`, `checksum_ascii`,
      `build_frame`, `verify_frame`, `DEFAULT_ADDRESS`. Mettre à jour son
      en-tête : il documente une grammaire d'enveloppe, pas un jeu de commandes.
- [ ] Créer `familles/` avec les quatre fichiers ci-dessus, en y déplaçant
      `read_command`, `digital_read_command` et `ENABLE_CHECKSUM` **sans changer
      les trames qu'ils produisent** : les tests de l'étape 1 les figent
      caractère par caractère et doivent rester verts par simple recâblage
      d'import.
- [ ] `autonome.py` est écrite maintenant mais n'est référencée par aucun
      modèle : c'est la place que prendra un 7070. Elle doit être couverte par un
      test de construction de commande, sinon elle pourrira sans qu'on le voie.
- [ ] Recâbler les six importateurs — `monitor.py`, `cli.py`, `diagnostic.py`,
      `configuration.py`, `__init__.py` et `tests/test_protocol.py` — vers la
      famille `adam5000`. Aucun d'eux ne change de comportement.
- [ ] `IO_SLOTS = 4` cesse d'être une constante de `modules.py` : c'est le champ
      `slots` de la famille `adam5000`, consulté par `settings` et `diagnostic`.

La case **Fin d'étape** est dans [TODO.md](../TODO.md), avec les autres.
