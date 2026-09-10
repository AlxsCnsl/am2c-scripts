# 13. `familles` — la grammaire de requête de l'ADAM-5000

Fichier : [serie/dcon/familles/\_\_init\_\_.py](../serie/dcon/familles/__init__.py) — 47 lignes.

**Rôle :** savoir *comment poser la question* à un module ADAM-5000 sur le
fond de panier — le préfixe de la commande, la place de l'adresse et du slot,
la trame qui active la checksum. Ce que `protocol.py`
([04-protocol.md](04-protocol.md)) ignore volontairement : lui ne sait
qu'habiller et vérifier une chaîne déjà écrite, pas la composer.

C'est un paquet Python (un dossier `familles/` avec un `__init__.py`), mais
aujourd'hui un seul fichier y vit ; on l'importe comme un module ordinaire
(`from . import familles`).

## Pourquoi ce n'est pas dans `protocol.py`

Un module ADAM-5000 se lit avec un slot (`#<adresse>S<slot>`) parce qu'il vit
sur un fond de panier à plusieurs emplacements. Un module autonome de la même
famille DCON (ADAM-4000, ICPcon I-7000) se lit par `#<adresse>` seul, sans
slot : la notion même de slot n'a pas de sens pour lui. Séparer cette
grammaire de l'enveloppe générique est ce qui permettrait, le jour où un tel
module serait câblé, de ne toucher qu'à ce fichier — `protocol.py`, lui,
n'a besoin de rien savoir de plus.

Aucune commande de sortie n'est construite ici, ni ailleurs dans le paquet :
seule l'image des états d'un module tout ou rien est lue (voir
[07-configuration.md](07-configuration.md#la-seule-fonction-du-paquet-qui-modifie-le-matériel)).

## Les fonctions et la constante

```python
from .. import protocol

ENABLE_CHECKSUM = "%01000840"

def read_command(address=protocol.DEFAULT_ADDRESS, slot=0):
    return f"#{address}S{slot}"

def build_command(address=protocol.DEFAULT_ADDRESS, slot=0, checksum=True):
    return protocol.build_frame(read_command(address, slot), checksum)

def digital_read_command(address=protocol.DEFAULT_ADDRESS, slot=0):
    return f"${address}S{slot}6"
```

### `read_command(address="01", slot=0)` → `#01S0`

Rend la commande **nue**, sans somme ni terminateur. Utile à deux endroits :
`diagnostic.probes()`, qui décide lui-même de l'habillage à essayer, et
`cli.show_raw()`, qui affiche la requête avant de l'envoyer.

### `build_command(address="01", slot=0, checksum=True)` → `#01S007\r`

Le raccourci : `protocol.build_frame(read_command(...))`. C'est ce qu'appelle
`Monitor.request()` à chaque cycle (voir [06-monitor.md](06-monitor.md)).

### `digital_read_command(address="01", slot=0)` → `$01S06`

La lecture d'un ADAM-5050. Deux différences avec la lecture analogique : le
préfixe `$` au lieu de `#`, et un `6` final imposé par la documentation du
module (c'est le code de la fonction « lire l'image des E/S »). Sa réponse est
accusée par `!`, pas par `>` — d'où le paramètre `ack` de
`protocol.verify_frame()` du côté appelant.

Vérifié : `familles.read_command("01", 0)` → `"#01S0"`,
`familles.digital_read_command("01", 2)` → `"$01S26"`,
`familles.build_command("01", 0)` → `"#01S007\r"`.

### `ENABLE_CHECKSUM = "%01000840"`

La trame d'activation de la checksum, telle que fournie par la documentation
du module (notation Advantech `%AANNCCFF`) :

| Morceau | Valeur | Sens |
|---|---|---|
| `%` | | commande de configuration |
| `AA` | `01` | adresse actuelle du module |
| `NN` | `00` | nouvelle adresse (ici : champ suivant, laissé à 00) |
| `CC` | `08` | code de vitesse — `08` = **38400 bauds** |
| `FF` | `40` | format de données ; le bit 6 à 1 (0x40) active la checksum |

⚠️ **Cette trame reconfigure aussi la vitesse à 38400**, quelle que soit la
vitesse à laquelle tu parlais au module. Le lanceur `lancer_adam.sh` le dit
explicitement à l'utilisateur avant de confirmer. Ne recompose ces champs
qu'avec la documentation du module sous les yeux ; l'option `--config-command`
existe précisément pour envoyer une autre trame sans toucher au code. C'est
`configuration.enable_checksum()` ([07-configuration.md](07-configuration.md))
qui l'envoie par défaut.

## Qui importe ce fichier

`monitor.py`, `diagnostic.py`, `configuration.py` et `cli.py` importent tous
`familles` à côté de `protocol` — c'est la seule façon de composer une requête
de lecture ADAM-5000 dans ce dépôt. `__init__.py` du paquet `dcon` ne
réexporte que `build_command` et `ENABLE_CHECKSUM` dans son API publique ;
`read_command` et `digital_read_command` restent accessibles via
`from dcon import familles`.
