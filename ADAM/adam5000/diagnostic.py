"""Couche application : balayage de diagnostic, quand aucune trame ne revient.

Un module muet ne discute pas des mêmes conditions que le programme. Trois
réglages doivent concorder avant qu'un seul octet ne réponde — la vitesse,
l'état du checksum, l'adresse — et rien dans le silence ne dit lequel est en
cause. Le balayage essaie les combinaisons plausibles et rend celles qui ont
obtenu quelque chose.

Un module qui répond `?01` n'est pas muet : il a compris la requête et l'a
refusée. C'est déjà une réponse, et le balayage la rapporte comme telle.

Lecture seule : uniquement des interrogations (`$aaM`, `#aaS0`…), jamais une
commande de configuration (`%`), qui elle modifierait le module.

Ne produit aucun affichage : les fonctions rendent des Attempt, que l'appelant
met en forme.
"""
import time
from collections import namedtuple

from . import protocol
from .modules import IO_SLOTS
from .serial_port import BAUDRATES, SerialPort

# Vitesses par ordre de vraisemblance : 9600 est la valeur d'usine la plus
# répandue, 38400 celle que ce dépôt a longtemps supposée.
SCAN_BAUDS = (9600, 38400, 19200, 57600, 115200, 4800, 2400, 1200)

# Attente minimale d'un essai. Aux vitesses basses, le temps de transmission
# d'une trame dépasse ce plancher : d'où le calcul de probe_timeout().
MIN_TIMEOUT = 0.3
LONGEST_FRAME = 64

# Le balayage d'adresses est long : 256 essais par état du checksum. Il
# n'interroge donc qu'à une seule vitesse, et attend moins longtemps.
ADDRESS_TIMEOUT = 0.15

Attempt = namedtuple("Attempt",
                     "baud checksum address slot command label response error")

def probe_timeout(baud):
    """Laisse le temps à la trame la plus longue d'arriver, même à 1200 bauds."""
    return max(MIN_TIMEOUT, LONGEST_FRAME * 10 / baud)

def probes(address, slots=IO_SLOTS):
    """Interrogations sans effet de bord, de la plus générale à la plus précise."""
    commands = [
        (f"${address}M", "nom du module", None),
        (f"${address}F", "version du micrologiciel", None),
        (f"${address}2", "configuration du module", None),
        (protocol.read_command(address, 0), "lecture analogique, slot 0", None),
    ]

    for slot in range(slots):
        commands.append((protocol.digital_read_command(address, slot),
                         f"16 E/S, slot {slot}", slot))

    return commands

def attempt(serial, baud, checksum, address, command, label, response_timeout,
            slot=None):
    """Un essai : rend la réponse obtenue, ou l'erreur rencontrée."""
    try:
        serial.flush_input()
        serial.write(protocol.build_frame(command, checksum))
        response = serial.read_frame(response_timeout)
    except (TimeoutError, ValueError, OSError) as exc:
        return Attempt(baud, checksum, address, slot, command, label, None, exc)

    return Attempt(baud, checksum, address, slot, command, label, response, None)

def accepted(attempt):
    """Vrai si le module a répondu autre chose qu'un refus."""
    return bool(attempt.response) and not attempt.response.startswith("?")

def sweep(port, address=protocol.DEFAULT_ADDRESS, bauds=SCAN_BAUDS,
          checksums=(False, True), slots=IO_SLOTS):
    """Balaie vitesse x checksum x interrogation ; rend chaque essai."""
    for baud in bauds:
        if baud not in BAUDRATES:
            continue

        timeout = probe_timeout(baud)

        try:
            serial = SerialPort(port, baud).open()
        except (OSError, ValueError) as exc:
            yield Attempt(baud, None, address, None, None,
                          "ouverture du port", None, exc)
            continue

        try:
            for checksum in checksums:
                for command, label, slot in probes(address, slots):
                    yield attempt(serial, baud, checksum, address,
                                  command, label, timeout, slot)
        finally:
            serial.close()

        # Laisser le convertisseur retomber avant de changer de vitesse.
        time.sleep(0.05)

def sweep_addresses(port, baud, checksums=(False, True)):
    """Cherche l'adresse du module en interrogeant les 256 possibles.

    Une seule vitesse : le produit des deux balayages serait interminable.
    """
    try:
        serial = SerialPort(port, baud).open()
    except (OSError, ValueError) as exc:
        yield Attempt(baud, None, None, None, None,
                      "ouverture du port", None, exc)
        return

    try:
        for value in range(256):
            address = f"{value:02X}"
            command = f"${address}M"

            for checksum in checksums:
                yield attempt(serial, baud, checksum, address, command,
                              "nom du module", ADDRESS_TIMEOUT)
    finally:
        serial.close()
