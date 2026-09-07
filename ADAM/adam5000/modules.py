"""Décodage de la charge utile, propre à chaque module d'E/S.

C'est ici que se rajoute le support d'un autre module (5017, 5018…) : la
charge utile arrive déjà validée par protocol.verify_frame(). Un module dont
la requête ou l'accusé diffèrent — le 5050 lit par `$aaS<slot>6` et répond
par '!' — demande en plus sa commande dans protocol.py.

Le nombre de voies et la largeur des champs sont des hypothèses sur le
module câblé, pas des vérités : l'ADAM-5081 compte 4 voies, mais la réponse
peut contenir plusieurs champs par voie. Ils sont donc paramétrables, et
possible_layouts() sert à retrouver le bon découpage face au matériel.
"""

from .protocol import DEFAULT_ADDRESS

EXPECTED_CHANNELS = 8
EXPECTED_WIDTH = 10

# ADAM-5050 : 16 voies tout ou rien, configurables en entrée ou en sortie.
IO_CHANNELS = 16
IO_WORD_LENGTH = 4

# Emplacements du fond de panier ADAM-5000, numérotés à partir de zéro.
IO_SLOTS = 4

# Découpages plausibles proposés au diagnostic : au-delà, on lit du bruit.
CANDIDATE_CHANNELS = (1, 2, 4, 8, 16)

def parse_5081(payload, channels=EXPECTED_CHANNELS, width=EXPECTED_WIDTH):
    """ADAM-5081 : `channels` voies de `width` chiffres."""
    expected_len = channels * width

    if len(payload) != expected_len:
        raise ValueError(
            f"Longueur invalide : {len(payload)} au lieu de {expected_len}"
        )

    if not payload.isdigit():
        raise ValueError("Données non numériques")

    values = []
    for i in range(channels):
        field = payload[i*width:(i+1)*width]
        values.append(int(field))

    return values

def parse_5050(payload, address=DEFAULT_ADDRESS):
    """ADAM-5050 : un mot hexadécimal de 4 chiffres, un bit par voie.

    La voie 00 est le bit de poids faible. Certains modules réémettent
    l'adresse en tête de charge utile, d'autres non : les deux sont acceptés.
    """
    if payload.upper().startswith(address.upper()):
        payload = payload[len(address):]

    word = payload[:IO_WORD_LENGTH].upper()

    if len(word) < IO_WORD_LENGTH or any(c not in "0123456789ABCDEF" for c in word):
        raise ValueError(f"Mot d'état illisible : {payload!r}")

    value = int(word, 16)

    return [(value >> channel) & 1 for channel in range(IO_CHANNELS)]

def possible_layouts(payload, candidates=CANDIDATE_CHANNELS):
    """Rend les découpages entiers de la charge utile, pour le diagnostic.

    Un découpage qui répète la même valeur d'une voie à l'autre est le signe
    qu'il coupe les champs au mauvais endroit.
    """
    layouts = []

    for channels in candidates:
        if not payload or len(payload) % channels:
            continue

        width = len(payload) // channels
        fields = [payload[i*width:(i+1)*width] for i in range(channels)]
        layouts.append((channels, width, fields))

    return layouts
