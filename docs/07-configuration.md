# 7. `configuration.py` — les commandes ponctuelles

Fichier : [serie/dcon/configuration.py](../serie/dcon/configuration.py) — 27 lignes.

**Rôle :** envoyer une seule trame, lire une seule réponse. Pas de boucle, pas
de réessai, pas de statistiques.

C'est le plus court fichier du paquet, et son existence séparée est un choix
délibéré : mélanger « une commande unique » et « une boucle de surveillance »
dans le même fichier obligerait à traîner des compteurs et des réessais qui
n'ont aucun sens pour une commande de configuration.

## `send_once(port, command, checksum=False, response_timeout=2.0, baud=DEFAULT_BAUD)`

```python
with SerialPort(port, baud) as serial:
    serial.write(protocol.build_frame(command, checksum))
    return serial.read_frame(response_timeout)
```

Trois lignes qui font tout : ouvrir, envoyer, lire, fermer. Le `with` garantit
la fermeture du port même si `read_frame()` lève un `TimeoutError`.

La réponse est rendue **brute** (terminateur retiré, mais rien d'autre) : ni
vérification d'accusé, ni découpage. C'est à l'appelant d'interpréter.

Malgré son nom de fichier, cette fonction n'est pas réservée à la configuration :
`cli.show_raw()` (`--raw`) s'en sert aussi pour faire une lecture unique.

**Noter le défaut `checksum=False`**, à l'inverse du reste du paquet. Explication
juste en dessous.

## `enable_checksum(port, command=familles.ENABLE_CHECKSUM, response_timeout=2.0, baud=DEFAULT_BAUD)`

```python
response = send_once(port, command, checksum=False,
                     response_timeout=response_timeout, baud=baud)

if not response.startswith(protocol.CONFIG_ACK):
    raise ValueError(f"Commande refusée par le module : {response!r}")

return response
```

Active la somme de contrôle du module, et rend sa réponse (`!01` si acceptée).

### Le point à bien comprendre : envoyée *sans* checksum

C'est contre-intuitif et c'est écrit en toutes lettres dans la docstring du
fichier. La logique :

- On active la checksum **parce que le module ne l'utilise pas encore**.
- Un module sans checksum **ignore purement et simplement** une trame qui en
  porte une (voir le tableau dans [04-protocol.md](04-protocol.md)).
- Donc envoyer `%01000840` avec sa somme reviendrait à parler dans le vide : la
  commande d'activation ne serait jamais reçue.

D'où `checksum=False` codé en dur, sans possibilité de le changer. Une fois la
commande passée, il faut relancer la lecture **sans** `--no-checksum` : le
module attend désormais des sommes.

### Le contrôle de la réponse

`startswith(CONFIG_ACK)` c'est-à-dire `startswith("!")`. Une réponse `?01`
signifie « compris, refusé » — souvent parce que la broche `INIT*` doit être
reliée à la masse pour autoriser une reconfiguration sur certains modèles. La
`ValueError` contient la réponse brute, ce qui permet de faire la différence
entre un refus (`'?01'`) et un `TimeoutError` (silence complet).

## Effets de bord à connaître

La trame par défaut `%01000840` fait **deux** choses, pas une :

1. elle active la somme de contrôle (`FF = 40`, bit 6) ;
2. elle règle le module à **38400 bauds** (`CC = 08`).

Donc après une activation réussie, si tu parlais à 9600 bauds, le module ne
t'entend plus à 9600 : il faut repasser à 38400. Le lanceur `lancer_adam.sh`
prévient l'utilisateur avant de confirmer. Pour ne changer que la checksum,
il faut composer une autre trame avec la documentation du module et la passer
par `--config-command`.

## La seule fonction du paquet qui modifie le matériel

Tout le reste du dépôt est en lecture seule. Ce fichier est la **seule**
exception, et c'est pour cela que :

- il est isolé dans son propre fichier ;
- `cli.main()` le place derrière une option explicite (`--enable-checksum`) ;
- `lancer_adam.sh` demande une confirmation `[o/N]` avant de l'appeler ;
- `diagnostic.py` ne l'utilise jamais et ne fabrique aucune trame `%`.

Garde cette propriété si tu ajoutes du code : une commande qui **écrit** dans le
module a sa place ici, pas ailleurs.
