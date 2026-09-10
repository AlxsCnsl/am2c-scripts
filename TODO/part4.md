# Étape 4 — Familles de protocole et registre de modules

← [TODO.md](../TODO.md)

Le cœur du chantier. Deux registres, deux métiers nets :

- une **famille** dit *comment on demande* — grammaire de lecture, notion de
  slot, commandes générales de sonde ;
- un **modèle** dit *comment on lit la réponse* — nombre de voies, largeur,
  décodage, conversion éventuelle.

Un ADAM-5081 et un ADAM-5050 partagent la famille `adam5000` (fond de panier à
slots) et diffèrent par leur décodage. Un ICPcon 7070 changera de famille sans
rien changer au reste.

## La structure visée

```
serie/dcon/
    protocol.py           enveloppe ASCII seule (étape 3)
    familles/
        __init__.py       REGISTRE_FAMILLES
        base.py           Famille, et rien d'autre
        adam5000.py       rack 4 slots : #aaSn (>) / $aaSn6 (!)
        autonome.py       DCON direct : #aa (>) / $aa6 (!)
    modules/
        __init__.py       REGISTRE, references(), trouver()
        base.py           ModuleType, et rien d'autre
        adam5081.py       analogique
        adam5050.py       tout ou rien 16 voies
        layouts.py        possible_layouts(), outil de diagnostic commun
```

## Le descripteur de famille

| Champ | Rôle |
|---|---|
| `nom` | « adam5000 », « autonome » — la clé du registre |
| `a_slot` | occupe un emplacement de fond de panier, ou module autonome |
| `slots` | nombre d'emplacements (4 pour l'ADAM-5000), `None` sinon |
| `commande_lecture(module, adresse, slot)` | construit la requête, sans habillage |
| `commande_checksum(adresse)` | la trame `%` d'activation, propre à la famille |
| `sondes(adresse)` | commandes générales pour le diagnostic (`$aaM`, `$aaF`, `$aa2`) |

`commande_lecture` consulte `module.nature` pour choisir entre la forme
analogique (`#`, accusé `>`) et la forme tout ou rien (`$…6`, accusé `!`) : c'est
la famille qui connaît les deux formes, le modèle qui dit laquelle le concerne.

## Le descripteur de modèle

| Champ | Rôle |
|---|---|
| `reference` | « 5050 », « 5081 » — la clé du registre |
| `libelle` | « ADAM-5050 » pour l'affichage |
| `famille` | le descripteur de famille, pas son nom |
| `nature` | `ANALOGIQUE` ou `TOUT_OU_RIEN` — choisit l'affichage et la requête |
| `voies` | nombre de voies nominal (16 pour le 5050, 4 pour le 5081) |
| `largeur` | largeur d'un champ, pour l'analogique (10) |
| `accuse` | `>` ou `!` — attendu par `verify_frame` |
| `conversion` | `None`, ou une fonction valeur brute → grandeur physique |
| `decode(charge, adresse)` | rend la liste des valeurs de voies |

## Le travail

- [ ] Créer `familles/` avec `base.py`, `adam5000.py`, `autonome.py` et son
      registre, en y déplaçant `read_command`, `digital_read_command` et
      `ENABLE_CHECKSUM` sortis de `protocol.py` à l'étape 3.
- [ ] `autonome.py` est écrite maintenant mais n'est référencée par aucun
      modèle : c'est la place que prendra un 7070. Elle doit être couverte par un
      test de construction de commande, sinon elle pourrira sans qu'on le voie.
- [ ] Créer le paquet `modules/` avec les cinq fichiers ci-dessus, en déplaçant
      le décodage existant sans le modifier — sauf la règle de déduction
      ci-dessous.
- [ ] Écrire `modules/base.py` : le descripteur `ModuleType` et rien d'autre, y
      compris le champ `conversion=None` (décision 9), appliqué par `decode()`
      s'il est défini.
- [ ] `modules/__init__.py` expose `REGISTRE`, `references()` et
      `trouver(reference)` qui accepte `5050`, `"5050"` et `"ADAM-5050"` (la
      normalisation qui vit aujourd'hui dans `settings.read_module`).
- [ ] `SUPPORTED_MODULES` disparaît : la liste **est** le registre.
- [ ] `IO_CHANNELS`, `EXPECTED_CHANNELS`, `EXPECTED_WIDTH` deviennent des champs
      du descripteur concerné, plus des constantes globales.
- [ ] **Découpage déduit (décision 8)** : le décodage du 5081 déclare
      `voies=4, largeur=10` comme nominal, puis applique la règle — si
      `len(charge) % largeur == 0`, alors `voies = len(charge) // largeur` ;
      sinon on lève une erreur qui cite la longueur observée. La largeur de champ
      est la donnée fiable, le nombre de voies est ce qui varie.
- [ ] `IO_SLOTS = 4` n'est plus une constante de `modules` : c'est le champ
      `slots` de la famille `adam5000`, consulté par `settings` et `diagnostic`.
- [ ] `parse_5050` doit utiliser son paramètre de nombre de voies au lieu de
      `IO_CHANNELS` en dur.

La case **Fin d'étape** est dans [TODO.md](../TODO.md), avec les autres.
