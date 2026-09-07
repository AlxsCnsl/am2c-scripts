"""Couche transport : port série brut via termios.

Aucune dépendance externe (pas de pyserial) : le port est ouvert comme un
fichier et configuré en mode « raw », seul moyen de recevoir des trames
terminées par \\r sans que le noyau ne les retienne.
"""
import fcntl
import os
import select
import struct
import termios
import time

# Constantes de lignes de contrôle, absentes du module termios de Python.
TIOCMBIS = 0x5416
TIOCM_DTR = 0x002
TIOCM_RTS = 0x004

DEFAULT_BAUD = 38400

# Vitesses acceptées par les modules ADAM. La constante termios n'est pas le
# nombre : B9600 ne vaut pas 9600, d'où la table.
BAUDRATES = {
    1200: termios.B1200, 2400: termios.B2400, 4800: termios.B4800,
    9600: termios.B9600, 19200: termios.B19200, 38400: termios.B38400,
    57600: termios.B57600, 115200: termios.B115200,
}

BAUD = BAUDRATES[DEFAULT_BAUD]

def baud_constant(baud):
    """Traduit une vitesse en constante termios, avec un message clair."""
    try:
        return BAUDRATES[baud]
    except KeyError:
        connues = ", ".join(str(v) for v in sorted(BAUDRATES))
        raise ValueError(f"Vitesse non gérée : {baud} (connues : {connues})")

class SerialPort:
    def __init__(self, device, baud=DEFAULT_BAUD):
        self.device = device
        # Accepte indifféremment une vitesse (38400) ou une constante termios,
        # pour ne pas casser un appel existant.
        self.baud = baud_constant(baud) if baud in BAUDRATES else baud
        self.fd = None

    def open(self):
        # O_NOCTTY : le port ne devient pas le terminal de contrôle.
        # O_NONBLOCK : c'est select() qui gère l'attente, pas read().
        self.fd = os.open(self.device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.configure()
        return self

    def configure(self):
        try:
            attrs = termios.tcgetattr(self.fd)
        except termios.error as exc:
            raise ValueError(
                f"{self.device} n'est pas un port série exploitable ({exc})"
            ) from exc

        attrs[0] = 0
        attrs[1] = 0
        # HUPCL retiré : sans cela le noyau fait retomber DTR à la fermeture du
        # dernier descripteur, ce qui coupe l'émission sur bien des
        # convertisseurs USB-série.
        attrs[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE
                      | termios.HUPCL | termios.CRTSCTS)
        attrs[2] |= termios.CS8 | termios.CLOCAL | termios.CREAD
        attrs[3] = 0
        attrs[4] = self.baud
        attrs[5] = self.baud
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        self.raise_dtr_rts()

    def raise_dtr_rts(self):
        """Force DTR et RTS : certains convertisseurs n'émettent pas sans elles."""
        try:
            fcntl.ioctl(self.fd, TIOCMBIS, struct.pack("I", TIOCM_DTR | TIOCM_RTS))
        except OSError:
            # Un pseudo-terminal n'a pas de lignes de contrôle : sans effet.
            pass

    def flush_input(self):
        """Jette ce qui traîne en réception : utile avant un essai isolé.

        La boucle de mesure, elle, ne s'en sert pas : une trame en cours d'arrivée
        y est une réponse légitime, pas un résidu.
        """
        termios.tcflush(self.fd, termios.TCIFLUSH)

    def write(self, text):
        os.write(self.fd, text.encode("ascii"))
        # Attendre que tout soit réellement parti sur la ligne avant
        # de repasser en réception.
        termios.tcdrain(self.fd)

    def read_frame(self, timeout=2.0):
        """Accumule les octets jusqu'au \\r et rend la trame sans son terminateur."""
        deadline = time.monotonic() + timeout
        data = bytearray()

        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            readable, _, _ = select.select([self.fd], [], [], remaining)
            if not readable:
                break

            try:
                chunk = os.read(self.fd, 256)
            except BlockingIOError:
                time.sleep(0.01)
                continue

            if not chunk:
                time.sleep(0.01)
                continue

            data.extend(chunk)

            if b"\r" in data:
                frame, _, rest = bytes(data).partition(b"\r")
                return frame.decode("ascii", errors="replace")

        if data:
            raise TimeoutError(
                f"Réponse incomplète ({len(data)} octets reçus avant timeout)"
            )

        raise TimeoutError("Aucune réponse reçue.")

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
