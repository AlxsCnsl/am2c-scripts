# Documentation du paquet `adam5000`

Documentation de lecture destinée à quelqu'un qui découvre le dépôt : elle
explique **ce que fait chaque fichier, chaque fonction, et pourquoi**. Aucune
connaissance préalable de la liaison série ou du protocole Advantech n'est
supposée — le [glossaire](11-glossaire.md) définit les termes au fur et à
mesure.

## Par où commencer

| Ordre | Fichier | Ce qu'on y apprend |
|---|---|---|
| 1 | [01-environnement.md](01-environnement.md) | Ce qui est installé, ce qui ne l'est pas, comment lancer le programme |
| 2 | [02-architecture.md](02-architecture.md) | Les 7 fichiers, leurs dépendances, le trajet d'une mesure |
| 3 | [03-serial_port.md](03-serial_port.md) | Couche 1 : ouvrir et lire un port série |
| 4 | [04-protocol.md](04-protocol.md) | Couche 2 : la grammaire des trames ASCII |
| 5 | [05-modules.md](05-modules.md) | Couche 3 : décoder les valeurs d'un module d'E/S |
| 6 | [06-monitor.md](06-monitor.md) | Couche 4 : la boucle de lecture et ses réessais |
| 7 | [07-configuration.md](07-configuration.md) | Couche 4 bis : les commandes ponctuelles |
| 8 | [08-diagnostic.md](08-diagnostic.md) | Couche 4 ter : le balayage quand rien ne répond |
| 9 | [09-cli.md](09-cli.md) | Couche 5 : les arguments et l'affichage |
| 10 | [10-relecture.md](10-relecture.md) | Relecture critique : anomalies trouvées et corrections proposées |
| 11 | [11-glossaire.md](11-glossaire.md) | Vocabulaire : baud, trame, checksum, slot, DTR… |
| 12 | [12-settings.md](12-settings.md) | Décrire le rack dans un fichier JSON, lu par `--config` |

## En une phrase

Le programme envoie une petite chaîne de caractères ASCII (par exemple
`#01S0`) sur un câble série vers un automate Advantech ADAM-5000, lit la
chaîne renvoyée en réponse, vérifie qu'elle est intacte, la découpe en valeurs
de voies, et l'affiche — en boucle.

## Rappel important

Le paquet se lance **toujours** avec `-m`, depuis le dossier `ADAM/` :

```sh
cd ADAM
python3 -m adam5000 --port /dev/ttyUSB0
```

`python3 adam5000/__main__.py` échoue (« attempted relative import with no
known parent package »), voir [01-environnement.md](01-environnement.md).
