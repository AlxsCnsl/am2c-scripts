# 12. `settings.py` — décrire le rack dans un fichier

Fichier : [ADAM/adam5000/settings.py](../ADAM/adam5000/settings.py) — 176 lignes.

**Rôle :** lire un fichier JSON qui décrit ce qui est enfiché dans le fond de
panier — un bloc par slot — le valider, et rendre une liste de `SlotSettings`.
Aucune E/S série : ce fichier ne connaît que le disque.

C'est la seule couche du paquet qui touche à un fichier plutôt qu'au port
série. Elle est volontairement indépendante des autres : elle importe
seulement des **constantes** de `modules.py`, `protocol.py` et
`serial_port.py` (`IO_SLOTS`, `SUPPORTED_MODULES`, `DEFAULT_ADDRESS`,
`BAUDRATES`) pour valider contre les mêmes limites que le reste du paquet,
jamais leurs fonctions.

## Ce que le fichier décrit, et ce qu'il ne décrit pas

```json
{
  "slots": [
    {"slot": 0, "module": "5081", "vitesse": 38400, "checksum": false},
    {"slot": 2, "module": "5050", "vitesse": 38400, "checksum": false}
  ]
}
```

Le port série et les droits d'accès (`/dev/ttyUSB0`, `sudo` ou groupe
`dialout`) **n'y figurent pas**. C'est délibéré : ces deux réglages dépendent
de la machine sur laquelle le script tourne, pas du rack physique, et restent
choisis au lancement par `choisir_port.sh`. Le fichier ne décrit que ce qui ne
bouge pas d'un PC à l'autre : quel module est enfiché où, à quelle vitesse il
parle, et s'il attend une somme de contrôle.

Un exemple concret vit dans [ADAM/config.json](../ADAM/config.json).

## Le type de résultat

```python
SlotSettings = namedtuple("SlotSettings", "slot module baud checksum address")
```

Un `namedtuple` par slot décrit. `module` porte la référence Advantech **sans
son préfixe** : `"5050"`, pas `"ADAM-5050"` — c'est `read_module()` qui
retire le préfixe s'il est présent dans le fichier.

## `load(path=DEFAULT_FILE)`

```python
try:
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
except FileNotFoundError:
    raise ValueError(f"Fichier de réglages introuvable : {path}") from None
except json.JSONDecodeError as exc:
    raise ValueError(f"{path} n'est pas un JSON valide : {exc}") from None

return parse(document)
```

`DEFAULT_FILE = "config.json"`, cherché dans le répertoire courant — c'est-à-
dire `ADAM/`, puisque le paquet se lance avec `python3 -m adam5000` depuis ce
dossier (voir [01-environnement.md](01-environnement.md)).

Les deux erreurs possibles à l'ouverture (fichier absent, JSON mal formé) sont
converties en une seule `ValueError` avec un message qui dit **quoi faire**,
plutôt que de laisser remonter une `FileNotFoundError` ou une
`json.JSONDecodeError` brute. `from None` supprime la trace de l'exception
d'origine dans l'affichage : le message de `ValueError` suffit, la trace
technique n'apporterait rien à l'utilisateur.

## `parse(document)`

Valide la forme générale du document — un objet avec une clé `"slots"`
contenant une liste non vide — puis appelle `parse_slot()` sur chaque bloc.

```python
if item.slot in vus:
    raise ValueError(
        f"Slot {item.slot} décrit deux fois (blocs n°{vus[item.slot]} "
        f"et n°{rank}) : un seul réglage par slot."
    )
```

`vus` associe un numéro de slot déjà rencontré au rang du bloc qui l'a
réservé, pour que le message d'erreur cite les deux blocs en cause plutôt que
de dire juste « doublon ». La liste rendue est triée par numéro de slot
(`sorted(..., key=lambda item: item.slot)`), indépendamment de l'ordre dans
lequel les blocs apparaissent dans le fichier.

## `parse_slot(entry, rank)`

Valide un bloc et construit son `SlotSettings`. Deux contrôles précèdent la
lecture des champs eux-mêmes :

```python
inconnues = set(entry) - set(REQUIRED_KEYS) - set(OPTIONAL_KEYS)
```

`REQUIRED_KEYS = ("slot", "module", "vitesse", "checksum")` et
`OPTIONAL_KEYS = ("adresse",)`. Une clé mal orthographiée (`"vitess"`) est
donc signalée explicitement, au lieu d'être silencieusement ignorée puis de
faire échouer la validation suivante avec un message qui ne mentionnerait pas
la faute de frappe.

## Les fonctions `read_*` : une par champ

Chacune prend la valeur brute (déjà sortie du JSON) et une étiquette pour le
message d'erreur, et rend soit la valeur validée, soit lève une `ValueError`.

| Fonction | Champ JSON | Contrôle |
|---|---|---|
| `read_slot(value, rank)` | `slot` | entier, dans `range(IO_SLOTS)` (0 à 3) |
| `read_module(value, etiquette)` | `module` | dans `SUPPORTED_MODULES` une fois le préfixe `ADAM-` retiré |
| `read_baud(value, etiquette)` | `vitesse` | entier, dans `BAUDRATES` (1200 à 115200) |
| `read_checksum(value, etiquette)` | `checksum` | booléen strict (`true`/`false`) |
| `read_address(value, etiquette)` | `adresse` (optionnel, défaut `DEFAULT_ADDRESS`) | deux chiffres hexadécimaux |

### `read_slot` et `read_baud` : le piège de `bool`

```python
if isinstance(value, bool) or not isinstance(value, int):
    raise ValueError(...)
```

En Python, `bool` est une sous-classe d'`int` : `isinstance(True, int)` vaut
`True`, et `True == 1`. Sans le test `isinstance(value, bool)` en premier,
`{"slot": true, ...}` serait accepté silencieusement comme `slot: 1`. Le test
explicite ferme cette porte.

### `read_module` : les trois écritures acceptées

```python
reference = str(value).strip().upper()
if reference.startswith("ADAM-"):
    reference = reference[len("ADAM-"):]
if reference not in SUPPORTED_MODULES:
    ...
```

`5050`, `"5050"` et `"ADAM-5050"` sont tous les trois acceptés et rendent la
même chaîne `"5050"`. `SUPPORTED_MODULES = ("5050", "5081")` — définie dans
[modules.py](../ADAM/adam5000/modules.py), voir
[05-modules.md](05-modules.md) — est la même liste que celle des fonctions
`parse_*` réellement écrites : ajouter un modèle, c'est ajouter son
décodage dans `modules.py` puis sa référence dans `SUPPORTED_MODULES`, ce qui
suffit à le rendre acceptable ici aussi.

### `read_checksum` : pourquoi il doit refléter l'état réel du module

```python
if not isinstance(value, bool):
    raise ValueError(f"{etiquette} : « checksum » doit valoir true ou false.")
```

Le commentaire du code le rappelle : une requête avec checksum reste sans
réponse si le module n'en attend pas, et l'inverse casse le découpage de la
réponse (voir [04-protocol.md](04-protocol.md)). Ce champ n'est donc pas
cosmétique — un mauvais réglage ici reproduit exactement le silence que
`diagnostic.py` sert à diagnostiquer.

## `--config` : le seul endroit qui appelle cette couche

`cli.show_settings(args)` ([09-cli.md](09-cli.md)) est le seul appelant de
`settings.load()`. Il lit le fichier, l'affiche sous forme de
tableau, puis quitte — **rien n'est envoyé sur le port série**. Aucun
`Monitor` n'est construit à partir des `SlotSettings` rendus : lire le rack et
lancer une lecture dessus sont deux actions séparées.

```
$ python3 -m adam5000 --config config.json
Fichier de réglages : config.json
2 slot(s) décrit(s). Rien n'est envoyé sur la liaison :
le fichier est seulement lu et contrôlé.

Slot | Module    | Vitesse | Checksum  | Adresse
   0 | ADAM-5081 |   38400 | activé    | 01
   2 | ADAM-5050 |   38400 | activé    | 01

Le port série reste choisi au lancement : il dépend du PC, pas du rack.
La lecture automatique de ces slots n'est pas encore branchée.
```

(Sortie réelle, obtenue avec [ADAM/config.json](../ADAM/config.json).)
