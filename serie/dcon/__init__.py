"""Lecture de modules d'E/S sur liaison série, sans dépendance externe.

« DCON » est le nom du protocole ASCII que parlent aussi bien les Advantech
ADAM — 5000 à fond de panier, 4000 autonomes — que les ICPcon I-7000. Le
paquet porte ce nom plutôt que celui d'une gamme : la grammaire d'enveloppe
est commune, seuls la commande de lecture et le décodage changent d'un
modèle à l'autre.

Seul l'ADAM-5000 est câblé ici pour l'instant.
"""
from .configuration import enable_checksum, send_once
from .familles import ENABLE_CHECKSUM, build_command
from .modules import EXPECTED_CHANNELS, EXPECTED_WIDTH, parse_5081
from .monitor import Failure, Measurement, Monitor
from .settings import SlotSettings, load as load_settings
from .protocol import (
    build_frame,
    checksum_ascii,
    verify_frame,
)
from .serial_port import BAUD, SerialPort

__all__ = [
    "BAUD",
    "ENABLE_CHECKSUM",
    "EXPECTED_CHANNELS",
    "EXPECTED_WIDTH",
    "Failure",
    "Measurement",
    "Monitor",
    "SerialPort",
    "SlotSettings",
    "build_command",
    "build_frame",
    "checksum_ascii",
    "enable_checksum",
    "load_settings",
    "parse_5081",
    "send_once",
    "verify_frame",
]
