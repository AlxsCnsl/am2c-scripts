# 11. Glossaire

Les termes du dépôt, dans l'ordre alphabétique.

**8N1** — Le format d'un caractère sur la ligne : 8 bits de données, aucune
parité (N pour *none*), 1 bit d'arrêt. Avec le bit de départ, un caractère
occupe donc **10 bits** sur le fil — c'est le calcul de
`diagnostic.probe_timeout()`. Réglage universel des modules ADAM.

**Accusé (ACK)** — Le premier caractère de la réponse : `>` pour une lecture
analogique, `!` pour une lecture 5050 ou une configuration acceptée, `?` pour un
refus. Vérifié par `protocol.verify_frame()`.

**Adresse (de station)** — Deux chiffres hexadécimaux identifiant un module sur
le bus, `01` en sortie d'usine. Plusieurs modules peuvent partager le même câble
RS-485 ; l'adresse dit à qui l'on parle. Option `--address`.

**Baud** — Nombre de symboles par seconde sur la ligne ; ici, pratiquement, le
nombre de bits par seconde. Attention : `termios.B9600` n'est pas
nécessairement le nombre 9600 — c'est un code interne du noyau, qui vaut `13`
sur bien des systèmes même s'il coïncide avec la vitesse sur cette machine.
D'où la table `BAUDRATES`, qui rend la traduction explicite et portable.

**Charge utile (*payload*)** — Ce qui reste d'une réponse une fois l'accusé et
la somme de contrôle retirés. C'est ce que `protocol.verify_frame()` rend et ce
que `modules.parse_*()` décode.

**Checksum / somme de contrôle** — Deux caractères hexadécimaux ajoutés en fin
de trame, égaux à la somme des codes ASCII du reste modulo 256. Optionnelle sur
le module ; **si les deux côtés ne sont pas d'accord, la trame est ignorée sans
message d'erreur** — le symptôme est un silence total. Voir
[04-protocol.md](04-protocol.md).

**DTR / RTS** — Deux lignes de contrôle du port série (*Data Terminal Ready*,
*Request To Send*), héritées de l'époque des modems. Beaucoup de convertisseurs
USB-série n'émettent pas si elles ne sont pas levées, d'où
`SerialPort.raise_dtr_rts()`.

**Fond de panier (*backplane*)** — Le châssis ADAM-5000 dans lequel s'enfichent
les modules d'E/S. Il compte ici 4 emplacements, numérotés 0 à 3
(`modules.IO_SLOTS`).

**Générateur** — Fonction Python contenant un `yield` : elle rend une valeur et
se met en pause, puis reprend là où elle s'était arrêtée. `Monitor.run()` et
`diagnostic.sweep()` en sont ; c'est ce qui permet à l'affichage d'avancer au fil
de l'eau sans que ces fonctions n'affichent quoi que ce soit.

**Gestionnaire de contexte** — Un objet utilisable avec `with`, grâce à ses
méthodes `__enter__` et `__exit__`. `SerialPort` et `Monitor` en sont : le port
est fermé quoi qu'il arrive, exception ou `Ctrl+C` compris.

**`ioctl`** — « *input/output control* » : appel système fourre-tout pour
piloter un périphérique au-delà de lire/écrire. Utilisé une seule fois ici, pour
lever DTR et RTS.

**`INIT*`** — Broche présente sur certains modules ADAM. Reliée à la masse
(GND), elle force le module dans un état de configuration connu (souvent 9600
bauds, adresse `00`) et autorise sa reconfiguration. L'étoile signale une
logique inversée : actif à l'état bas. À vérifier quand une commande `%` est
refusée par un `?`.

**Mode *raw*** — Mode d'un port série où le noyau ne transforme rien : pas
d'écho, pas de traduction `\r`→`\n`, pas d'attente d'une ligne entière. Le
contraire du mode *canonique* d'un terminal. Obtenu ici en mettant `iflag`,
`oflag` et `lflag` à zéro.

**`namedtuple`** — Tuple dont les champs portent un nom, donc lisible
(`m.timestamp`) et immuable. Trois dans le paquet : `Measurement`, `Failure`,
`Attempt`.

**RS-232 / RS-485** — Deux normes électriques différentes, **incompatibles entre
elles**. RS-232 relie deux appareils en point à point ; RS-485 relie plusieurs
appareils sur une paire de fils, en semi-duplex (on parle chacun son tour). Un
module câblé en RS-485 sur un port RS-232 reste parfaitement muet, sans qu'aucun
réglage logiciel n'y change rien — c'est la conclusion de `--scan` quand il ne
trouve rien.

**Slot / emplacement** — La position d'un module dans le fond de panier, de 0 à
3. Option `--slot`. Ce n'est pas l'adresse : l'adresse désigne le châssis,
le slot désigne la carte à l'intérieur.

**Terminateur** — Le `\r` (retour chariot, code 13) qui clôt chaque trame.
`SerialPort.read_frame()` accumule les octets jusqu'à lui et ne le rend pas à
l'appelant.

**`termios`** — L'interface POSIX de configuration des terminaux et ports série.
La liste de 7 éléments qu'elle manipule est détaillée dans
[03-serial_port.md](03-serial_port.md).

**Tout ou rien (TOR)** — Se dit d'une entrée/sortie qui ne prend que deux états,
0 ou 1 (contact ouvert/fermé, relais actif/inactif). Par opposition à
*analogique*, qui prend une valeur dans une plage continue. L'ADAM-5050 est un
module tout ou rien à 16 voies, l'ADAM-5081 un module analogique.

**Trame** — Un message complet : accusé ou préfixe, charge utile, somme
éventuelle, terminateur. Par exemple `#01S007\r` en requête, `>0000123456…\r` en
réponse.

**Voie (*channel*)** — Une entrée ou une sortie individuelle du module. Numérotée
à partir de 0. Sur le 5050, la voie 0 est le **bit de poids faible** du mot
d'état.
