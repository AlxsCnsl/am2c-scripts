"""Interface en ligne de commande : arguments et mise en forme de l'affichage."""
import argparse
import sys

from . import configuration, diagnostic, protocol
from .modules import (
    EXPECTED_CHANNELS,
    EXPECTED_WIDTH,
    IO_CHANNELS,
    parse_5050,
    possible_layouts,
)
from .serial_port import BAUDRATES, DEFAULT_BAUD
from .monitor import (
    DEFAULT_ADDRESS,
    DEFAULT_SLOT,
    IO_SLOTS,
    Measurement,
    Monitor,
    Monitor5050,
)

# Le vert et le rouge ne servent qu'à un écran : redirigée dans un fichier,
# la vue reste lisible sans séquences d'échappement.
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
CLEAR_SCREEN = "\033[2J\033[H"

def format_measurement(measurement, checksum=True, width=EXPECTED_WIDTH):
    stamp = measurement.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    line = (
        stamp + " | "
        + " | ".join(f"V{i}={v}" for i, v in enumerate(measurement.values))
        + f" | checksum={'OK' if checksum else 'désactivé'}"
        + f" | largeur={width}"
    )

    if measurement.rejected:
        line += f" | rejetées={measurement.rejected}"

    return line

def format_failure(failure):
    return (
        f"Avertissement : aucune trame valide après {failure.attempts} essais "
        f"(rejets cumulés={failure.rejected_total}, "
        f"dernière erreur={failure.last_error})"
    )

def format_attempt(attempt):
    etat = "avec" if attempt.checksum else "sans"
    refus = "" if diagnostic.accepted(attempt) else "   (refus, mais le module entend)"
    return (f"  {etat} checksum | {attempt.command} "
            f"({attempt.label}) -> {attempt.response!r}{refus}")

def suggest_command(port, trouvailles):
    """Propose la commande à relancer, en préférant un slot qui a vraiment répondu."""
    lectures = [a for a in trouvailles
                if a.slot is not None and diagnostic.accepted(a)]
    retenu = lectures[0] if lectures else trouvailles[0]

    options = [f"--port {port}", f"--baud {retenu.baud}",
               f"--address {retenu.address}"]

    if not retenu.checksum:
        options.append("--no-checksum")

    if retenu.slot is not None:
        options += ["--5050", f"--slot {retenu.slot}"]

    return "python3 -m adam5000 " + " ".join(options)

def run_scan(args):
    """Balaie les réglages possibles et rapporte ce qui a répondu."""
    print(f"Port : {args.port}")
    print("Balayage en lecture seule : aucune commande de configuration n'est")
    print("envoyée, le module n'est pas modifié.")
    print()

    trouvailles = []
    vitesse = None
    repondu = False

    for attempt in diagnostic.sweep(args.port, address=args.address):
        if attempt.baud != vitesse:
            if vitesse is not None and not repondu:
                print("  rien")
            vitesse = attempt.baud
            repondu = False
            print(f"{attempt.baud} bauds")

        if attempt.command is None:
            print(f"  port inutilisable : {attempt.error}")
            return

        if attempt.response:
            print(format_attempt(attempt))
            trouvailles.append(attempt)
            repondu = True

    if vitesse is not None and not repondu:
        print("  rien")

    print()

    if trouvailles:
        print("Le module répond. À reprendre :")
        print(f"  {suggest_command(args.port, trouvailles)}")

        if not any(a.slot is not None and diagnostic.accepted(a)
                   for a in trouvailles):
            print()
            print("Aucun slot n'a rendu d'état : le module répond, mais pas de")
            print("5050 là où on le cherche. Vérifier son emplacement.")
        return

    print("Aucune réponse, quelle que soit la vitesse.")

    if not args.scan_addresses:
        print("Reste l'adresse : relancer avec --scan-addresses "
              f"(256 essais à {args.baud} bauds, environ deux minutes).")
        print("Sinon, chercher du côté du câblage : RS-232 contre RS-485,")
        print("RX et TX croisés, masse commune, INIT* relié à GND.")
        return

    print(f"Recherche de l'adresse à {args.baud} bauds…")
    for attempt in diagnostic.sweep_addresses(args.port, args.baud):
        if attempt.command is None:
            print(f"  port inutilisable : {attempt.error}")
            return
        if attempt.response:
            print(f"  adresse {attempt.address} -> {attempt.response!r}")
            trouvailles.append(attempt)

    if not trouvailles:
        print("  aucune adresse ne répond.")

def display_io16(measurement, monitor):
    """Redessine la vue des 16 voies : rouge pour 0, vert pour 1."""
    screen = sys.stdout.isatty()
    word = sum(state << channel for channel, state in enumerate(measurement.values))

    if screen:
        print(CLEAR_SCREEN, end="")

    etat = "activé" if monitor.checksum else "désactivé"
    print("ADAM-5050 — 16 entrées/sorties")
    print(f"Port : {monitor.port} | {monitor.baud} bauds | adresse {monitor.address}"
          f" | slot {monitor.slot} | checksum {etat}")
    print(f"Mot d'état : 0x{word:04X} | rafraîchissement {monitor.interval:g} s")
    line = "Dernière lecture : " + measurement.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    if measurement.rejected:
        line += f" | trames rejetées avant celle-ci : {measurement.rejected}"
    print(line)
    print("Aucune sortie n'est commandée : les états sont seulement lus.")
    print("Arrêt avec Ctrl+C.")
    print()

    for first in range(0, IO_CHANNELS, 4):
        cells = []
        for channel in range(first, first + 4):
            state = measurement.values[channel]
            cell = f"E/S {channel:02d} : {state}"
            cells.append((GREEN if state else RED) + cell + RESET if screen else cell)
        print("    ".join(cells))

    sys.stdout.flush()

def print_header(monitor):
    etat = "activé" if monitor.checksum else "désactivé"
    print(f"Port : {monitor.port}")
    print(f"{monitor.baud} bauds, 8N1, checksum {etat}")
    print(f"Adresse : {monitor.address}, slot : {monitor.slot}")
    print(f"Décodage strict : {monitor.channels} voies x {monitor.width} caractères")
    print(f"Lecture toutes les {monitor.interval:.2f} s.")
    print(f"Nouvelle tentative après {monitor.retry_delay:.2f} s en cas d'erreur.")
    print("Arrêt avec Ctrl+C.")
    print()

def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyS0")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD,
                        choices=sorted(BAUDRATES),
                        help="vitesse de la liaison (défaut : %(default)s)")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--retry-delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--address", default=DEFAULT_ADDRESS,
                        help="adresse du module interrogé (défaut : %(default)s)")
    parser.add_argument("--slot", type=int, default=DEFAULT_SLOT,
                        help=f"slot occupé sur le fond de panier "
                             f"(0 à {IO_SLOTS - 1}, défaut : %(default)s)")
    parser.add_argument("--5050", dest="io_5050", action="store_true",
                        help="lire les 16 voies tout ou rien d'un ADAM-5050 "
                             "au lieu des voies analogiques")
    parser.add_argument("--no-checksum", action="store_true",
                        help="le module n'utilise pas la checksum")
    parser.add_argument("--enable-checksum", action="store_true",
                        help="activer la checksum du module, puis quitter")
    parser.add_argument("--config-command", default=protocol.ENABLE_CHECKSUM,
                        help="trame d'activation envoyée (défaut : %(default)s)")
    parser.add_argument("--channels", type=int, default=EXPECTED_CHANNELS,
                        help="nombre de voies attendues (défaut : %(default)s)")
    parser.add_argument("--width", type=int, default=EXPECTED_WIDTH,
                        help="largeur d'un champ en caractères (défaut : %(default)s)")
    parser.add_argument("--scan", action="store_true",
                        help="chercher les réglages du module en balayant vitesse "
                             "et checksum, puis quitter (lecture seule)")
    parser.add_argument("--scan-addresses", action="store_true",
                        help="avec --scan, poursuivre par les 256 adresses "
                             "possibles si rien n'a répondu")
    parser.add_argument("--raw", action="store_true",
                        help="afficher la trame brute d'une seule lecture, puis quitter "
                             "(suit --5050)")
    return parser.parse_args(argv)

def show_raw(args):
    """Lit une trame et la montre telle quelle, sans rien supposer du format."""
    checksum = not args.no_checksum

    if args.io_5050:
        command = protocol.digital_read_command(args.address, args.slot)
        ack = protocol.CONFIG_ACK
    else:
        command = protocol.read_command(args.address, args.slot)
        ack = protocol.ACK

    response = configuration.send_once(
        args.port, command,
        checksum=checksum,
        response_timeout=args.timeout,
        baud=args.baud,
    )

    print(f"Requête  : {protocol.build_frame(command, checksum)!r}")
    print(f"Réponse  : {response!r}")
    print(f"Longueur : {len(response)} caractères, terminateur exclu")

    payload = protocol.verify_frame(response, checksum, ack=ack)
    print(f"Charge utile : {len(payload)} caractères")
    print()

    if args.io_5050:
        states = parse_5050(payload, args.address)
        word = sum(state << channel for channel, state in enumerate(states))
        print(f"Mot d'état : 0x{word:04X}")
        print("États : " + " ".join(f"{channel:02d}={state}"
                                    for channel, state in enumerate(states)))
        return

    print("Découpages possibles :")

    for channels, width, fields in possible_layouts(payload):
        repete = " (mêmes valeurs répétées)" if len(set(fields)) < channels else ""
        print(f"  {channels} voies x {width} : "
              + " | ".join(str(int(f)) if f.isdigit() else repr(f) for f in fields)
              + repete)

def enable_checksum(args):
    """Envoie la trame de configuration, sans checksum, et rend compte."""
    print(f"Port : {args.port}")
    print(f"Commande envoyée : {args.config_command}")
    print("Envoyée sans checksum : le module n'en attend pas encore.")
    print()

    response = configuration.enable_checksum(
        args.port, args.config_command, response_timeout=args.timeout,
        baud=args.baud,
    )

    print(f"Réponse du module : {response!r}")
    print("Checksum activée. Relancer la lecture sans --no-checksum.")

def monitor_loop(args):
    monitor = Monitor(
        args.port,
        interval=args.interval,
        retries=args.retries,
        retry_delay=args.retry_delay,
        response_timeout=args.timeout,
        address=args.address,
        slot=args.slot,
        checksum=not args.no_checksum,
        channels=args.channels,
        width=args.width,
        baud=args.baud,
    )

    try:
        with monitor:
            print_header(monitor)

            for event in monitor.run():
                if isinstance(event, Measurement):
                    print(format_measurement(event, monitor.checksum, monitor.width))
                else:
                    print(format_failure(event))
                    if monitor.last_frame:
                        print(f"  dernière trame reçue : {monitor.last_frame!r}")

    except KeyboardInterrupt:
        print()
        print("Lecture arrêtée.")
        print(f"Nombre total de trames rejetées : {monitor.rejected_total}")

def monitor_5050_loop(args):
    monitor = Monitor5050(
        args.port,
        interval=args.interval,
        retries=args.retries,
        retry_delay=args.retry_delay,
        response_timeout=args.timeout,
        address=args.address,
        slot=args.slot,
        checksum=not args.no_checksum,
        baud=args.baud,
    )

    try:
        with monitor:
            for event in monitor.run():
                if isinstance(event, Measurement):
                    display_io16(event, monitor)
                else:
                    print(format_failure(event))
                    if monitor.last_frame:
                        print(f"  dernière trame reçue : {monitor.last_frame!r}")

    except KeyboardInterrupt:
        print()
        print("Lecture arrêtée.")
        print(f"Nombre total de trames rejetées : {monitor.rejected_total}")

def main(argv=None):
    args = parse_args(argv)

    try:
        # Le balayage passe devant : c'est le recours quand plus rien ne
        # répond, et il ne touche pas au module.
        if args.scan:
            run_scan(args)
        elif args.enable_checksum:
            enable_checksum(args)
        elif args.raw:
            show_raw(args)
        elif args.io_5050:
            monitor_5050_loop(args)
        else:
            monitor_loop(args)

    except Exception as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    return 0
