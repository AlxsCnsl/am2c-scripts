# TODO — rendre le paquet ouvert à d'autres modules

Objectif de ce chantier : **pouvoir accueillir d'autres modèles de modules**
(ICPcon 7070, ADAM-4000…) sans les ajouter maintenant. Rien de nouveau n'est
supporté à la fin ; ce qui change, c'est que l'ajout d'un modèle devient un geste
local au lieu d'une modification de six fichiers.

**Toutes les décisions sont prises** (voir plus bas). Le plan se déroule sans
nouvel arbitrage : les seules cases qui attendent une main humaine sont marquées
**(toi)** et ne bloquent aucune autre étape.

---

## Où on en est

| Étape | État | Fait |
|---|---|---|
| 1 — Poser le filet de tests | à faire | 0/6 |
| 2 — Renommage `dcon` / `serie/` | à faire | 0/6 |
| 3 — Rendre `protocol.py` générique | à faire | 0/4 |
| 4 — Familles et registre de modules | à faire | 0/11 |
| 5 — Un seul `Monitor` | à faire | 0/7 |
| 6 — Découper `cli.py` | à faire | 0/9 |
| 7 — `config.json` : décrire et s'en servir | à faire | 0/9 |
| 8 — Diagnostic ouvert aux autres familles | à faire | 0/4 |
| 9 — Corrections en attente | à faire | 0/10 |
| 10 — Scripts shell | à faire | 0/5 |
| 11 — Validation et documentation | à faire | 0/8 |

Les cases font foi, le tableau les compte. Une étape n'est `faite` que lorsque sa
case **Fin d'étape** est cochée — constatée, pas déduite.

---

## Décisions prises

Cette liste est close. Elle ne se rouvre pas en cours de chantier ; si le
matériel contredit un de ces choix, on corrige le code **et** on récrit la ligne
ici en disant ce qui a été observé.

1. **Registre déclaratif complet** : un descripteur par modèle, un `Monitor`
   unique.
2. **Niveau `familles/`** dès maintenant : la grammaire de lecture appartient à
   la famille (rack ADAM-5000 à slots, ou module DCON autonome), le décodage
   appartient au modèle. Deux registres, chacun avec un métier net.
3. **Le paquet s'appelle `dcon`** — le nom du protocole, vrai pour Advantech
   comme pour ICPcon. `python3 -m dcon`. Plus de renommage après celui-là.
4. **Le dossier `ADAM/` devient `serie/`** : il contient le paquet, les lanceurs
   et `config.json`. Le lanceur racine garde son nom `./lancer-adam.sh`.
5. **`--module` remplace `--5050`**, qui est **supprimé** (pas d'alias).
6. **`--list-modules`** est l'option qui écrit une référence par ligne (drapeaux
   en anglais comme `--scan-addresses`, messages en français).
7. **`ADAM_DEBUG` devient `DCON_DEBUG`** (étape 9, point 4).
8. **Découpage analogique déduit de la longueur reçue.** Le descripteur du 5081
   déclare `voies=4, largeur=10` comme nominal. `decode()` applique la règle :
   si `len(charge) % largeur == 0`, alors `voies = len(charge) // largeur` ;
   sinon on lève avec la longueur observée. La largeur de champ est la donnée
   fiable, le nombre de voies est ce qui varie. `EXPECTED_CHANNELS = 8` disparaît
   comme constante globale.
9. **Champ `conversion` optionnel dans `ModuleType`**, `None` par défaut,
   appliqué par `decode()` s'il existe. Aucun module actuel n'en définit ; le
   jour où un 7070 renvoie des grandeurs physiques, c'est une ligne dans son
   fichier, pas une modification de `monitor.py` ni de l'affichage.
10. **Le reliquat après `\r` est jeté, et c'est voulu** : la liaison est en
    question/réponse stricte, ce qui suit le terminateur d'une réponse est un
    résidu ou du bruit. Comportement inchangé, commenté et figé par un test.
11. **Suite de tests `unittest`** de la bibliothèque standard, sur les couches
    pures.
12. **`config.json`** : format étendu **et** lecture réellement branchée.

---

## Invariants à ne pas casser

À relire avant chaque étape. Ce sont des choix, pas des oublis. Cette liste ne se
coche pas : un invariant ne se termine jamais, il tient ou il est cassé.

1. **Aucune commande d'écriture vers un module tout ou rien.** Seule l'image des
   états est lue. Ni le registre ni les familles ne doivent ouvrir de porte à une
   commande de sortie, même « pour plus tard ».
2. **`diagnostic.py` reste en lecture seule** : jamais de trame `%`.
3. **Pas de `flush_input()` dans la boucle de mesure**
   ([monitor.py:78](ADAM/adam5000/monitor.py#L78)) — une trame en cours d'arrivée
   est une réponse, pas un résidu.
4. **Aucun affichage dans les couches basses.** `protocol`, `familles`,
   `modules`, `monitor`, `settings`, `diagnostic` ne font pas de `print()`.
5. **`HUPCL` effacé et `tcdrain()` après écriture**
   ([serial_port.py:64](ADAM/adam5000/serial_port.py#L64)) — nécessaires aux
   convertisseurs USB et au semi-duplex RS-485.
6. **Aucune dépendance externe.** Pas de `pyserial`, pas de paquet tiers, y
   compris pour les tests.
7. **`--scan` passe avant tout dans le dispatch** : c'est le recours quand plus
   rien ne répond.
8. **Le port série n'entre pas dans `config.json`** : il dépend du PC, pas du
   rack.
9. **Français** partout : code, commentaires, messages, documentation. Les
   drapeaux de ligne de commande restent en anglais, comme les existants.

Les liens de cette page pointent vers `ADAM/adam5000/` tant que l'étape 2 n'est
pas faite ; ils deviennent `serie/dcon/` ensuite.

---

## Étape 1 — Poser le filet de tests

**Avant toute modification.** Sans matériel branché en permanence, c'est le seul
moyen de refactorer sans casser un décodage en silence.

- [ ] Créer `ADAM/tests/`, lancé par `python3 -m unittest discover tests` depuis
      `ADAM/` (même contrainte de répertoire que le paquet). Le dossier suit le
      renommage à l'étape 2.
- [ ] `test_protocol.py` : `checksum_ascii` sur des trames connues, `build_frame`
      avec et sans checksum, `verify_frame` (checksum juste/fausse, réponse trop
      courte, accusé `>` contre `!`, refus `?`).
- [ ] `test_modules.py` : `parse_5081` (longueur exacte, longueur fausse, non
      numérique), `parse_5050` (bit 0 = voie 0, mot `0000`, `FFFF`, minuscules,
      adresse réémise ou non), `possible_layouts`.
- [ ] `test_settings.py` : document valide, clé inconnue, clé manquante, slot en
      double, slot hors bornes, `true` refusé comme slot, vitesse inconnue,
      module inconnu, adresse invalide.
- [ ] Figer les comportements **actuels**, y compris ceux qui seront corrigés à
      l'étape 9 : le test change alors en même temps que le code, et on voit ce
      qui bouge.

- [ ] **Fin d'étape :** la suite passe en vert sur le code inchangé.

---

## Étape 2 — Renommage `adam5000` → `dcon`, `ADAM/` → `serie/`

Fait maintenant, tant que le dépôt est petit, pour que tout le travail des étapes
suivantes s'écrive directement sous le nom définitif.

- [ ] `git mv ADAM serie` puis `git mv serie/adam5000 serie/dcon`. Les imports
      internes sont relatifs : rien à corriger dedans, sauf `__init__.py` et
      `__main__.py` s'ils nomment le paquet.
- [ ] Lanceurs : `serie/lancer_adam.sh`, `serie/lancer_diagnostic.sh`,
      `serie/choisir_port.sh` et `./lancer-adam.sh` à la racine (qui garde son
      nom et ne change que de chemin).
- [ ] Textes : `CLAUDE.md`, `serie/README.md`, tout `docs/` — y compris la
      consigne « lancer avec `-m` depuis le dossier du paquet ».
- [ ] Ajouter en tête de `serie/dcon/__init__.py` une phrase qui dit ce que le
      nom recouvre : protocole ASCII DCON, familles Advantech ADAM et ICPcon.
- [ ] Vérifier qu'il ne reste aucune occurrence du vieux nom de paquet ni du
      vieux chemin : `grep -rn 'adam5000\|ADAM/' . --exclude-dir=.git`. Les
      mentions de « ADAM-5000 » ou « ADAM-5050 » comme références matérielles
      sont légitimes et restent.

- [ ] **Fin d'étape :** `python3 -m dcon --help` répond depuis `serie/`, la suite
      de tests de l'étape 1 passe toujours, et `./lancer-adam.sh` démarre.

---

## Étape 3 — Rendre `protocol.py` réellement générique

Aujourd'hui `protocol.py` prétend être « indépendant du module d'E/S » mais
contient `#<addr>S<slot>` et `$<addr>S<slot>6`, qui sont la grammaire du fond de
panier ADAM-5000. Un ADAM-4000 ou un I-7000 lit par `#<addr>`, sans slot.

- [ ] Garder dans `protocol.py` uniquement ce qui est vrai pour toute la famille
      ASCII Advantech/DCON : `TERMINATOR`, `ACK`, `CONFIG_ACK`, `checksum_ascii`,
      `build_frame`, `verify_frame`, `DEFAULT_ADDRESS`.
- [ ] Déplacer `read_command`, `digital_read_command` et `ENABLE_CHECKSUM` vers
      les familles (étape 4).
- [ ] Mettre à jour l'en-tête du fichier : il documente une grammaire
      d'enveloppe, pas un jeu de commandes.

- [ ] **Fin d'étape :** aucune mention de « slot » ni de référence de module dans
      `protocol.py` ; la suite de tests passe toujours.

---

## Étape 4 — Familles de protocole et registre de modules

Le cœur du chantier. Deux registres : la famille porte la grammaire de lecture et
la notion de slot, le modèle porte son décodage.

→ Détail : [TODO/part3.md](TODO/part3.md)

- [ ] **Fin d'étape :** ajouter un modèle = écrire un fichier dans `modules/` et
      l'inscrire au registre. Rien d'autre. Les tests de l'étape 1 tournent
      contre le registre.

---

## Étape 5 — Un seul `Monitor`

`Monitor5050` existe uniquement parce que `request()` et `decode()` étaient
codés en dur. Avec le registre, cette raison disparaît.

- [ ] `Monitor.__init__` prend un `ModuleType` au lieu de `channels`/`width`.
- [ ] `request()` : `protocol.build_frame(module.famille.commande_lecture(module,
      adresse, slot), checksum)`.
- [ ] `decode()` : `module.decode(protocol.verify_frame(reponse, checksum,
      module.accuse), adresse)`.
- [ ] Supprimer `Monitor5050` (et avec elle le `channels=` codé en dur signalé au
      point 7 de `docs/10-relecture.md`).
- [ ] La garde « slot dans le fond de panier » se déclenche selon
      `module.famille.a_slot` : un module autonome n'a pas de slot à valider.
- [ ] `Measurement` et `Failure` ne changent pas. Ajouter le descripteur au
      `Measurement` seulement si l'affichage en a besoin — sinon l'appelant l'a
      déjà.

- [ ] **Fin d'étape :** `monitor.py` ne contient plus aucune référence à un
      modèle ni à une famille précise.

---

## Étape 6 — Découper `cli.py`

386 lignes, 45 % du paquet, trois métiers mêlés. Chaque nouveau modèle
l'alourdirait.

```
serie/dcon/cli/
    __init__.py     main() : dispatch seul
    arguments.py    parse_args()
    affichage.py    formats de mesure, en-têtes, vue tout ou rien
    scan.py         mise en forme du diagnostic
```

- [ ] Créer le paquet `cli/` ci-dessus, un métier par fichier.
- [ ] **`--module` remplace `--5050`**, avec `choices=references()` alimenté par
      le registre. `--5050` est supprimé : mettre à jour `lancer_adam.sh`
      (étape 10), `serie/README.md`, `CLAUDE.md` et `docs/` dans la même étape.
- [ ] Ajouter `--list-modules` : une référence par ligne sur la sortie standard,
      rien d'autre — c'est ce que le menu shell consommera (étape 10).
- [ ] Un seul chemin de boucle de mesure : `monitor_loop(args)` choisit
      l'affichage selon `module.nature` — `display_io16` devient
      `vue_tout_ou_rien(mesure, monitor)`, dimensionnée par `module.voies` au
      lieu de 16 en dur.
- [ ] `show_raw()` s'appuie sur le descripteur et sa famille pour la commande et
      l'accusé, au lieu de son `if args.io_5050`.
- [ ] `suggest_command()` propose `--module <ref>` ; le slot n'est proposé que si
      la famille du modèle en a un.
- [ ] Renommer `cli.enable_checksum()` (point 7 de `docs/10-relecture.md`)
      pendant qu'on y est : `afficher_activation_checksum()`.
- [ ] Vérifier que l'ordre de dispatch de `main()` est conservé tel quel :
      `--scan`, puis `--config`, puis `--enable-checksum`, `--raw`, boucle.
      `--list-modules` se place avant tout le reste : il n'ouvre pas le port.

- [ ] **Fin d'étape :** aucun fichier de `cli/` ne dépasse ~150 lignes ; aucune
      référence de modèle en dur hors du registre.

---

## Étape 7 — `config.json` : décrire une installation, et s'en servir

Deux manques : le format ne sait décrire qu'un rack à slots, et `--config`
affiche puis quitte ([cli.py:284](ADAM/adam5000/cli.py#L284)).

→ Détail : [TODO/part6.md](TODO/part6.md)

- [ ] **Fin d'étape :** un rack hétérogène se lit avec une seule commande, sans
      réénumérer les arguments.

---

## Étape 8 — Diagnostic ouvert aux autres familles

`probes()` balaie les slots du fond de panier : face à un module autonome, il
cherche au mauvais endroit.

- [ ] Construire la liste des sondes depuis les deux registres : commandes
      générales de chaque famille (`$aaM`, `$aaF`, `$aa2`) puis, pour chaque
      modèle connu, sa commande de lecture — avec balayage des slots seulement si
      `famille.a_slot`.
- [ ] `Attempt` gagne la référence du modèle sondé, pour que `suggest_command()`
      propose directement `--module <ref>`.
- [ ] Conserver strictement la lecture seule : aucune commande `%`.

- [ ] **Fin d'étape :** ajouter un modèle au registre enrichit automatiquement le
      balayage.

---

## Étape 9 — Corrections en attente

Reprises de `docs/10-relecture.md`, à traiter avec un test chacune (étape 1).

- [ ] `parse_5050` mange le mot d'état quand il commence comme l'adresse
      ([modules.py:59](ADAM/adam5000/modules.py#L59)) — ne retirer l'adresse que
      s'il reste assez de caractères. **Bogue reproductible, à faire en premier.**
- [ ] `SerialPort.__init__` laisse passer une vitesse inconnue jusqu'à `termios`
      ([serial_port.py:44](ADAM/adam5000/serial_port.py#L44)) — inverser le test.
- [ ] `--scan-addresses` ne propose pas de commande à relancer
      ([cli.py:128-137](ADAM/adam5000/cli.py#L128-L137)).
- [ ] `except Exception` masque la trace : ajouter la sortie par `DCON_DEBUG`
      (décision 7), et un `except KeyboardInterrupt` dans `main()` (code de
      retour 130) qui couvre toutes les branches.
- [ ] `__init__.py` : refléter les deux registres, retirer `BAUD` (code termios
      mort, à ne pas confondre avec `DEFAULT_BAUD`).
- [ ] `show_raw()` : vider le tampon d'entrée après ouverture, comme
      `diagnostic.attempt()`.
- [ ] Commenter le non-remise à zéro de `rejected_since_ok` sur un `Failure`
      ([monitor.py:108](ADAM/adam5000/monitor.py#L108)) : c'est voulu, ça ne se
      voit pas.
- [ ] **Reliquat après `\r` (décision 10)** : le comportement ne change pas.
      Écrire dans `read_frame()` pourquoi on le jette — liaison en
      question/réponse stricte — et ajouter le test qui fige ce choix.
- [ ] **Découpage analogique (décision 8)** : appliquer la règle de déduction
      dans le décodage du 5081, supprimer `EXPECTED_CHANNELS`, et couvrir par des
      tests les trois cas — longueur nominale (40), longueur multiple (80), et
      longueur qui ne divise pas (erreur citant la longueur observée).

- [ ] **Fin d'étape :** chaque point ci-dessus est corrigé et couvert par un test,
      ou explicitement documenté comme un choix.

---

## Étape 10 — Scripts shell

- [ ] `lancer_adam.sh` : le menu ne peut plus lister les modules en dur. Le
      peupler depuis `python3 -m dcon --list-modules` — ainsi un modèle ajouté au
      registre apparaît au menu sans toucher au shell.
- [ ] Remplacer `--5050 --slot N` par `--module <ref> [--slot N]`, et ne demander
      le slot que si la famille du module en a un.
- [ ] `lancer_diagnostic.sh` : rien à changer, sauf si l'option de balayage
      change de nom.
- [ ] Ajouter une entrée « lire tout le rack depuis `config.json` » une fois
      l'étape 7 faite.

- [ ] **Fin d'étape :** un modèle ajouté au registre apparaît au menu sans qu'une
      ligne de shell soit touchée.

---

## Étape 11 — Validation et documentation

- [ ] Faire tourner la suite de tests complète.
- [ ] Vérifier qu'aucune trame `%` n'est émise hors de `--enable-checksum` :
      `grep -rn '"%' serie/dcon/`.
- [ ] Invoquer l'agent `documenter` (obligatoire après toute modification du
      dépôt, cf. `CLAUDE.md`). `docs/02-architecture.md`, `05-modules.md`,
      `06-monitor.md`, `09-cli.md` et `12-settings.md` sont à revoir en
      profondeur ; `10-relecture.md` perd les points traités à l'étape 9 ; le
      renommage et le niveau `familles/` touchent toute la série.
- [ ] **(toi)** `--raw` sur le 5081 : confirmer ou infirmer la règle de déduction
      (décision 8) et récrire cette ligne avec la longueur réellement observée.
- [ ] **(toi)** Lecture continue du 5050 sur son slot.
- [ ] **(toi)** `--scan` sur un port muet.
- [ ] **(toi)** Lecture complète du rack depuis `config.json`.

- [ ] **Fin d'étape :** le matériel répond comme avant le chantier, et `docs/`
      décrit le paquet tel qu'il est devenu.

Le port `/dev/ttyUSB0` n'est pas accessible depuis la session : les cases
**(toi)** attendent une main humaine, elles ne sont pas en retard — et **aucune
étape ne les attend** pour avancer.

---

## Après la refonte : ajouter un module

Le résultat attendu de tout ce chantier, en trois gestes :

1. écrire `modules/<reference>.py` : un descripteur `ModuleType` qui désigne sa
   famille, et sa fonction de décodage ;
2. l'inscrire au registre dans `modules/__init__.py` ;
3. ajouter ses cas dans `tests/test_modules.py`.

Ni `protocol.py`, ni `familles/` (si la famille existe déjà), ni `monitor.py`, ni
`cli/`, ni `settings.py`, ni les scripts shell ne doivent être touchés.
