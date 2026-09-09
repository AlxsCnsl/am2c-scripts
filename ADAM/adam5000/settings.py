"""Couche réglages : description du rack ADAM lue dans un fichier JSON.

Le fichier décrit ce qui est enfiché dans le fond de panier — un bloc par
slot — et rien de ce qui dépend du PC. Le port série et les droits d'accès
en sont volontairement absents : ils changent d'une machine à l'autre et
restent choisis au lancement (`choisir_port.sh`), alors que le rack, lui, ne
bouge pas.

Format attendu :

    {
      "slots": [
        {"slot": 0, "module": "5081", "vitesse": 38400, "checksum": false},
        {"slot": 2, "module": "5050", "vitesse": 38400, "checksum": false}
      ]
    }

Un slot ne peut être décrit qu'une fois : un même emplacement ne porte qu'un
module. Seuls les slots réellement occupés sont à décrire.

Cette couche ne parle ni au port série ni au protocole : elle rend des
SlotSettings, que l'appelant traduit ensuite en Monitor.
"""
import json
from collections import namedtuple

from .modules import IO_SLOTS, SUPPORTED_MODULES
from .protocol import DEFAULT_ADDRESS
from .serial_port import BAUDRATES

# Cherché dans le répertoire courant, c'est-à-dire ADAM/ puisque le paquet se
# lance par `python3 -m adam5000` depuis ce dossier.
DEFAULT_FILE = "config.json"

REQUIRED_KEYS = ("slot", "module", "vitesse", "checksum")
OPTIONAL_KEYS = ("adresse",)

# `module` porte la référence Advantech sans son préfixe : « 5050 », « 5081 ».
SlotSettings = namedtuple("SlotSettings", "slot module baud checksum address")

def load(path=DEFAULT_FILE):
    """Lit le fichier de réglages et rend un SlotSettings par slot décrit."""
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except FileNotFoundError:
        raise ValueError(f"Fichier de réglages introuvable : {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} n'est pas un JSON valide : {exc}") from None

    return parse(document)

def parse(document):
    """Valide un document déjà décodé ; rend les slots triés par numéro."""
    if not isinstance(document, dict):
        raise ValueError("Le fichier doit contenir un objet JSON "
                         "avec une clé « slots ».")

    if "slots" not in document:
        raise ValueError("Clé « slots » absente : rien à configurer.")

    entries = document["slots"]

    if not isinstance(entries, list) or not entries:
        raise ValueError("« slots » doit être une liste d'au moins un bloc.")

    settings = []
    # Numéro de slot -> rang du bloc qui l'a réservé, pour nommer le doublon.
    vus = {}

    for rank, entry in enumerate(entries, start=1):
        item = parse_slot(entry, rank)

        if item.slot in vus:
            raise ValueError(
                f"Slot {item.slot} décrit deux fois (blocs n°{vus[item.slot]} "
                f"et n°{rank}) : un seul réglage par slot."
            )

        vus[item.slot] = rank
        settings.append(item)

    return sorted(settings, key=lambda item: item.slot)

def parse_slot(entry, rank):
    """Valide un bloc et rend le SlotSettings correspondant."""
    if not isinstance(entry, dict):
        raise ValueError(f"Bloc n°{rank} : un objet JSON est attendu.")

    inconnues = set(entry) - set(REQUIRED_KEYS) - set(OPTIONAL_KEYS)
    if inconnues:
        connues = ", ".join(REQUIRED_KEYS + OPTIONAL_KEYS)
        raise ValueError(
            f"Bloc n°{rank} : clé(s) inconnue(s) "
            f"{', '.join(sorted(inconnues))} (attendues : {connues})."
        )

    manquantes = [key for key in REQUIRED_KEYS if key not in entry]
    if manquantes:
        raise ValueError(
            f"Bloc n°{rank} : clé(s) manquante(s) {', '.join(manquantes)}."
        )

    slot = read_slot(entry["slot"], rank)
    etiquette = f"Bloc n°{rank} (slot {slot})"

    return SlotSettings(
        slot=slot,
        module=read_module(entry["module"], etiquette),
        baud=read_baud(entry["vitesse"], etiquette),
        checksum=read_checksum(entry["checksum"], etiquette),
        address=read_address(entry.get("adresse", DEFAULT_ADDRESS), etiquette),
    )

def read_slot(value, rank):
    # bool est un int en Python : true serait sinon accepté comme slot 1.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Bloc n°{rank} : « slot » doit être un entier.")

    if value not in range(IO_SLOTS):
        raise ValueError(
            f"Bloc n°{rank} : slot {value} hors du fond de panier "
            f"(0 à {IO_SLOTS - 1})."
        )

    return value

def read_module(value, etiquette):
    """Accepte 5050, \"5050\" ou \"ADAM-5050\" ; rend la référence nue."""
    reference = str(value).strip().upper()

    if reference.startswith("ADAM-"):
        reference = reference[len("ADAM-"):]

    if reference not in SUPPORTED_MODULES:
        connus = ", ".join(SUPPORTED_MODULES)
        raise ValueError(
            f"{etiquette} : module « {value} » non géré (connus : {connus}). "
            "Un autre modèle demande son décodage dans modules.py."
        )

    return reference

def read_baud(value, etiquette):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{etiquette} : « vitesse » doit être un entier.")

    if value not in BAUDRATES:
        connues = ", ".join(str(v) for v in sorted(BAUDRATES))
        raise ValueError(
            f"{etiquette} : vitesse {value} non gérée (connues : {connues})."
        )

    return value

def read_checksum(value, etiquette):
    # Doit refléter l'état réel du module : une requête avec checksum reste
    # sans réponse si le module n'en attend pas, et l'inverse casse le
    # découpage de la réponse.
    if not isinstance(value, bool):
        raise ValueError(
            f"{etiquette} : « checksum » doit valoir true ou false."
        )

    return value

def read_address(value, etiquette):
    adresse = str(value).strip().upper()

    if len(adresse) != 2 or any(c not in "0123456789ABCDEF" for c in adresse):
        raise ValueError(
            f"{etiquette} : adresse « {value} » invalide "
            "(deux chiffres hexadécimaux, par exemple 01)."
        )

    return adresse
