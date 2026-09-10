"""Grammaire de lecture du fond de panier ADAM-5000.

Ce qui est ici répond à la question « comment on demande » : la forme de la
requête, la place du slot, la trame d'activation de la checksum. C'est propre
à une famille de matériel, pas au protocole : un module autonome (ADAM-4000,
ICPcon I-7000) lit par `#<adresse>`, sans slot, et n'aurait rien à faire de
ces fonctions.

Requête analogique   : #<adresse>S<slot>      (réponse accusée par '>')
Requête tout ou rien : $<adresse>S<slot>6     (réponse accusée par '!')

Paquet en cours de constitution : l'étape 4 du chantier y ajoute le
descripteur de famille et son registre (`base.py`, `adam5000.py`,
`autonome.py`) ; ce fichier deviendra le point d'entrée qui les expose. Les
trames produites ici ne doivent pas changer en chemin — les tests les figent
caractère par caractère.

Aucune commande de sortie n'est construite ici, ni ailleurs : seule l'image
des états d'un module tout ou rien est lue.
"""
from .. import protocol

# Trame d'activation de la checksum, telle que fournie par la documentation du
# module (notation Advantech %AANNCCFF) :
#   %   01        00          08              40
#       adresse   champ       38400 bauds     format de données,
#                 suivant                     bit 6 à 1 = checksum
# Elle est reprise à l'identique : ne recomposer ces champs qu'avec la
# documentation du module sous les yeux (--config-command permet de la
# remplacer sans toucher au code).
ENABLE_CHECKSUM = "%01000840"

def read_command(address=protocol.DEFAULT_ADDRESS, slot=0):
    """Commande de lecture, sans habillage : utile pour l'envoyer telle quelle."""
    return f"#{address}S{slot}"

def build_command(address=protocol.DEFAULT_ADDRESS, slot=0, checksum=True):
    return protocol.build_frame(read_command(address, slot), checksum)

def digital_read_command(address=protocol.DEFAULT_ADDRESS, slot=0):
    """Lecture des voies tout ou rien d'un module de fond de panier (ADAM-5050).

    Grammaire distincte de la lecture analogique : '$' au lieu de '#', et un 6
    final imposé par la documentation. La réponse est accusée par '!' et non
    par '>', d'où le paramètre `ack` de protocol.verify_frame().
    """
    return f"${address}S{slot}6"
