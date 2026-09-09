# 1. Environnement : ce qui est installé, ce qui tourne

## Aucune bibliothèque à installer

C'est le point le plus surprenant du dépôt quand on arrive dessus : **il n'y a
rien à installer**. Pas de `requirements.txt`, pas de `pip install`, pas de
`venv`, pas de `setup.py`. Le paquet n'utilise que la bibliothèque standard de
Python 3.

Vérifié sur cette machine :

```
$ python3 --version
Python 3.13.15
$ python3 -c "import serial"
ModuleNotFoundError: No module named 'serial'
```

`pyserial` — la bibliothèque que 90 % des projets série utilisent — **n'est pas
installée et n'est pas utilisée**. Le fichier `serial_port.py` la remplace en
appelant directement le noyau Linux. C'est un choix assumé du dépôt : le
programme doit pouvoir tourner sur une machine industrielle sans accès réseau,
donc sans possibilité d'installer quoi que ce soit.

> Conséquence pratique pour toi : ne remplace jamais `serial_port.py` par
> `import serial` sans en parler. Ce serait ajouter une dépendance externe là
> où le dépôt s'est explicitement construit sans.

## Les modules standard utilisés

Chacun vient de Python lui-même. Voici à quoi ils servent ici :

| Module | Où | À quoi il sert dans ce projet |
|---|---|---|
| `os` | `serial_port.py` | `os.open`, `os.read`, `os.write`, `os.close` : traiter le port série comme un fichier |
| `termios` | `serial_port.py` | Régler le port série (vitesse, 8 bits, pas de parité). C'est l'API POSIX des terminaux |
| `fcntl` + `struct` | `serial_port.py` | Envoyer un `ioctl` au noyau pour lever les lignes DTR et RTS (voir glossaire) |
| `select` | `serial_port.py` | Attendre que des octets arrivent, sans bloquer indéfiniment |
| `time` | partout | `time.monotonic()` pour les délais d'attente, `time.sleep()` pour les pauses |
| `datetime` | `monitor.py` | Horodater chaque mesure |
| `collections.namedtuple` | `monitor.py`, `diagnostic.py` | Petits objets de résultat immuables (`Measurement`, `Failure`, `Attempt`) |
| `argparse` | `cli.py` | Analyser les arguments de la ligne de commande |
| `sys` | `cli.py` | `sys.stdout.isatty()` (est-ce un écran ?) et `sys.stderr` |

Rien d'autre. Pas de `logging`, pas de `threading`, pas de `asyncio` : le
programme est mono-tâche et volontairement simple.

## Comment lancer

### Le lanceur interactif (le plus simple)

```sh
sh ADAM/lancer_adam.sh
```

Il pose trois questions (action, port, vitesse), gère les droits `sudo` si
besoin, puis construit la ligne de commande `python3 -m adam5000 …` à ta place.
Le script `choisir_port.sh` s'occupe du choix du port et des permissions ; il
est *sourcé* (`.`) par les deux lanceurs, donc les variables `$PORT` et
`$USE_SUDO` qu'il définit sont visibles ensuite.

### En direct

```sh
cd ADAM
python3 -m adam5000 --port /dev/ttyUSB0 --baud 9600 --5050
```

### Pourquoi `-m` et pas autre chose

Le dossier `adam5000/` est un **paquet** Python : ses fichiers se référencent
entre eux avec des imports relatifs (`from . import protocol`). Le point
signifie « le paquet auquel j'appartiens ».

- `python3 -m adam5000` → Python charge d'abord le paquet `adam5000`, puis
  exécute son `__main__.py`. Le paquet existe, les imports relatifs marchent.
- `python3 adam5000/__main__.py` → Python exécute un simple script isolé. Il
  n'y a plus de paquet parent, donc `from .cli import main` échoue avec
  `attempted relative import with no known parent package`.

Et il faut être dans `ADAM/` (le dossier *parent* de `adam5000/`) pour que
Python trouve le paquet dans le répertoire courant. C'est pourquoi les deux
lanceurs shell font `cd "$SCRIPT_DIR"` avant d'appeler `python3`.

## Les droits sur le port série

Ouvrir `/dev/ttyUSB0` demande d'appartenir au groupe `dialout` (ou d'être
root). Sans cela, `os.open()` lève `PermissionError` et le programme affiche
`Erreur : [Errno 13] Permission denied`.

Deux solutions, dans cet ordre de préférence :

```sh
sudo usermod -aG dialout $USER   # définitif ; nécessite de se reconnecter
sudo python3 -m adam5000 …       # ponctuel ; ce que propose choisir_port.sh
```

## Les options de la ligne de commande

Toutes définies dans `parse_args()` de [`cli.py`](../ADAM/adam5000/cli.py) —
détaillées dans [09-cli.md](09-cli.md).

| Option | Défaut | Rôle |
|---|---|---|
| `--port` | `/dev/ttyS0` | Fichier de périphérique du port série |
| `--baud` | `38400` | Vitesse de la liaison (choix imposé parmi 1200…115200) |
| `--interval` | `2.0` | Secondes entre deux cycles de mesure |
| `--retries` | `5` | Tentatives par cycle avant d'abandonner |
| `--retry-delay` | `0.5` | Pause entre deux tentatives |
| `--timeout` | `2.0` | Attente maximale d'une réponse |
| `--address` | `01` | Adresse de station du module |
| `--slot` | `0` | Emplacement du module sur le fond de panier (0 à 3) |
| `--5050` | absent | Lire les 16 voies tout ou rien au lieu des voies analogiques |
| `--no-checksum` | absent | Le module n'utilise pas la somme de contrôle |
| `--enable-checksum` | absent | Activer la somme de contrôle du module, puis quitter |
| `--config-command` | `%01000840` | Trame de configuration envoyée par `--enable-checksum` |
| `--channels` | `8` | Nombre de voies analogiques attendues |
| `--width` | `10` | Largeur d'un champ analogique, en caractères |
| `--scan` | absent | Balayer les réglages possibles, puis quitter (lecture seule) |
| `--scan-addresses` | absent | Avec `--scan`, essayer aussi les 256 adresses |
| `--config` | absent (`config.json` si présent sans valeur) | Lire, valider et afficher un fichier de réglages des slots, puis quitter |
| `--raw` | absent | Une seule lecture, trame brute affichée, puis quitter |

## Pas de tests, pas de linter

Il n'y a ni suite de tests, ni `pytest`, ni `ruff`/`flake8`, ni formateur
configuré. Le code se vérifie donc à la main, contre du matériel réel — d'où
l'importance de `--raw` et `--scan`, qui sont les seuls « outils de test » du
dépôt.
