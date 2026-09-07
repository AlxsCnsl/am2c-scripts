# 4. `protocol.py` — la grammaire des trames

Fichier : [ADAM/adam5000/protocol.py](../ADAM/adam5000/protocol.py) — 75 lignes.

**Rôle :** fabriquer les chaînes à envoyer, et vérifier celles qui reviennent.
Ce fichier ne fait **aucune entrée/sortie** : il ne manipule que des chaînes de
caractères. On peut donc l'essayer entièrement sans matériel branché.

## Le protocole ADAM en cinq lignes

Advantech utilise un protocole ASCII lisible à l'œil nu. Une trame est une
courte chaîne terminée par un retour chariot `\r` (code 13).

```
Requête analogique  : #<adresse>S<slot>[<checksum>]<CR>
Réponse             : ><charge utile>[<checksum>]<CR>
Requête tout ou rien: $<adresse>S<slot>6[<checksum>]<CR>
Réponse             : !<charge utile>[<checksum>]<CR>
Configuration       : %<champs>[<checksum>]<CR>
Réponse             : !<adresse>[<checksum>]<CR>
Refus (n'importe quand) : ?<adresse><CR>
```

Le premier caractère de la réponse est l'**accusé** : `>` ou `!` = accepté,
`?` = compris mais refusé. Un `?` n'est donc pas un échec de communication :
c'est la preuve que le module t'entend. C'est une information précieuse au
diagnostic.

## Les constantes

```python
TERMINATOR = "\r"
ACK = ">"                    # accusé d'une lecture analogique
CONFIG_ACK = "!"             # accusé d'une config ET d'une lecture 5050
DEFAULT_ADDRESS = "01"       # adresse d'usine d'un module neuf
ENABLE_CHECKSUM = "%01000840"
```

`ENABLE_CHECKSUM` se décompose selon la notation Advantech `%AANNCCFF` :

| Morceau | Valeur | Sens |
|---|---|---|
| `%` | | commande de configuration |
| `AA` | `01` | adresse actuelle du module |
| `NN` | `00` | nouvelle adresse (ici : champ suivant, laissé à 00) |
| `CC` | `08` | code de vitesse — `08` = **38400 bauds** |
| `FF` | `40` | format de données ; le bit 6 à 1 (0x40) active la checksum |

⚠️ **Cette trame reconfigure aussi la vitesse à 38400**, quelle que soit la
vitesse à laquelle tu parlais au module. Le lanceur `lancer_adam.sh` le dit
explicitement à l'utilisateur avant de confirmer. Ne recompose ces champs
qu'avec la documentation du module sous les yeux ; l'option `--config-command`
existe précisément pour envoyer une autre trame sans toucher au code.

## Les fonctions

### `checksum_ascii(text)`

```python
def checksum_ascii(text):
    return f"{sum(text.encode('ascii')) & 0xFF:02X}"
```

La somme de contrôle Advantech : on additionne les codes ASCII de tous les
caractères de la trame (terminateur exclu), on ne garde que l'octet de poids
faible (`& 0xFF`), et on l'écrit en deux caractères hexadécimaux majuscules
(`:02X`).

Exemple vérifié : `checksum_ascii("#01S0")` → `"07"`.
`35+48+49+83+48 = 263` ; `263 & 0xFF = 7` ; écrit sur deux chiffres : `07`.

C'est un contrôle d'intégrité faible (deux erreurs peuvent se compenser), mais
c'est ce que le matériel impose.

### `build_frame(command, checksum=True)`

```python
body = command.strip().upper()
return body + (checksum_ascii(body) if checksum else "") + TERMINATOR
```

Habille une commande : nettoyage, majuscules, somme éventuelle, terminateur.
`.upper()` est important — les ADAM attendent des majuscules (`$01S06`, pas
`$01s06`).

Noter que la somme est calculée **sur le corps déjà mis en majuscules**, donc
cohérente avec ce qui part réellement sur le fil.

### `read_command(address="01", slot=0)` → `#01S0`

Rend la commande **nue**, sans somme ni terminateur. Utile à deux endroits :
`diagnostic.probes()`, qui décide lui-même de l'habillage à essayer, et
`cli.show_raw()`, qui affiche la requête avant de l'envoyer.

### `build_command(address="01", slot=0, checksum=True)` → `#01S007\r`

Le raccourci : `build_frame(read_command(...))`. C'est ce qu'appelle
`Monitor.request()` à chaque cycle.

### `digital_read_command(address="01", slot=0)` → `$01S06`

La lecture d'un ADAM-5050. Deux différences avec la lecture analogique :
le préfixe `$` au lieu de `#`, et un `6` final imposé par la documentation
(c'est le code de la fonction « lire l'image des E/S »). Et sa réponse est
accusée par `!`, pas par `>` — d'où le paramètre `ack` de `verify_frame()`.

### `verify_frame(response, checksum=True, ack=ACK)`

Le contrôle à la réception. Trois étapes :

```python
body = response

if checksum:
    if len(response) < 4:
        raise ValueError("Réponse trop courte")
    received = response[-2:].upper()      # les 2 derniers caractères
    body = response[:-2]                  # tout sauf eux
    if received != checksum_ascii(body):
        raise ValueError("Checksum invalide")
elif len(response) < 2:
    raise ValueError("Réponse trop courte")

if not body.startswith(ack):
    raise ValueError(f"Préfixe '{ack}' absent : {body!r}")

return body[1:]                            # la charge utile, sans l'accusé
```

1. Si la somme est active : on la détache, on la recalcule sur le reste, on
   compare. Une différence = trame corrompue, on la rejette.
2. On vérifie l'accusé attendu. Une réponse `?01` échoue ici, avec un message
   qui contient la réponse brute (`{body!r}` — le `!r` affiche les guillemets
   et les caractères invisibles, indispensable pour déboguer une liaison série).
3. On rend la **charge utile** : tout sauf le caractère d'accusé.

Les deux erreurs sont des `ValueError`, ce que `Monitor.cycle()` attrape pour
réessayer.

## Le piège central de tout le dépôt : l'état de la checksum

La somme de contrôle est **optionnelle sur le module** et ce réglage vit dans
le matériel, pas dans le programme. Les deux côtés doivent être d'accord :

| Module | Programme | Résultat |
|---|---|---|
| sans checksum | sans checksum (`--no-checksum`) | ✅ tout marche |
| avec checksum | avec checksum (défaut) | ✅ tout marche |
| **sans** checksum | **avec** checksum | ❌ le module ignore la trame → **aucune réponse** |
| **avec** checksum | **sans** checksum | ❌ le module ignore la trame → **aucune réponse** |

Un désaccord ne donne pas un message d'erreur clair : il donne un **silence
total**, exactement comme un câble débranché. C'est pour cette raison que
`diagnostic.sweep()` essaie systématiquement les deux états, et que
l'argument `checksum` traverse toutes les couches du paquet.
