# 9. `cli.py` — arguments et affichage

Fichier : [ADAM/adam5000/cli.py](../ADAM/adam5000/cli.py) — 386 lignes, le plus
gros du paquet.

**Rôle :** lire la ligne de commande, choisir quoi faire, et **mettre en forme**.
C'est le seul fichier du paquet qui a le droit d'appeler `print()`.

Cette concentration est volontaire : tant que tout l'affichage est ici, changer
la sortie (CSV, journal, couleurs) ne touche à aucune logique métier.

## Les constantes de couleur

```python
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
CLEAR_SCREEN = "\033[2J\033[H"
```

Ce sont des **séquences d'échappement ANSI** : `\033` est le caractère Échap, et
le terminal interprète ce qui suit comme une instruction (couleur, effacement,
retour du curseur en haut à gauche pour `\033[H`).

Elles ne sont émises que si `sys.stdout.isatty()` est vrai — c'est-à-dire si la
sortie est un vrai terminal. Redirigée dans un fichier (`… > mesures.txt`), la
vue reste lisible, sans caractères parasites. Le test se trouve dans
`display_io16()` : `screen = sys.stdout.isatty()`.

## Les fonctions de mise en forme

Ces quatre fonctions sont **pures** : elles prennent un objet et rendent une
chaîne, sans rien afficher. Facile à relire, facile à essayer.

### `format_measurement(measurement, checksum=True, width=EXPECTED_WIDTH)`

Une ligne par mesure analogique :

```
2026-09-07 14:32:10 | V0=1234 | V1=5678 | checksum=OK | largeur=10 | rejetées=2
```

Le `| rejetées=N` n'apparaît **que si** `measurement.rejected` est non nul : pas
de bruit visuel quand tout va bien. Rappeler `checksum` et `largeur` sur chaque
ligne peut sembler redondant, mais c'est délibéré : quand on relit un journal
plus tard, on sait sous quelles hypothèses les valeurs ont été décodées.

### `format_failure(failure)`

Le message d'échec d'un cycle : nombre d'essais, rejets cumulés, dernière
erreur. C'est `last_error` qui porte l'information utile
(`TimeoutError('Aucune réponse reçue.')` ou `ValueError('Checksum invalide')`).

### `format_attempt(attempt)`

Une ligne du balayage :

```
  sans checksum | $01S06 (16 E/S, slot 0) -> '!010000'
  avec checksum | $01M (nom du module) -> '?01'   (refus, mais le module entend)
```

`{attempt.response!r}` : le `!r` utilise `repr()`, qui montre les guillemets et
rend visibles les caractères invisibles. Sur une liaison série, c'est
indispensable — sans lui, on ne distingue pas `'!01'` de `'!01 '`.

### `suggest_command(port, trouvailles)`

La fonction la plus utile du fichier pour l'utilisateur : elle reconstruit la
ligne de commande à relancer avec les réglages qui ont marché.

```python
lectures = [a for a in trouvailles if a.slot is not None and diagnostic.accepted(a)]
retenu = lectures[0] if lectures else trouvailles[0]
```

Elle **préfère un essai qui a vraiment lu un slot** plutôt qu'un simple
« nom du module » : le premier prouve qu'on lit des données, le second seulement
qu'on est entendu. À défaut, elle retombe sur la première trouvaille.

Puis elle assemble les options (`--port`, `--baud`, `--address`, et selon le cas
`--no-checksum`, `--5050 --slot N`) pour produire par exemple :

```
python3 -m adam5000 --port /dev/ttyUSB0 --baud 9600 --address 01 --no-checksum --5050 --slot 0
```

## Les fonctions d'affichage

### `run_scan(args)` — `--scan`

Consomme `diagnostic.sweep()` et affiche au fil de l'eau. Sa mécanique :

```python
for attempt in diagnostic.sweep(args.port, address=args.address):
    if attempt.baud != vitesse:            # on change de vitesse
        if vitesse is not None and not repondu:
            print("  rien")                # bilan de la vitesse précédente
        vitesse = attempt.baud
        repondu = False
        print(f"{attempt.baud} bauds")
    if attempt.command is None:
        print(f"  port inutilisable : {attempt.error}")
        return                              # inutile d'insister
    if attempt.response:
        print(format_attempt(attempt))
        trouvailles.append(attempt)
        repondu = True
```

Les variables `vitesse` et `repondu` servent à regrouper l'affichage par
vitesse et à écrire « rien » sous celles qui n'ont rien donné. Le bloc après la
boucle rejoue ce bilan pour la dernière vitesse — un cas classique qu'on oublie
souvent.

À la fin, trois issues :

1. **Des trouvailles** → afficher la commande suggérée. Et si aucun *slot* n'a
   répondu, prévenir : le module parle, mais il n'y a pas de 5050 là où on le
   cherche.
2. **Rien, sans `--scan-addresses`** → proposer d'aller plus loin, ou de
   regarder le câblage.
3. **Rien, avec `--scan-addresses`** → balayer les 256 adresses.

### `display_io16(measurement, monitor)` — la vue des 16 E/S

Redessine tout l'écran à chaque rafraîchissement :

```python
word = sum(state << channel for channel, state in enumerate(measurement.values))
```

Recompose le mot hexadécimal à partir de la liste de bits — l'opération inverse
de `parse_5050()`. `state << channel` remet chaque bit à sa place, la somme les
réunit. Affiché en `0x{word:04X}`, c'est ce qu'on peut comparer directement à la
trame brute.

Puis une grille de 4 lignes × 4 voies :

```python
for first in range(0, IO_CHANNELS, 4):
    cells = []
    for channel in range(first, first + 4):
        state = measurement.values[channel]
        cell = f"E/S {channel:02d} : {state}"
        cells.append((GREEN if state else RED) + cell + RESET if screen else cell)
    print("    ".join(cells))
```

Vert pour 1, rouge pour 0 — mais uniquement si `screen` est vrai.

L'en-tête rappelle port, vitesse, adresse, slot, état de la checksum, mot d'état
et horodatage, plus la phrase « Aucune sortie n'est commandée : les états sont
seulement lus. » — la garantie de sécurité, affichée à l'écran.

### `print_header(monitor)`

L'en-tête de la boucle analogique, affiché une fois au démarrage. Il rappelle
notamment `Décodage strict : N voies x M caractères` : c'est **l'hypothèse** de
découpage, celle qu'il faut confronter à `--raw` si les valeurs semblent
absurdes.

### `show_raw(args)` — `--raw`

L'outil de mise au point à connaître. Une seule lecture, tout affiché :

```
Requête  : '$01S0607\r'
Réponse  : "!010000AB"
Longueur : 9 caractères, terminateur exclu
Charge utile : 6 caractères
```

Puis, selon le mode :

- **`--5050`** : le mot d'état et les 16 états déjà décodés.
- **analogique** : tous les découpages possibles via `possible_layouts()`, avec
  la mention `(mêmes valeurs répétées)` quand un découpage donne partout la même
  valeur — signe presque certain qu'il coupe au mauvais endroit.

C'est la commande à lancer en premier quand les valeurs affichées par la boucle
paraissent fausses : elle ne suppose rien du format.

### `show_settings(args)` — `--config [FICHIER]`

```python
slots = settings.load(args.config)
```

`--config` accepte un argument optionnel (`nargs="?"`) : sans valeur, `args.config`
vaut `settings.DEFAULT_FILE` (`"config.json"`) grâce à `const=`, absent de la
ligne de commande il vaut `None` — ce qui permet à `main()` de distinguer « ne
rien faire » de « lire le fichier par défaut ».

La fonction lit le fichier avec `settings.load()` ([12-settings.md](12-settings.md)),
l'affiche en tableau (une ligne par slot), puis rend la main : **aucun octet
n'est envoyé sur le port série**, et aucun `Monitor` n'est construit à partir
des réglages lus — lire le rack et le surveiller restent deux actions
séparées.

### `enable_checksum(args)` — `--enable-checksum`

Enrobe `configuration.enable_checksum()` : annonce la commande envoyée, explique
qu'elle part sans checksum, affiche la réponse, et rappelle qu'il faut relancer
la lecture **sans** `--no-checksum`.

⚠️ Cette fonction porte **le même nom** que celle de `configuration.py`. Il n'y a
pas de conflit (l'une est `cli.enable_checksum`, l'autre
`configuration.enable_checksum`, appelée avec son préfixe de module), mais c'est
déroutant à la lecture — voir la [relecture](10-relecture.md).

### `monitor_loop(args)` et `monitor_5050_loop(args)`

Même structure toutes les deux :

```python
monitor = Monitor(...)          # ou Monitor5050(...)
try:
    with monitor:
        for event in monitor.run():
            if isinstance(event, Measurement):
                ...affichage...
            else:
                print(format_failure(event))
                if monitor.last_frame:
                    print(f"  dernière trame reçue : {monitor.last_frame!r}")
except KeyboardInterrupt:
    print("Lecture arrêtée.")
    print(f"Nombre total de trames rejetées : {monitor.rejected_total}")
```

- `isinstance(event, Measurement)` distingue succès et échec : c'est le
  générateur qui décide, l'affichage qui suit.
- En cas d'échec, la **trame brute** est montrée si on en a une : c'est
  l'information qui permet de comprendre si le module a répondu n'importe quoi
  ou n'a rien dit du tout.
- Le `Ctrl+C` est rattrapé pour afficher un bilan propre au lieu d'une trace
  d'exception. Le `with` a déjà fermé le port à ce stade.

## `parse_args(argv=None)`

Toutes les options sont déclarées ici, avec `argparse`. Deux détails :

```python
parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, choices=sorted(BAUDRATES), ...)
```

`choices=` fait rejeter une vitesse non gérée **avant** toute tentative
d'ouverture, avec la liste des valeurs acceptées. Bien mieux qu'un échec obscur
au moment de configurer le port.

```python
parser.add_argument("--5050", dest="io_5050", action="store_true", ...)
```

`dest="io_5050"` est **obligatoire** : `args.5050` serait un nom d'attribut
illégal en Python (un identifiant ne peut pas commencer par un chiffre).

`argv=None` en paramètre permet d'appeler `parse_args(["--port", "/dev/x"])`
depuis un futur test, au lieu de dépendre de `sys.argv`.

## `main(argv=None)`

```python
args = parse_args(argv)
try:
    if args.scan:                 run_scan(args)
    elif args.config is not None: show_settings(args)
    elif args.enable_checksum:    enable_checksum(args)
    elif args.raw:                show_raw(args)
    elif args.io_5050:            monitor_5050_loop(args)
    else:                         monitor_loop(args)
except Exception as exc:
    print(f"Erreur : {exc}", file=sys.stderr)
    return 1
return 0
```

Trois choses à retenir :

1. **L'ordre du `if/elif` est un choix, pas un hasard.** `--scan` passe devant
   tout : c'est le recours quand plus rien ne marche, et il ne doit jamais être
   masqué par une autre option restée sur la ligne de commande. `--config`
   vient juste après, pour la même raison : il ne touche ni au port ni au
   module.
2. **Le message d'erreur va sur `sys.stderr`**, pas sur la sortie standard. Ainsi
   `python3 -m adam5000 … > mesures.txt` met les mesures dans le fichier et
   laisse les erreurs à l'écran.
3. **Le code de retour** : `0` = succès, `1` = échec. C'est la convention Unix,
   utilisable dans un script shell (`if python3 -m adam5000 …; then`).
   `__main__.py` le transmet au système avec `raise SystemExit(main())`.

Sur le `except Exception` large, voir la [relecture](10-relecture.md#5-except-exception-masque-la-trace-en-cas-de-bogue).

## Les deux fichiers d'amorçage

### `__main__.py` (3 lignes)

```python
from .cli import main
raise SystemExit(main())
```

Le fichier qu'exécute `python3 -m adam5000`. `raise SystemExit(valeur)` est la
façon idiomatique de sortir avec un code de retour ; c'est équivalent à
`sys.exit()` sans avoir à importer `sys`.

### `__init__.py`

Il fait deux choses :

1. **Marquer le dossier comme un paquet** (même vide, un `__init__.py` suffit).
2. **Définir l'API publique** : réexporter les noms utiles pour qu'on puisse
   écrire `from adam5000 import Monitor` sans connaître le fichier d'origine.
   La liste `__all__` déclare ce qui sort avec `from adam5000 import *`. Elle
   inclut `SlotSettings` et `load_settings` (alias de `settings.load`), pour
   qu'un script puisse lire un fichier de réglages sans importer `settings`
   directement.

⚠️ Cette liste reste incomplète (ni `Monitor5050`, ni `parse_5050`, ni
`diagnostic`) : voir la [relecture](10-relecture.md).
