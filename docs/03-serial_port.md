# 3. `serial_port.py` — la couche transport

Fichier : [ADAM/adam5000/serial_port.py](../ADAM/adam5000/serial_port.py) — 144 lignes.

**Rôle :** ouvrir un port série, le régler, écrire des octets dessus, lire une
trame jusqu'au retour chariot. Il ne sait rien du protocole ADAM.

## L'idée de base : un port série est un fichier

Sous Linux, `/dev/ttyUSB0` est un fichier spécial. On l'ouvre avec `os.open()`,
on écrit dedans avec `os.write()`, on lit avec `os.read()`. Ce qui change d'un
fichier ordinaire, c'est qu'il faut **le configurer** avant : vitesse, nombre de
bits, parité. C'est le rôle de `termios`.

## Les constantes du haut de fichier

```python
TIOCMBIS  = 0x5416     # « ioctl : mets ces bits de contrôle à 1 »
TIOCM_DTR = 0x002      # le bit DTR
TIOCM_RTS = 0x004      # le bit RTS
```

Ces trois valeurs existent dans les en-têtes C de Linux mais **pas dans le
module `termios` de Python**. Elles sont donc recopiées à la main. C'est
normal et volontaire ; ne t'inquiète pas de voir des nombres magiques ici.

```python
DEFAULT_BAUD = 38400
BAUDRATES = {1200: termios.B1200, ..., 115200: termios.B115200}
BAUD = BAUDRATES[DEFAULT_BAUD]
```

**Pourquoi cette table plutôt que le nombre directement ?** Parce que les
`termios.B*` sont des **codes internes du noyau**, pas des vitesses. Sur
beaucoup de systèmes Unix, `B9600` vaut `13` et non `9600` ; sur cette machine
les deux coïncident (vérifié : `python3 -c "import termios; print(termios.B9600)"`
affiche `9600`), mais c'est une coïncidence de plateforme sur laquelle il ne
faut pas compter. La table rend le code portable : on manipule des nombres
humains et on ne traduit qu'au dernier moment.

`BAUD` (le code de 38400) est exporté par `__init__.py` mais n'est plus utilisé
nulle part dans le code — voir [10-relecture.md](10-relecture.md).

## `baud_constant(baud)`

```python
def baud_constant(baud):
    try:
        return BAUDRATES[baud]
    except KeyError:
        connues = ", ".join(str(v) for v in sorted(BAUDRATES))
        raise ValueError(f"Vitesse non gérée : {baud} (connues : {connues})")
```

Traduit une vitesse humaine en code noyau. Si la vitesse est inconnue, elle
lève une `ValueError` qui **liste les vitesses acceptées** — un message d'erreur
utile plutôt qu'un `KeyError: 3000` sec. C'est un bon réflexe à reprendre.

## La classe `SerialPort`

### `__init__(self, device, baud=DEFAULT_BAUD)`

Ne fait qu'enregistrer les paramètres. **Rien n'est ouvert ici** : construire
l'objet ne touche pas au matériel. C'est `open()` qui le fait.

```python
self.baud = baud_constant(baud) if baud in BAUDRATES else baud
```

Cette ligne accepte indifféremment `38400` (nombre humain) ou `termios.B38400`
(code noyau), pour ne casser aucun appel existant. Elle a un défaut, décrit dans
la [relecture](10-relecture.md#3-une-vitesse-inconnue-passe-sans-erreur).

`self.fd = None` : `fd` veut dire *file descriptor*, le numéro entier que le
noyau donne à un fichier ouvert. `None` signifie « pas encore ouvert ».

### `open(self)`

```python
self.fd = os.open(self.device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
self.configure()
return self
```

Les trois drapeaux, un par un :

- `O_RDWR` : lecture et écriture, évidemment.
- `O_NOCTTY` : « ce port ne devient pas mon terminal de contrôle ». Sans lui, un
  Ctrl+C arrivant sur la ligne série pourrait tuer le programme. Sécurité.
- `O_NONBLOCK` : `os.read()` ne bloque jamais ; s'il n'y a rien, il lève une
  erreur au lieu d'attendre. C'est voulu : c'est `select()` qui gère l'attente,
  avec un vrai délai maximal. Bloquer sur `read()` serait ingérable.

`return self` permet d'écrire `port = SerialPort(dev).open()` en une ligne.

### `configure(self)`

Le cœur technique du fichier. `termios.tcgetattr(fd)` renvoie une liste de
7 éléments, dans un ordre fixé par POSIX :

| Index | Nom | Ce que le code en fait |
|---|---|---|
| 0 | `iflag` — traitement en entrée | `= 0` : aucune traduction (pas de CR→LF, pas de contrôle de flux XON/XOFF) |
| 1 | `oflag` — traitement en sortie | `= 0` : aucune traduction |
| 2 | `cflag` — contrôle | 8 bits, pas de parité, 1 bit de stop (voir ci-dessous) |
| 3 | `lflag` — mode ligne | `= 0` : mode **raw**. Pas d'écho, pas d'attente d'une ligne entière |
| 4 | `ispeed` | vitesse en réception |
| 5 | `ospeed` | vitesse en émission |
| 6 | `cc` — caractères de contrôle | `VMIN = 0`, `VTIME = 0` : `read()` rend ce qui est là, tout de suite |

Le détail du `cflag` :

```python
attrs[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE
              | termios.HUPCL | termios.CRTSCTS)
attrs[2] |= termios.CS8 | termios.CLOCAL | termios.CREAD
```

- `&= ~(…)` **efface** ces bits, `|= …` les **allume**. C'est l'idiome classique
  de manipulation de drapeaux.
- `PARENB` effacé + `CS8` allumé + `CSTOPB` effacé = **8N1** : 8 bits de données,
  aucune parité (N), 1 bit de stop. C'est le réglage universel des ADAM.
- `CRTSCTS` effacé : pas de contrôle de flux matériel (les ADAM n'en font pas).
- `CLOCAL` : ignore les lignes de modem — sans lui, l'ouverture peut rester
  bloquée à attendre une porteuse qui n'existe pas.
- `CREAD` : autoriser la réception. Sans lui, on n'entend rien.
- **`HUPCL` effacé** : c'est la ligne la plus subtile du fichier. Par défaut, le
  noyau fait retomber DTR quand le dernier descripteur du port se ferme. Sur
  beaucoup de convertisseurs USB-série, DTR à 0 coupe physiquement l'émission.
  En l'effaçant, DTR reste levé et le convertisseur continue de fonctionner
  entre deux ouvertures — ce qui compte beaucoup pour `diagnostic.sweep()`, qui
  ouvre et referme le port à chaque vitesse.

`termios.TCSANOW` : applique les réglages immédiatement (par opposition à
« après avoir vidé les tampons »).

### `raise_dtr_rts(self)`

```python
fcntl.ioctl(self.fd, TIOCMBIS, struct.pack("I", TIOCM_DTR | TIOCM_RTS))
```

Force les lignes DTR et RTS à l'état haut. Certains convertisseurs USB-série
s'en servent comme alimentation ou comme signal « je suis prêt à émettre » et
restent muets sans elles. `struct.pack("I", …)` transforme l'entier en 4 octets
bruts, format attendu par l'`ioctl`.

Le `try/except OSError: pass` couvre le cas d'un pseudo-terminal (utile pour
tester sans matériel) qui n'a pas de lignes de contrôle : l'appel échoue, et
c'est sans conséquence.

### `flush_input(self)`

Jette les octets en attente en réception. Utilisé par `diagnostic.attempt()`
avant chaque essai isolé, pour ne pas confondre la réponse de l'essai précédent
avec celle de l'essai en cours.

**La boucle de mesure ne s'en sert délibérément pas** : dans une boucle, une
trame en cours d'arrivée est une réponse légitime, pas un résidu. Vider le
tampon là couperait des trames en deux.

### `write(self, text)`

```python
os.write(self.fd, text.encode("ascii"))
termios.tcdrain(self.fd)
```

`encode("ascii")` : le protocole ADAM est purement ASCII, donc la conversion est
sans ambiguïté. `tcdrain()` **attend que tous les octets soient réellement
partis sur le fil** avant de rendre la main. Sans lui, on repasserait en lecture
alors que la requête est encore dans le tampon d'émission — et sur une liaison
RS-485 semi-duplex, on manquerait le début de la réponse.

### `read_frame(self, timeout=2.0)`

La fonction la plus dense du fichier. Elle accumule les octets jusqu'au `\r`.

```python
deadline = time.monotonic() + timeout
data = bytearray()

while time.monotonic() < deadline:
    remaining = max(0.0, deadline - time.monotonic())
    readable, _, _ = select.select([self.fd], [], [], remaining)
    if not readable:
        break
    ...
    data.extend(chunk)
    if b"\r" in data:
        frame, _, rest = bytes(data).partition(b"\r")
        return frame.decode("ascii", errors="replace")
```

Points à comprendre :

- **`time.monotonic()` et pas `time.time()`** : une horloge qui ne recule
  jamais, même si l'heure système change. Règle générale : pour mesurer une
  *durée*, `monotonic()` ; pour afficher une *date*, `datetime.now()`.
- **`deadline` calculée une fois**, et `remaining` recalculée à chaque tour :
  le délai total ne dérive pas, même si la réponse arrive en dix morceaux.
- **`select.select([fd], [], [], remaining)`** : « préviens-moi quand il y a
  quelque chose à lire, ou au bout de `remaining` secondes ». Le troisième
  argument vide, ce sont les descripteurs en écriture ; le quatrième, le délai.
- **Un `bytearray`, pas des `bytes`** : `bytes` est immuable, donc `data +=
  chunk` recopierait tout à chaque fois. `bytearray.extend()` ajoute en place.
- **`partition(b"\r")`** coupe en trois : avant, le séparateur, après. La trame
  utile est la première part ; le terminateur n'est pas rendu à l'appelant.
- **`errors="replace"`** : un octet parasite (parasite électrique sur le câble)
  devient `�` au lieu de faire planter le décodage. Le contrôle de la
  somme, plus haut dans la pile, rejettera la trame — mieux vaut une trame
  rejetée qu'une exception non prévue.

Les deux fins possibles :

```python
if data:
    raise TimeoutError(f"Réponse incomplète ({len(data)} octets reçus avant timeout)")
raise TimeoutError("Aucune réponse reçue.")
```

La distinction est précieuse au diagnostic : *rien du tout* signifie souvent un
problème de câblage ou d'adresse ; *quelque chose d'incomplet* signifie souvent
une mauvaise vitesse ou un `\r` jamais envoyé.

⚠️ La variable `rest` (ce qui suit le `\r` dans le même paquet) est ignorée :
voir la [relecture](10-relecture.md#2-les-octets-qui-suivent-le-r-sont-perdus).

### `close(self)`

Ferme le descripteur et remet `self.fd = None`. Le test `if self.fd is not None`
rend l'appel **idempotent** : fermer deux fois ne provoque pas d'erreur.

### `__enter__` / `__exit__`

Ces deux méthodes font de `SerialPort` un *gestionnaire de contexte*, ce qui
permet :

```python
with SerialPort("/dev/ttyUSB0", 9600) as serial:
    serial.write("#01S0\r")
    print(serial.read_frame())
# ici le port est fermé, même si une exception a été levée
```

`__exit__` renvoie `False` : « je n'ai pas traité l'exception, laisse-la
remonter ». Renvoyer `True` l'avalerait silencieusement — presque toujours une
erreur.
