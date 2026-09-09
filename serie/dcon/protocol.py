"""Couche protocole : grammaire ASCII Advantech, indépendante du module d'E/S.

Requête       : #<adresse>S<slot>[<checksum>]<CR>
Réponse       : ><charge utile>[<checksum>]<CR>   (un '?' à la place du '>' = erreur)
Tout ou rien  : $<adresse>S<slot>6[<checksum>]<CR> (réponse !<charge utile>)
Configuration : %<champs>[<checksum>]<CR>         (réponse !<adresse> si acceptée)

La checksum est optionnelle sur l'ADAM : un module sorti d'usine n'en attend
pas et n'en renvoie pas. Toutes les fonctions prennent donc un drapeau
`checksum`, qui doit refléter l'état réel du module ; sinon la trame envoyée
est ignorée et la réponse mal découpée.
"""

TERMINATOR = "\r"
ACK = ">"
CONFIG_ACK = "!"

# Adresse de station par défaut : celle que porte un module sorti d'usine.
DEFAULT_ADDRESS = "01"

# Trame d'activation de la checksum, telle que fournie par la documentation du
# module (notation Advantech %AANNCCFF) :
#   %   01        00          08              40
#       adresse   champ       38400 bauds     format de données,
#                 suivant                     bit 6 à 1 = checksum
# Elle est reprise à l'identique : ne recomposer ces champs qu'avec la
# documentation du module sous les yeux (--config-command permet de la
# remplacer sans toucher au code).
ENABLE_CHECKSUM = "%01000840"

def checksum_ascii(text):
    return f"{sum(text.encode('ascii')) & 0xFF:02X}"

def build_frame(command, checksum=True):
    """Habille une commande : checksum optionnelle puis terminateur."""
    body = command.strip().upper()
    return body + (checksum_ascii(body) if checksum else "") + TERMINATOR

def read_command(address=DEFAULT_ADDRESS, slot=0):
    """Commande de lecture, sans habillage : utile pour l'envoyer telle quelle."""
    return f"#{address}S{slot}"

def build_command(address=DEFAULT_ADDRESS, slot=0, checksum=True):
    return build_frame(read_command(address, slot), checksum)

def digital_read_command(address=DEFAULT_ADDRESS, slot=0):
    """Lecture des voies tout ou rien d'un module de fond de panier (ADAM-5050).

    Grammaire distincte de la lecture analogique : '$' au lieu de '#', et un 6
    final imposé par la documentation. La réponse est accusée par '!' et non
    par '>', d'où le paramètre `ack` de verify_frame().
    """
    return f"${address}S{slot}6"

def verify_frame(response, checksum=True, ack=ACK):
    """Valide la checksum et l'accusé positif, rend la charge utile."""
    body = response

    if checksum:
        if len(response) < 4:
            raise ValueError("Réponse trop courte")

        received = response[-2:].upper()
        body = response[:-2]

        if received != checksum_ascii(body):
            raise ValueError("Checksum invalide")

    elif len(response) < 2:
        raise ValueError("Réponse trop courte")

    if not body.startswith(ack):
        raise ValueError(f"Préfixe '{ack}' absent : {body!r}")

    return body[1:]
