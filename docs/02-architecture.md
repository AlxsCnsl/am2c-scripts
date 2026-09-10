# 2. Architecture : les couches et le trajet d'une mesure

## Le principe

Le paquet est construit **en couches**, chacune ignorante de celles du dessus.
C'est l'invariant de conception à préserver : une couche ne connaît que celle
qui est juste en dessous d'elle.

```
        ┌──────────────────────────────────────────────┐
   5    │  cli.py          arguments + affichage       │  le seul à faire print()
        └───────────────┬──────────────────────────────┘
                        │
        ┌───────────────┴──────┬───────────────┬─────────────────┐
   4    │  monitor.py          │ configuration │  diagnostic.py  │  aucun print()
        │  boucle + réessais   │ .py  one-shot │  balayage       │
        └───────────────┬──────┴───────┬───────┴────────┬────────┘
                        │              │                │
        ┌───────────────┴──────────────┴────────────────┴────────┐
   3/2  │  modules.py  décodage       protocol.py  grammaire     │  aucune E/S
        └───────────────────────┬────────────────────────────────┘
                                │
        ┌───────────────────────┴────────────────────────────────┐
   1    │  serial_port.py     octets bruts, termios, select      │
        └────────────────────────────────────────────────────────┘
                                │
                          /dev/ttyUSB0
```

## Les règles qui découlent de ce découpage

Retiens ces quatre règles, elles expliquent 90 % des choix du code :

1. **`serial_port.py` ne sait pas ce qu'est une trame ADAM.** Il transporte des
   octets et s'arrête au `\r`. Rien de plus.
2. **`protocol.py` ne sait pas quel module est branché.** Il sait fabriquer et
   vérifier une trame, pas ce que contient la charge utile.
3. **`modules.py` ne sait pas d'où viennent les données.** Ce sont des fonctions
   pures : une chaîne entre, une liste de nombres sort. Aucune E/S, donc
   testables sans matériel.
4. **La couche 4 n'affiche rien.** `monitor.run()` *produit* des résultats
   (`yield`), `diagnostic.sweep()` aussi. C'est `cli.py` qui décide comment les
   montrer. Tu peux donc écrire un export CSV en ne touchant qu'à `cli.py`.

### Ce que ça veut dire quand tu modifies le code

| Tu veux… | Tu touches à… |
|---|---|
| Ajouter le support d'un ADAM-5017 | `modules.py` (+ `protocol.py` si sa grammaire diffère) |
| Écrire les mesures dans un CSV | `cli.py` seulement |
| Gérer une nouvelle vitesse | `serial_port.py` (table `BAUDRATES`) |
| Changer la stratégie de réessai | `monitor.py` seulement |
| Ajouter une interrogation au diagnostic | `diagnostic.probes()` |

### Un fichier à part : `settings.py`

`settings.py` ([12-settings.md](12-settings.md)) ne figure pas dans le schéma
ci-dessus : il ne lit pas le port série, seulement un fichier JSON qui décrit
le rack (quel module dans quel slot, à quelle vitesse). Il importe des
constantes de `modules.py`, `protocol.py` et `serial_port.py` pour valider
contre les mêmes limites que le reste du paquet, mais aucune de leurs
fonctions — il reste donc en dehors des quatre couches de lecture. Seul
`cli.py` s'en sert, via `--config`.

## Le trajet complet d'une mesure

Prenons `python3 -m dcon --port /dev/ttyUSB0 --5050 --no-checksum`.

```
__main__.py
  └─ cli.main()
       └─ cli.parse_args()              → objet args
       └─ cli.monitor_5050_loop(args)
            └─ Monitor5050(...)         couche 4
                 └─ .open()             → SerialPort(...).open()      couche 1
                 └─ .run()  boucle infinie :
                      └─ .cycle()       jusqu'à 5 tentatives
                           └─ .read_once()
                                ├─ .request()
                                │    └─ familles.digital_read_command()  → "$01S06"
                                │    └─ protocol.build_frame()           → "$01S06\r"
                                ├─ serial.write("$01S06\r")     couche 1 → le câble
                                ├─ serial.read_frame(2.0)       couche 1 ← le câble
                                │                                 → "!01FF00"
                                └─ .decode("!01FF00")
                                     ├─ protocol.verify_frame(..., ack="!") → "01FF00"
                                     └─ modules.parse_5050("01FF00")
                                          → [0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1]
                           └─ retourne Measurement(horodatage, valeurs, rejetées)
                      └─ time.sleep(interval)
            └─ cli.display_io16(mesure, monitor)   couche 5 : l'écran
```

Chaque flèche descendante est un appel, chaque flèche remontante un retour. Le
seul endroit où le programme parle à l'extérieur (le câble) est la couche 1 ;
le seul endroit où il parle à l'utilisateur est la couche 5.

## Les six points d'entrée de `main()`

`cli.main()` choisit une seule branche, **et l'ordre compte** :

```python
if args.scan:                 run_scan(args)            # 1. balayage, lecture seule
elif args.config is not None: show_settings(args)       # 2. lecture du fichier de réglages
elif args.enable_checksum:    enable_checksum(args)     # 3. configuration
elif args.raw:                show_raw(args)            # 4. une lecture brute
elif args.io_5050:            monitor_5050_loop(args)   # 5. boucle 16 E/S
else:                         monitor_loop(args)        # 6. boucle analogique
```

`--scan` passe en premier volontairement : c'est le recours quand plus rien ne
répond, et il ne doit jamais être masqué par une autre option qu'on aurait
laissée traîner sur la ligne de commande. `--config` vient juste après : comme
le balayage, il ne touche ni au port série ni au module — il ne fait que lire
et afficher un fichier — et doit donc pouvoir être vérifié avant tout échange.

## Le vocabulaire des objets de résultat

Trois `namedtuple` circulent entre les couches 4 et 5. Un `namedtuple` est un
tuple dont les champs ont un nom : immuable, léger, et lisible.

| Objet | Défini dans | Champs | Signification |
|---|---|---|---|
| `Measurement` | `monitor.py` | `timestamp`, `values`, `rejected` | Une lecture réussie |
| `Failure` | `monitor.py` | `attempts`, `rejected_total`, `last_error` | Un cycle entièrement raté |
| `Attempt` | `diagnostic.py` | `baud`, `checksum`, `address`, `slot`, `command`, `label`, `response`, `error` | Un essai du balayage |

`cli.py` distingue les deux premiers par `isinstance(event, Measurement)`.
