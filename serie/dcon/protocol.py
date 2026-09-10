"""Couche protocole : l'enveloppe ASCII du DCON, et rien d'autre.

Ici on habille et on contrôle une trame ; on ne dit jamais ce qu'elle demande.
Le jeu de commandes — la forme exacte de la requête, l'emplacement qu'elle
désigne dans un fond de panier, la trame qui active la checksum — appartient
à la famille de matériel et vit à côté.

Ce qui est commun à toute la famille ASCII Advantech/DCON :

Requête  : <corps>[<checksum>]<CR>
Réponse  : <accusé><charge utile>[<checksum>]<CR>

L'accusé positif vaut '>' pour une lecture de valeurs, '!' pour un état ou
une configuration acceptée ; un '?' à la place signale un refus du module.

La checksum est optionnelle sur ces modules : sorti d'usine, un module n'en
attend pas et n'en renvoie pas. Toutes les fonctions prennent donc un drapeau
`checksum`, qui doit refléter l'état réel du module ; sinon la trame envoyée
est ignorée et la réponse mal découpée.
"""

TERMINATOR = "\r"
ACK = ">"
CONFIG_ACK = "!"

# Adresse de station par défaut : celle que porte un module sorti d'usine.
DEFAULT_ADDRESS = "01"

def checksum_ascii(text):
    return f"{sum(text.encode('ascii')) & 0xFF:02X}"

def build_frame(command, checksum=True):
    """Habille une commande : checksum optionnelle puis terminateur."""
    body = command.strip().upper()
    return body + (checksum_ascii(body) if checksum else "") + TERMINATOR

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
