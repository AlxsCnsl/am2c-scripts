# ADAM-5000

Lecture des modules d'E/S ADAM-5000 sur liaison série, en Python 3, sans
dépendance externe (bibliothèque standard uniquement). Deux modules sont
gérés : l'ADAM-5081 (voies analogiques) et l'ADAM-5050 (16 entrées/sorties
tout ou rien).

## Structure

```
lancer_adam.sh            lanceur interactif (action, port, droits, cadence)
lancer_diagnostic.sh      lanceur du balayage, quand le module reste muet
choisir_port.sh           choix du port et des droits, inclus par les deux
dcon/                     paquet Python
├── serial_port.py        transport : termios, 8N1, vitesse, lecture de trame
├── protocol.py           trames ASCII Advantech : checksum, requête, accusé
├── modules.py            décodage par module d'E/S (ADAM-5081, ADAM-5050)
├── monitor.py            boucle de lecture, tentatives, statistiques
├── configuration.py      commandes ponctuelles : activation du checksum
├── diagnostic.py         balayage vitesse / checksum / adresse, en lecture seule
├── cli.py                arguments et mise en forme de l'affichage
└── __main__.py           python3 -m dcon
```

Les quatre couches sont indépendantes : ajouter le support d'un autre module
(5017, 5018…) ne touche que `modules.py`, changer la sortie (CSV, journal)
ne touche que `cli.py`.

## Lancement

Depuis ce dossier (`serie/`) :

```sh
sh lancer_adam.sh                                     # interactif
python3 -m dcon --port /dev/ttyUSB0 --interval 2  # direct
```

Options : `--port`, `--baud`, `--interval`, `--retries`, `--retry-delay`,
`--timeout`, `--address`, `--slot`, `--5050`, `--no-checksum`,
`--enable-checksum`, `--config-command`, `--scan`, `--scan-addresses`,
`--raw`.

Les cinq couches sont indépendantes : `diagnostic.py` et `monitor.py` sont
deux usages de la même pile, et n'affichent rien ni l'un ni l'autre.

## Quand rien ne répond

Un module qui ne renvoie **aucune** trame ne discute pas des mêmes conditions
que le programme : vitesse, état du checksum ou adresse. Rien dans le silence
ne dit lequel des trois est en cause — d'où le balayage :

```sh
sh lancer_diagnostic.sh                        # interactif
python3 -m dcon --port /dev/ttyUSB0 --scan # direct
```

Il essaie chaque vitesse avec et sans checksum, interroge le nom du module,
la version, la lecture analogique et les quatre slots, puis rend la commande
à relancer avec les réglages trouvés. Il est en lecture seule : il n'envoie
aucune commande de configuration (`%`) et ne modifie donc pas le module.
Ajouter `--scan-addresses` le fait continuer par les 256 adresses possibles.

Une réponse `?01` n'est pas un échec : le module a compris et refusé. Un slot
qui refuse alors qu'un autre répond dit simplement où est le 5050.

Si le balayage reste muet de bout en bout, la cause n'est plus dans les
réglages mais dans le câblage : RS-232 contre RS-485, RX et TX croisés, masse
commune, alimentation du châssis, et selon le modèle INIT* relié à GND.

Pour une seule requête et sa trame brute, `--raw` suffit :

```sh
python3 -m dcon --port /dev/ttyUSB0 --baud 9600 --5050 --raw --no-checksum
```

## Module ADAM-5050 : 16 entrées/sorties

```sh
python3 -m dcon --port /dev/ttyUSB0 --5050 --slot 0 --interval 1
```

La vue est redessinée à chaque cycle : une voie à 1 s'affiche en vert, une
voie à 0 en rouge. Redirigée dans un fichier, elle reste lisible : les
couleurs ne sortent que sur un terminal.

La lecture emploie `$<adresse>S<slot>6`, à laquelle le module répond `!` suivi
d'un mot de quatre chiffres hexadécimaux — un bit par voie, la voie 00 étant
le bit de poids faible. La grammaire diffère donc de la lecture analogique
(`#<adresse>S<slot>`, accusée par `>`), d'où la commande dédiée dans
`protocol.py` et le paramètre `ack` de `verify_frame()`.

Aucune sortie n'est jamais commandée : le programme ne fait que lire leur
image, ce qui écarte toute activation accidentelle. `--slot` désigne
l'emplacement du module sur le fond de panier (0 à 3), et `--address`
l'adresse de la station.

## Checksum

Le checksum est optionnel côté ADAM, et les deux extrémités doivent être
d'accord : une requête envoyée avec checksum reste sans réponse si le module
n'en attend pas, et l'inverse fait échouer le décodage. Le lanceur pose donc
la question, et `--no-checksum` la reporte en ligne de commande :

```sh
python3 -m dcon --port /dev/ttyUSB0 --no-checksum   # module sans checksum
```

Pour l'activer sur un module qui en est dépourvu (choix 3 du lanceur) :

```sh
python3 -m dcon --port /dev/ttyUSB0 --enable-checksum
```

La trame envoyée est `%01000840` — adresse 01, 38400 bauds, bit checksum à 1 —
et elle part sans checksum, puisqu'elle s'adresse à un module qui n'en attend
pas encore. Le module répond `!01` s'il accepte, `?01` s'il refuse.
`--config-command` permet de fournir une autre trame si l'adresse ou la vitesse
diffèrent. Selon le modèle, INIT* peut devoir être relié à GND.

L'option `-m` est obligatoire : `python3 dcon/` et
`python3 dcon/__main__.py` échouent sur `attempted relative import with no
known parent package`, car Python charge alors `__main__.py` sans package
parent. Seul `-m dcon` définit le paquet.

L'accès au port série demande d'appartenir au groupe `dialout` ; le lanceur
propose de le configurer.
