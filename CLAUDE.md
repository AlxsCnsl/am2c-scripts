# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A collection of standalone operational shell scripts plus one self-contained Python package
(`ADAM/adam5000`) for reading Advantech ADAM-5000 I/O modules over a serial link. There is no
build system, package manifest, or test suite — everything is meant to be run directly. Scripts
and comments are in French; keep new comments/output in French to match.

## Running things

- `python3 -m adam5000 ...` — must always be run with `-m` from inside `ADAM/`. Running
  `python3 adam5000/__main__.py` or `python3 adam5000/` breaks relative imports
  ("attempted relative import with no known parent package").
- `sh ADAM/lancer_adam.sh` — interactive launcher (analog read loop, ADAM-5050 digital I/O view,
  or checksum activation). Sources `choisir_port.sh` for port/permission selection.
- `sh ADAM/lancer_diagnostic.sh` — interactive read-only diagnostic sweep, for when a module
  stays silent. Wraps `python3 -m adam5000 --scan [--scan-addresses]`.
- `./lancer-adam.sh` (repo root) — convenience wrapper that just execs `ADAM/lancer_adam.sh`.
- `./fenix-usb-crochetage.sh <minutes>` — temporarily unblocks USB mass storage
  (`/etc/modprobe.d/usb-storage.conf`), then re-blocks it after a delay. Needs root.
- `./start-gamatrack.sh` / `./stop-gamatrack.sh` — start/stop the Docker daemon (and thus the
  Gamatrack containers, which restart automatically via Docker's restart policy).
- No test suite, linter, or formatter is configured anywhere in the repo.

Useful CLI flags for `adam5000` (see `ADAM/adam5000/cli.py`): `--port`, `--baud`, `--interval`,
`--retries`, `--retry-delay`, `--timeout`, `--address`, `--slot`, `--5050`, `--no-checksum`,
`--enable-checksum`, `--config-command`, `--scan`, `--scan-addresses`, `--raw`.

## adam5000 package architecture

Layered, with each layer independent of the others — this is the key design invariant to
preserve when changing code:

1. **`serial_port.py`** — raw transport. Opens the tty via `termios`/`fcntl` in raw 8N1 mode
   (no `pyserial` dependency). Forces DTR/RTS for converters that need it; drops `HUPCL` so DTR
   doesn't fall on close. `read_frame()` accumulates bytes until `\r`.
2. **`protocol.py`** — Advantech ASCII frame grammar, independent of which I/O module is
   attached. Analog read is `#<addr>S<slot>` acked with `>`; digital (ADAM-5050) read is
   `$<addr>S<slot>6` acked with `!` (see `verify_frame(..., ack=...)`); config commands are
   `%<fields>` acked with `!<addr>`. Checksum is optional on the device and must be tracked
   correctly on both ends — a checksummed request to a module without checksum enabled gets no
   response at all, and the reverse breaks decoding.
3. **`modules.py`** — payload decoding, one function per I/O module. `parse_5081` splits fixed
   width numeric fields for analog channels; `parse_5050` decodes a 4-hex-digit bitmask (channel
   0 = LSB) for the 16-point digital module. Adding support for another module (5017, 5018, …)
   only touches this file (plus a new request builder in `protocol.py` if its grammar differs).
4. **`monitor.py`** — read loop with retries/statistics, module-agnostic (`Monitor`) plus a
   `Monitor5050` subclass overriding `request()`/`decode()` for the digital grammar. Yields
   `Measurement` or `Failure` namedtuples; does no printing.
5. **`configuration.py`** — one-shot commands only (e.g. `enable_checksum`), no loop, no retries.
   Deliberately sent *without* checksum since it targets a module that doesn't expect one yet.
6. **`diagnostic.py`** — read-only sweep across baud rate × checksum state × probe command, used
   when a module produces no response at all. Never sends a `%` config frame, so it cannot alter
   module state. `cli.py` formats its `Attempt` results and suggests a ready-to-run command line.
7. **`cli.py`** — argument parsing and all display/formatting. Dispatch order in `main()`
   matters: `--scan` is checked before `--enable-checksum`/`--raw`/`--5050`, since the scan is the
   fallback when nothing else works and must never be shadowed.

The ADAM-5050 module is read-only in this codebase by design — no output/relay is ever
commanded, only the input/output state image, to avoid any accidental actuation.

`ADAM/README.md` (in French) has more protocol detail, worked examples, and wiring
troubleshooting notes (RS-232 vs RS-485, INIT* to GND, etc.) — read it before touching
`protocol.py` or `serial_port.py`.
