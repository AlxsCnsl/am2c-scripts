# 6. `monitor.py` — la boucle de lecture

Fichier : [ADAM/adam5000/monitor.py](../ADAM/adam5000/monitor.py) — 138 lignes.

**Rôle :** lire en boucle, réessayer quand ça échoue, compter les échecs.
**Et n'afficher strictement rien.** C'est la règle du fichier : il *produit*
des résultats, l'appelant décide quoi en faire.

## Les objets de résultat

```python
Measurement = namedtuple("Measurement", "timestamp values rejected")
Failure     = namedtuple("Failure", "attempts rejected_total last_error")
```

- `Measurement` : une lecture réussie. `values` est la liste des voies,
  `rejected` le nombre de trames rejetées **depuis la dernière réussite**
  (indicateur de qualité de la liaison : 0 = tout va bien).
- `Failure` : un cycle entièrement raté. `last_error` contient l'exception
  rencontrée à la dernière tentative, ce qui permet d'afficher *pourquoi*.

Un `namedtuple` s'utilise comme un tuple (`m[0]`) ou par nom (`m.timestamp`).
Il est **immuable** : une fois créé, on ne peut plus le modifier — pratique
pour un résultat qu'on ne veut pas voir altéré en cours de route.

## La classe `Monitor` (voies analogiques)

### `__init__(...)`

Beaucoup de paramètres, tous avec une valeur par défaut. Les trois catégories :

| Catégorie | Paramètres | Rôle |
|---|---|---|
| Liaison | `port`, `baud`, `response_timeout` | comment parler au module |
| Cadence | `interval`, `retries`, `retry_delay` | à quel rythme et avec quelle obstination |
| Module | `address`, `slot`, `checksum`, `channels`, `width` | à qui l'on parle et comment le décoder |

Les attributs d'état, initialisés à la fin :

```python
self.last_frame = None        # dernière trame brute reçue, pour le débogage
self.rejected_total = 0       # compteur cumulé sur toute la session
self.rejected_since_ok = 0    # compteur depuis la dernière lecture réussie
self.serial = None            # le SerialPort, créé seulement par open()
```

Comme pour `SerialPort`, **construire l'objet ne touche pas au matériel**.

### `open()` / `close()` / `__enter__` / `__exit__`

Même schéma que `SerialPort` : `open()` crée et ouvre le port, `close()` le
ferme si besoin, et les deux méthodes magiques permettent d'écrire :

```python
with monitor:
    for event in monitor.run():
        ...
# port fermé quoi qu'il arrive, y compris sur Ctrl+C
```

### `request()` et `decode()` — les deux méthodes à surcharger

```python
def request(self):
    return protocol.build_command(self.address, self.slot, self.checksum)

def decode(self, response):
    payload = protocol.verify_frame(response, self.checksum)
    return parse_5081(payload, self.channels, self.width)
```

Ce sont les **seuls** endroits où `Monitor` sait quel module est branché. Tout
le reste (réessais, statistiques, cadence) est indépendant du module. C'est le
patron de conception *méthode template* : la classe de base définit
l'enchaînement, les sous-classes remplissent les trous.

### `read_once()`

```python
self.last_frame = None
self.serial.write(self.request())
response = self.serial.read_frame(self.response_timeout)
self.last_frame = response
return self.decode(response)
```

Une requête, une réponse, un décodage. Deux détails importants :

- **Pas de `flush_input()` ici.** Le commentaire du code le souligne : dans une
  boucle, ce qui traîne dans le tampon est une réponse légitime, pas un résidu.
- **`last_frame` est conservée avant le décodage.** Si `decode()` lève une
  erreur, la trame brute reste disponible : c'est elle que `cli.py` affiche sous
  le message d'échec. Quand le découpage en voies n'est qu'une hypothèse, la
  trame brute est le seul juge.

### `cycle()` — la logique de réessai

```python
last_error = None
for attempt in range(1, self.retries + 1):
    try:
        values = self.read_once()
    except (ValueError, TimeoutError, BlockingIOError) as exc:
        last_error = exc
        self.rejected_total += 1
        self.rejected_since_ok += 1
        if attempt < self.retries:
            time.sleep(self.retry_delay)
    else:
        rejected = self.rejected_since_ok
        self.rejected_since_ok = 0
        return Measurement(datetime.now(), values, rejected)

return Failure(self.retries, self.rejected_total, last_error)
```

Trois choses à retenir :

1. **Le `else` d'un `try`** s'exécute quand *aucune* exception n'a été levée.
   `try/except/else` est plus précis que de mettre le code de succès dans le
   `try` : on ne risque pas d'attraper une erreur venue du chemin heureux.
2. **Les exceptions attrapées sont énumérées**, pas `except Exception`. Ce sont
   exactement les trois erreurs « normales » d'une liaison série : trame
   invalide (`ValueError`), pas de réponse (`TimeoutError`), lecture non
   bloquante à vide (`BlockingIOError`). Une `PermissionError` sur le port, elle,
   n'est **pas** attrapée : ce n'est pas un incident de ligne, ça doit remonter.
3. **`if attempt < self.retries`** : pas de pause après la dernière tentative,
   elle ne servirait à rien. Détail, mais c'est le genre de soin qui évite les
   secondes perdues.

### `run()`

```python
def run(self):
    while True:
        yield self.cycle()
        time.sleep(self.interval)
```

Une **fonction génératrice** : le `yield` rend une valeur *et met la fonction en
pause*. À l'itération suivante de la boucle `for` de l'appelant, l'exécution
reprend juste après le `yield`, fait la pause, et recommence.

Pourquoi un générateur plutôt qu'une boucle qui affiche directement ? Parce
qu'il **rend le contrôle à l'appelant entre chaque mesure**. C'est ce qui permet
à `cli.py` d'afficher un tableau, d'écrire un CSV ou de ne rien faire — sans que
`monitor.py` en sache quoi que ce soit.

La boucle est infinie : elle s'arrête par `Ctrl+C`, que `cli.py` attrape.

## La classe `Monitor5050` (16 entrées/sorties)

```python
class Monitor5050(Monitor):
    def __init__(self, port, slot=DEFAULT_SLOT, **kwargs):
        if slot not in range(IO_SLOTS):
            raise ValueError(f"Slot du 5050 hors du fond de panier : {slot} ...")
        super().__init__(port, slot=slot, channels=IO_CHANNELS, **kwargs)

    def request(self):
        command = protocol.digital_read_command(self.address, self.slot)
        return protocol.build_frame(command, self.checksum)

    def decode(self, response):
        payload = protocol.verify_frame(response, self.checksum, ack=protocol.CONFIG_ACK)
        return parse_5050(payload, self.address)
```

Un exemple d'héritage bien dosé : **seules les deux méthodes qui dépendent du
module sont redéfinies**. Toute la mécanique de `cycle()`, `run()`,
`read_once()`, les compteurs, l'ouverture du port : héritée telle quelle, sans
une ligne dupliquée.

Les deux différences avec l'analogique sont exactement celles du protocole :
la commande `$aaS<slot>6` au lieu de `#aaS<slot>`, et l'accusé `!` au lieu de `>`.

Le contrôle du slot dans `__init__` est une **validation précoce** : mieux vaut
échouer immédiatement avec un message clair que d'envoyer `$01S96` à un module
qui ne répondra jamais et laisser l'utilisateur chercher pourquoi.

`**kwargs` transmet tous les autres paramètres (`interval`, `checksum`, `baud`…)
au parent sans les réécrire.

La docstring rappelle la règle de sécurité : **aucune sortie n'est jamais
commandée**, seule leur image est lue.
