"""Couche application : boucle de lecture, tentatives et statistiques.

Ne produit aucun affichage : run() rend des Measurement ou des Failure, que
l'appelant met en forme comme il veut (console, CSV, autre).
"""
import time
from collections import namedtuple
from datetime import datetime

from . import familles, protocol
from .modules import (
    EXPECTED_CHANNELS,
    EXPECTED_WIDTH,
    IO_CHANNELS,
    IO_SLOTS,
    parse_5050,
    parse_5081,
)
from .serial_port import DEFAULT_BAUD, SerialPort

DEFAULT_ADDRESS = protocol.DEFAULT_ADDRESS
DEFAULT_SLOT = 0

Measurement = namedtuple("Measurement", "timestamp values rejected")
Failure = namedtuple("Failure", "attempts rejected_total last_error")

class Monitor:
    def __init__(self, port, interval=2.0, retries=5, retry_delay=0.5,
                 response_timeout=2.0, address=DEFAULT_ADDRESS, slot=DEFAULT_SLOT,
                 checksum=True, channels=EXPECTED_CHANNELS, width=EXPECTED_WIDTH,
                 baud=DEFAULT_BAUD):
        self.port = port
        self.baud = baud
        self.interval = interval
        self.retries = retries
        self.retry_delay = retry_delay
        self.response_timeout = response_timeout
        self.address = address
        self.slot = slot
        # Doit correspondre à l'état réel du module : une requête avec
        # checksum reste sans réponse si le module n'en attend pas.
        self.checksum = checksum
        # Hypothèse de découpage, à confronter au module réel (--raw).
        self.channels = channels
        self.width = width

        self.last_frame = None
        self.rejected_total = 0
        self.rejected_since_ok = 0
        self.serial = None

    def open(self):
        self.serial = SerialPort(self.port, self.baud).open()
        return self

    def close(self):
        if self.serial is not None:
            self.serial.close()
            self.serial = None

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def request(self):
        """Trame envoyée à chaque cycle : propre au module lu."""
        return familles.build_command(self.address, self.slot, self.checksum)

    def decode(self, response):
        """Contrôle de trame puis découpage en voies : propre au module lu."""
        payload = protocol.verify_frame(response, self.checksum)
        return parse_5081(payload, self.channels, self.width)

    def read_once(self):
        # Ne pas vider le buffer ici.
        # On envoie une seule requête puis on attend la réponse complète.
        self.last_frame = None
        self.serial.write(self.request())
        response = self.serial.read_frame(self.response_timeout)
        # Conservée telle quelle : le découpage en voies n'est qu'une
        # hypothèse, la trame brute est le seul juge en cas de doute.
        self.last_frame = response
        return self.decode(response)

    def cycle(self):
        """Un cycle de mesure : jusqu'à self.retries tentatives."""
        last_error = None

        for attempt in range(1, self.retries + 1):
            try:
                values = self.read_once()
            except (ValueError, TimeoutError, BlockingIOError) as exc:
                last_error = exc
                self.rejected_total += 1
                self.rejected_since_ok += 1

                if attempt < self.retries:
                    # Laisser le temps à l'ADAM de finir sa réponse précédente.
                    time.sleep(self.retry_delay)
            else:
                rejected = self.rejected_since_ok
                self.rejected_since_ok = 0
                return Measurement(datetime.now(), values, rejected)

        return Failure(self.retries, self.rejected_total, last_error)

    def run(self):
        while True:
            yield self.cycle()
            # Intervalle entre deux cycles de mesure complets.
            time.sleep(self.interval)

class Monitor5050(Monitor):
    """ADAM-5050 : 16 voies tout ou rien, lues sur un slot du fond de panier.

    Aucune sortie n'est commandée : seule leur image est lue, ce qui écarte
    tout risque d'activation accidentelle.
    """

    def __init__(self, port, slot=DEFAULT_SLOT, **kwargs):
        if slot not in range(IO_SLOTS):
            raise ValueError(
                f"Slot du 5050 hors du fond de panier : {slot} (attendu 0 à {IO_SLOTS - 1})"
            )

        super().__init__(port, slot=slot, channels=IO_CHANNELS, **kwargs)

    def request(self):
        command = familles.digital_read_command(self.address, self.slot)
        return protocol.build_frame(command, self.checksum)

    def decode(self, response):
        payload = protocol.verify_frame(response, self.checksum,
                                        ack=protocol.CONFIG_ACK)
        return parse_5050(payload, self.address)
