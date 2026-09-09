"""Lecture des modules ADAM-5000 sur liaison série, sans dépendance externe."""
from .configuration import enable_checksum, send_once
from .modules import EXPECTED_CHANNELS, EXPECTED_WIDTH, parse_5081
from .monitor import Failure, Measurement, Monitor
from .settings import SlotSettings, load as load_settings
from .protocol import (
    ENABLE_CHECKSUM,
    build_command,
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
