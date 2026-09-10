# 4. `protocol.py` — l'enveloppe des trames

Fichier : [serie/dcon/protocol.py](../serie/dcon/protocol.py) — 57 lignes.

**Rôle :** habiller une commande déjà écrite (checksum, terminateur) et
vérifier une réponse déjà reçue (checksum, accusé). Ce fichier ne fait
**aucune entrée/sortie** : il ne manipule que des chaînes de caractères. On
peut donc l'essayer entièrement sans matériel branché.

Il ne sait en revanche **rien de la forme d'une requête** : ni le préfixe
(`#`, `$`, `%`…), ni l'adresse, ni le slot. Cette partie-là — « comment on
pose la question » — appartient à la famille de matériel et vit dans le
paquet `familles` (voir [13-familles.md](13-familles.md)) ; `protocol.py` se
contente de dresser et de contrôler la chaîne qu'on lui donne, quelle que
soit sa forme.

## L'enveloppe DCON en deux lignes

Le protocole ASCII Advantech/DCON est lisible à l'œil nu. Une trame est une
courte chaîne terminée par un retour chariot `\r` (code 13) :

```
Requête  : <corps>[<checksum>]<CR>
Réponse  : <accusé><charge utile>[<checksum>]<CR>
```

Le premier caractère de la réponse est l'**accusé** : `>` pour une lecture de
valeurs, `!` pour un état ou une configuration acceptée, `?` = compris mais
refusé. Un `?` n'est donc pas un échec de communication : c'est la preuve que
le module t'entend. C'est une information précieuse au diagnostic.

Exemples concrets (le contenu du `<corps>` vient du paquet `familles`, voir
[13-familles.md](13-familles.md)) :

```
#01S0[07]<CR>         requête de lecture analogique, avec sa checksum
>+000123[8F]<CR>      réponse acceptée
$01S06[40]<CR>        requête de lecture tout ou rien
!01FF00[..]<CR>       réponse acceptée, accusée par '!'
?01<CR>                refus, quelle que soit la requête posée
```

## Les constantes

```python
TERMINATOR = "\r"
ACK = ">"                    # accusé d'une lecture de valeurs
CONFIG_ACK = "!"             # accusé d'un état ET d'une configuration acceptée
DEFAULT_ADDRESS = "01"       # adresse d'usine d'un module neuf
```

`DEFAULT_ADDRESS` reste ici bien qu'il ne serve qu'à composer des requêtes
(dans `familles.py` et `settings.py`) : c'est une valeur d'usine du
matériel DCON en général, pas une particularité de l'ADAM-5000.

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
