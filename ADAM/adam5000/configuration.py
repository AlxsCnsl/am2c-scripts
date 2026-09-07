"""Couche application : commandes de configuration ponctuelles.

Séparée de monitor.py : ici une seule trame part et une seule réponse revient,
sans boucle, sans tentatives ni statistiques.

L'activation de la checksum est elle-même envoyée sans checksum : elle
s'adresse à un module qui n'en attend pas encore.
"""
from . import protocol
from .serial_port import DEFAULT_BAUD, SerialPort

def send_once(port, command, checksum=False, response_timeout=2.0,
              baud=DEFAULT_BAUD):
    """Envoie une commande brute et rend la réponse, terminateur retiré."""
    with SerialPort(port, baud) as serial:
        serial.write(protocol.build_frame(command, checksum))
        return serial.read_frame(response_timeout)

def enable_checksum(port, command=protocol.ENABLE_CHECKSUM, response_timeout=2.0,
                    baud=DEFAULT_BAUD):
    """Active la checksum du module ; rend la réponse (!<adresse> si acceptée)."""
    response = send_once(port, command, checksum=False,
                         response_timeout=response_timeout, baud=baud)

    if not response.startswith(protocol.CONFIG_ACK):
        raise ValueError(f"Commande refusée par le module : {response!r}")

    return response