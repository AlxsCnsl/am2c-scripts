# 8. `diagnostic.py` — le balayage quand rien ne répond

Fichier : [serie/dcon/diagnostic.py](../serie/dcon/diagnostic.py) — 124 lignes.

**Rôle :** trouver les réglages du module quand il reste muet. **En lecture
seule** : uniquement des interrogations, jamais de commande de configuration.

## Le problème que ce fichier résout

Un module qui ne renvoie **aucun** octet ne dit pas pourquoi. Il faut que trois
réglages concordent avant qu'un seul caractère revienne :

- la **vitesse** (9600 ? 38400 ? autre chose ?) ;
- l'**état de la checksum** (le module en attend-il une ?) ;
- l'**adresse** (l'usine met 01, mais quelqu'un a pu la changer).

Un désaccord sur n'importe lequel des trois produit exactement le même
symptôme : le silence. Impossible de deviner lequel est en cause — d'où le
balayage systématique.

Et un point de vocabulaire essentiel : **un module qui répond `?01` n'est pas
muet**. Il a compris la requête et l'a refusée. C'est déjà la preuve que la
liaison fonctionne, et le balayage le rapporte comme une trouvaille.

## Les constantes

```python
SCAN_BAUDS = (9600, 38400, 19200, 57600, 115200, 4800, 2400, 1200)
MIN_TIMEOUT = 0.3
LONGEST_FRAME = 64
ADDRESS_TIMEOUT = 0.15
```

`SCAN_BAUDS` est ordonné **par vraisemblance**, pas par valeur : 9600 est la
valeur d'usine la plus répandue, 38400 celle que ce dépôt a longtemps supposée.
Le but est de tomber juste vite.

## `probe_timeout(baud)`

```python
return max(MIN_TIMEOUT, LONGEST_FRAME * 10 / baud)
```

Combien de temps attendre une réponse, selon la vitesse. Le calcul :

- une trame fait au plus 64 caractères ;
- chaque caractère prend **10 bits** sur le fil (1 bit de départ + 8 de données
  + 1 d'arrêt — c'est le « 8N1 ») ;
- donc `64 × 10 / baud` secondes de transmission pure.

À 1200 bauds ça fait 0,53 s ; à 115200 bauds, 0,006 s. Le `max()` impose un
plancher de 0,3 s pour laisser au module le temps de *réfléchir*, pas seulement
de transmettre. Attendre 2 s à chaque essai rendrait le balayage interminable ;
attendre 0,05 s à 1200 bauds couperait des réponses valides.

## `probes(address, slots=4)`

```python
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
```

La liste des interrogations, **de la plus générale à la plus précise**. On
commence par « qui es-tu ? » (`$aaM`), qui marche sur n'importe quel ADAM et ne
dépend d'aucun slot ; on finit par les lectures de slot, qui ne répondent que si
le bon module est au bon endroit.

Chaque entrée est un triplet `(commande, libellé lisible, slot ou None)`. Le
libellé sert à l'affichage, le slot sert à `cli.suggest_command()` pour
construire la ligne de commande à relancer.

**Aucune de ces commandes ne modifie le module** : ce sont toutes des
interrogations. Aucune trame `%` n'est jamais fabriquée dans ce fichier.

## `attempt(serial, baud, checksum, address, command, label, response_timeout, slot=None)`

```python
try:
    serial.flush_input()
    serial.write(protocol.build_frame(command, checksum))
    response = serial.read_frame(response_timeout)
except (TimeoutError, ValueError, OSError) as exc:
    return Attempt(baud, checksum, address, slot, command, label, None, exc)
return Attempt(baud, checksum, address, slot, command, label, response, None)
```

Un essai unique. Le `flush_input()` est ici indispensable — contrairement à la
boucle de mesure : entre deux essais du balayage, ce qui traîne dans le tampon
est la réponse tardive de l'essai **précédent**, et la prendre pour la réponse de
l'essai en cours donnerait un résultat faux.

Une exception n'est jamais propagée : elle est rangée dans le champ `error` de
l'`Attempt`. Le balayage doit continuer même si un essai échoue — c'est
justement le cas normal, la plupart des essais échouent.

## `accepted(attempt)`

```python
return bool(attempt.response) and not attempt.response.startswith("?")
```

Vrai si le module a répondu **autre chose qu'un refus**. Trois états possibles
pour un essai, et cette fonction sépare le troisième :

| Réponse | `accepted()` | Interprétation |
|---|---|---|
| `None` | `False` | silence : la liaison ne passe pas |
| `'?01'` | `False` | refus : la liaison passe, la requête ne convient pas |
| `'!0000'` | `True` | accepté : les réglages sont bons |

`cli.py` affiche quand même les refus, avec la mention « (refus, mais le module
entend) ».

## `sweep(port, address="01", bauds=SCAN_BAUDS, checksums=(False, True), slots=4)`

Trois boucles imbriquées : **vitesse × état du checksum × interrogation**. Avec
les valeurs par défaut : 8 vitesses × 2 états × 8 interrogations = 128 essais.

```python
for baud in bauds:
    if baud not in BAUDRATES:
        continue
    timeout = probe_timeout(baud)
    try:
        serial = SerialPort(port, baud).open()
    except (OSError, ValueError) as exc:
        yield Attempt(baud, None, address, None, None, "ouverture du port", None, exc)
        continue
    try:
        for checksum in checksums:
            for command, label, slot in probes(address, slots):
                yield attempt(serial, baud, checksum, address, command, label, timeout, slot)
    finally:
        serial.close()
    time.sleep(0.05)
```

Points de conception :

- **C'est un générateur.** Les résultats sortent au fil de l'eau, donc l'affichage
  avance pendant le balayage au lieu d'attendre la fin. Sur une minute de
  balayage, ça change tout pour l'utilisateur.
- **Le port est rouvert à chaque vitesse.** C'est le seul moyen fiable de changer
  de vitesse sur certains convertisseurs.
- **`try/finally`** garantit la fermeture du port même si l'appelant abandonne le
  générateur (`break`, `Ctrl+C`).
- **`time.sleep(0.05)`** laisse le convertisseur USB « retomber » entre deux
  vitesses — sans cette pause, certains modèles gardent l'ancienne configuration
  quelques millisecondes et les premiers essais de la vitesse suivante sont
  faussés.
- L'échec d'ouverture est signalé par un `Attempt` dont **`command` vaut `None`** :
  c'est le signal conventionnel « ce n'est pas le module qui ne répond pas, c'est
  le port qui ne s'ouvre pas ». `cli.run_scan()` teste exactement cela pour
  arrêter tout de suite avec un message de permission.

## `sweep_addresses(port, baud, checksums=(False, True))`

Le recours ultime : essayer les 256 adresses possibles.

```python
for value in range(256):
    address = f"{value:02X}"
    command = f"${address}M"
    for checksum in checksums:
        yield attempt(serial, baud, checksum, address, command, "nom du module", ADDRESS_TIMEOUT)
```

`f"{value:02X}"` donne `00`, `01`, … `FF` (hexadécimal, deux chiffres, majuscules).

Deux compromis assumés, expliqués par la docstring :

- **Une seule vitesse.** Le produit des deux balayages ferait 8 × 256 × 2 = 4096
  essais, soit une éternité. On fixe la vitesse (celle de `--baud`) et on ne fait
  varier que l'adresse.
- **Un délai plus court** (`ADDRESS_TIMEOUT = 0.15 s`). Même ainsi :
  256 × 2 × 0,15 ≈ 77 secondes, d'où le « environ deux minutes » annoncé par
  `cli.py` et par `lancer_diagnostic.sh`.

Une seule interrogation par adresse (`$aaM`, « nom du module ») : c'est la plus
universelle, celle à laquelle tout ADAM répond quel que soit son équipement.

## Comment on s'en sert

```sh
sh serie/lancer_diagnostic.sh                          # interactif
python3 -m dcon --port /dev/ttyUSB0 --scan        # direct
python3 -m dcon --port /dev/ttyUSB0 --scan --scan-addresses
```

Si le balayage complet reste muet de bout en bout, la cause n'est plus dans les
réglages logiciels mais dans le **câblage** : RS-232 contre RS-485, RX et TX
croisés, masse commune absente, châssis non alimenté, ou `INIT*` non relié à
GND selon le modèle. C'est ce que `cli.run_scan()` affiche en conclusion.
