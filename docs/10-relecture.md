# 10. Relecture critique du code Python

Relecture des fichiers Python du paquet `adam5000`. Les constats sont classés
par gravité. Chaque anomalie est reproduite ou tracée jusqu'à la ligne
concernée ; **aucune correction n'a été appliquée** — ce document propose, il
ne modifie pas.

## Impression générale

Le code est d'une qualité nettement au-dessus de la moyenne pour des scripts
d'atelier : découpage en couches respecté sans exception, commentaires qui
expliquent le *pourquoi* et pas le *quoi*, exceptions énumérées plutôt
qu'attrapées en bloc, aucun affichage dans les couches basses, et une règle de
sécurité (lecture seule sur le 5050) tenue partout. Les anomalies ci-dessous
sont réelles mais mineures ; aucune ne remet en cause la conception.

---

## 1. `parse_5050()` confond un mot d'état avec l'adresse

**Gravité : moyenne — bogue reproductible**
[modules.py:59](../ADAM/adam5000/modules.py#L59)

```python
if payload.upper().startswith(address.upper()):
    payload = payload[len(address):]
```

L'intention est bonne : certains modules réémettent leur adresse en tête de
charge utile, d'autres non. Mais le test se fait sur les caractères seuls, sans
regarder la longueur. Si le module **ne** réémet **pas** l'adresse et que le mot
d'état commence par les mêmes chiffres, les deux premiers caractères du mot sont
mangés.

Reproduction (adresse par défaut `01`) :

```
$ python3 -c "from adam5000 import modules; print(modules.parse_5050('0100'))"
ValueError: Mot d'état illisible : '00'

$ python3 -c "from adam5000 import modules; print(modules.parse_5050('01FF'))"
ValueError: Mot d'état illisible : 'FF'
```

`0x0100` est un état parfaitement légitime : voie 8 active, les autres au repos.
Toute la plage `0x0100`–`0x01FF` (256 états sur 65536) est concernée avec
l'adresse `01`, et la plage correspondante pour toute autre adresse.

L'erreur est *visible* (exception plutôt que valeurs fausses), et
`Monitor.cycle()` réessaiera — mais il réessaiera indéfiniment tant que la voie
8 restera dans cet état, produisant un `Failure` sur un module en parfait état
de marche.

**Correction proposée** — ne retirer l'adresse que s'il reste assez de
caractères pour un mot complet :

```python
if (len(payload) > IO_WORD_LENGTH
        and payload.upper().startswith(address.upper())):
    payload = payload[len(address):]
```

Une charge utile de 4 caractères est forcément un mot seul ; une de 6 avec
l'adresse en tête est sans ambiguïté.

---

## 2. Les octets qui suivent le `\r` sont perdus

**Gravité : faible en usage normal, à connaître**
[serial_port.py:124](../ADAM/adam5000/serial_port.py#L124)

```python
frame, _, rest = bytes(data).partition(b"\r")
return frame.decode("ascii", errors="replace")
```

`rest` est nommé puis jeté. Ces octets ont déjà été retirés du tampon du noyau
par `os.read()` : ils sont donc définitivement perdus, pas simplement reportés
au prochain appel.

En pratique, le protocole est strictement requête/réponse et une seule trame
circule à la fois : le cas ne se produit pas. Il se produirait si le module
émettait deux trames coup sur coup (réponse tardive d'un réessai précédent
suivie de la réponse en cours), et le symptôme serait alors une trame perdue
sans explication.

**Deux options :**

- *documenter* : renommer `rest` en `_` et ajouter un commentaire « une seule
  trame circule à la fois, le reliquat est ignoré » ;
- *conserver* : stocker `rest` dans `self._reste` et le préfixer au `data` du
  prochain `read_frame()`. Plus juste, mais ajoute un état à une classe qui n'en
  a pas et complique le raisonnement. À ne faire que si le cas se présente
  réellement.

Le choix par défaut du dépôt (simplicité) est défendable ; ce qui manque, c'est
la phrase qui dit que c'est un choix.

---

## 3. Une vitesse inconnue passe sans erreur

**Gravité : faible — l'API interne contredit sa propre garde**
[serial_port.py:44](../ADAM/adam5000/serial_port.py#L44)

```python
self.baud = baud_constant(baud) if baud in BAUDRATES else baud
```

`baud_constant()` existe pour lever une `ValueError` explicite listant les
vitesses connues. Mais cette ligne ne l'appelle **que si la vitesse est déjà
connue** : une valeur inconnue (`SerialPort(dev, 3000)`) contourne la garde et
part telle quelle vers `termios`, où elle sera interprétée comme un code noyau
brut — configuration silencieusement fausse ou erreur incompréhensible.

En pratique la CLI est protégée par `choices=sorted(BAUDRATES)` dans
`parse_args()`, donc le cas ne peut pas venir de la ligne de commande. Il peut
venir d'un appel direct au paquet.

**Correction proposée** — inverser le test, de façon qu'une valeur inconnue
finisse toujours chez `baud_constant()` :

```python
# Un code termios déjà traduit passe tel quel ; tout le reste est soumis à
# baud_constant(), qui traduit ou refuse avec un message explicite.
self.baud = baud if baud in BAUDRATES.values() else baud_constant(baud)
```

Une vitesse inconnue obtient alors le message d'erreur prévu pour elle. (Sur
cette machine, `termios.B38400` vaut justement `38400`, donc les deux ensembles
se confondent et rien ne change pour les vitesses connues ; sur une plateforme
où `B9600 == 13`, la ligne continue d'accepter les deux formes.)

---

## 4. `--scan-addresses` ne propose pas de commande à relancer

**Gravité : faible — fonctionnalité inachevée**
[cli.py:128-137](../ADAM/adam5000/cli.py#L128-L137)

Dans le chemin nominal, `run_scan()` termine par
`print(suggest_command(args.port, trouvailles))` : l'utilisateur reçoit la ligne
de commande exacte à relancer. Dans la branche `--scan-addresses`, les adresses
trouvées sont ajoutées à `trouvailles`… et rien n'en est fait :

```python
for attempt in diagnostic.sweep_addresses(args.port, args.baud):
    ...
    if attempt.response:
        print(f"  adresse {attempt.address} -> {attempt.response!r}")
        trouvailles.append(attempt)

if not trouvailles:
    print("  aucune adresse ne répond.")
```

C'est précisément le cas où l'aide serait la plus utile : l'utilisateur vient
d'attendre deux minutes et vient d'apprendre que son module est à l'adresse `2F`,
information qu'il doit maintenant reporter à la main.

**Correction proposée** — remplacer le bloc final par :

```python
if trouvailles:
    print()
    print("Le module répond. À reprendre :")
    print(f"  {suggest_command(args.port, trouvailles)}")
else:
    print("  aucune adresse ne répond.")
```

`suggest_command()` fonctionne tel quel sur ces `Attempt` (leur `slot` vaut
`None`, elle retombe sur la première trouvaille).

---

## 5. `except Exception` masque la trace en cas de bogue

**Gravité : faible — gêne la mise au point**
[cli.py:382](../ADAM/adam5000/cli.py#L382)

```python
except Exception as exc:
    print(f"Erreur : {exc}", file=sys.stderr)
    return 1
```

Excellent pour les erreurs attendues : `Permission denied`, `Vitesse non
gérée`, `Commande refusée par le module` deviennent des messages courts au lieu
de traces effrayantes. Mais un vrai bogue (`AttributeError`, `IndexError`) est
réduit à une ligne sans indication de l'endroit, ce qui rend le diagnostic
pénible — d'autant qu'il n'y a pas de tests pour rattraper ça.

**Correction proposée** — une variable d'environnement qui laisse passer la
trace :

```python
except Exception as exc:
    if os.environ.get("ADAM_DEBUG"):
        raise
    print(f"Erreur : {exc}", file=sys.stderr)
    return 1
```

Accessoirement, `Ctrl+C` pendant `--scan` ou `--raw` produit aujourd'hui une
trace `KeyboardInterrupt` (seules les deux boucles de mesure la rattrapent).
Ajouter `except KeyboardInterrupt: print("\nInterrompu."); return 130` dans
`main()` traiterait les six branches d'un coup (130 est le code de retour
conventionnel pour une interruption).

---

## 6. `__init__.py` ne reflète plus le contenu du paquet

**Gravité : faible — cohérence**
[__init__.py](../ADAM/adam5000/__init__.py)

L'API publique déclarée date d'avant le support du 5050 et du diagnostic. Il
manque : `Monitor5050`, `parse_5050`, `digital_read_command`, `DEFAULT_ADDRESS`,
`possible_layouts`, et tout `diagnostic`.

Et il exporte `BAUD` :

```python
BAUD = BAUDRATES[DEFAULT_BAUD]      # serial_port.py
```

c'est-à-dire le **code termios** de 38400, à ne pas confondre avec
`DEFAULT_BAUD`, qui est la vitesse elle-même. Les deux se trouvent numériquement
égaux sur cette machine, ce qui masque la distinction plus que ça ne l'éclaire —
et aucun code du paquet ne s'en sert plus. Deux noms voisins pour deux notions
différentes, dont l'un est mort : le genre de détail sur lequel un nouveau venu
perd une demi-heure.

**Correction proposée** : ajouter les noms manquants à `__all__`, et retirer
`BAUD` de l'export (voire du fichier, après vérification qu'aucun script
extérieur ne l'importe).

---

## 7. Points mineurs

Sans conséquence, mais à savoir :

- **`rejected_since_ok` n'est pas remis à zéro sur un `Failure`.**
  [monitor.py:108](../ADAM/adam5000/monitor.py#L108) — après un cycle
  entièrement raté, le compteur continue de s'accumuler et sera reporté sur la
  prochaine mesure réussie. C'est cohérent avec le libellé affiché (« trames
  rejetées avant celle-ci »), donc probablement voulu ; ça mérite une ligne de
  commentaire, parce qu'un relecteur y verra un oubli.

- **Deux fonctions nommées `enable_checksum`.**
  `cli.enable_checksum()` appelle `configuration.enable_checksum()`. Aucun
  conflit technique (l'appel est préfixé par son module), mais la lecture est
  ambiguë. `afficher_activation_checksum()` côté CLI lèverait le doute.

- **`Monitor5050` fixe `channels` en dur.**
  [monitor.py:129](../ADAM/adam5000/monitor.py#L129) — passer `channels=` à son
  constructeur provoquerait un `TypeError` (argument dupliqué), et `width` reste
  accepté alors qu'il ne sert à rien pour un module tout ou rien. Sans
  conséquence aujourd'hui, `cli.py` ne les passe pas.

- **`EXPECTED_CHANNELS = 8` contre « l'ADAM-5081 compte 4 voies ».**
  [modules.py:9-16](../ADAM/adam5000/modules.py#L9-L16) — la docstring et la
  constante ne disent pas la même chose. Le commentaire l'assume (« plusieurs
  champs par voie »), mais la valeur reste une hypothèse **non confirmée contre
  le matériel**. À trancher avec `--raw` sur le module réel, puis à figer avec un
  commentaire qui dit ce qui a été observé.

- **`show_raw()` ne vide pas le tampon d'entrée.**
  [cli.py:236](../ADAM/adam5000/cli.py#L236) — `configuration.send_once()` ouvre
  le port et lit aussitôt. Un reliquat d'une exécution précédente pourrait être
  pris pour la réponse. Un `flush_input()` après ouverture, comme le fait
  `diagnostic.attempt()`, fiabiliserait l'outil de mise au point.

---

## Ce qui est bien fait et qu'il faut préserver

À ne pas « améliorer » par mégarde :

1. **L'absence de `flush_input()` dans `Monitor.read_once()`** — c'est un choix
   documenté, pas un oubli. Le rajouter couperait des trames en cours d'arrivée.
2. **`HUPCL` effacé** dans `serial_port.configure()` — sans ça, DTR retombe à la
   fermeture et beaucoup de convertisseurs USB cessent d'émettre.
3. **`tcdrain()` après chaque écriture** — indispensable en semi-duplex RS-485.
4. **Les exceptions énumérées** dans `Monitor.cycle()` — une `PermissionError`
   doit remonter, pas être réessayée cinq fois.
5. **`--scan` testé en premier dans `main()`** — c'est le recours quand rien ne
   marche, il ne doit jamais être masqué.
6. **L'absence totale de commande d'écriture pour le 5050** — garantie de
   sécurité : aucun relais ne peut être actionné par accident.
7. **`time.monotonic()` pour les durées, `datetime.now()` pour les dates** —
   correct partout, ce qui est rare.
