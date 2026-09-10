# 5. `modules.py` — le décodage des valeurs

Fichier : [serie/dcon/modules.py](../serie/dcon/modules.py) — 87 lignes.

**Rôle :** transformer une charge utile (déjà validée par `verify_frame()`) en
liste de valeurs de voies. Une fonction par module d'E/S.

C'est le fichier le plus simple à comprendre et le plus facile à essayer : ce
sont des **fonctions pures**, sans matériel ni état. Tu peux les appeler à la
main :

```sh
cd serie
python3 -c "from dcon import modules; print(modules.parse_5050('01FF00'))"
```

## Les constantes

```python
EXPECTED_CHANNELS = 8      # voies analogiques supposées (ADAM-5081)
EXPECTED_WIDTH = 10        # caractères par voie analogique
IO_CHANNELS = 16           # voies tout ou rien de l'ADAM-5050
IO_WORD_LENGTH = 4         # 4 chiffres hexadécimaux = 16 bits
IO_SLOTS = 4               # emplacements du fond de panier, numérotés 0 à 3
SUPPORTED_MODULES = ("5050", "5081")    # références dont le décodage existe ici
CANDIDATE_CHANNELS = (1, 2, 4, 8, 16)   # découpages plausibles, pour --raw
```

`SUPPORTED_MODULES` liste les références dont une fonction `parse_*` existe
plus bas dans ce fichier. C'est la même liste que `settings.py`
([12-settings.md](12-settings.md)) utilise pour valider le champ `module` d'un
fichier de réglages : ajouter un modèle ici, c'est aussi le rendre acceptable
dans le fichier JSON, sans toucher à `settings.py`.

Le commentaire du fichier insiste sur un point : `EXPECTED_CHANNELS` et
`EXPECTED_WIDTH` sont des **hypothèses sur le module câblé**, pas des vérités.
L'ADAM-5081 compte 4 voies physiques, mais la réponse peut contenir plusieurs
champs par voie, d'où la valeur 8 par défaut. Ces deux valeurs sont réglables
par `--channels` et `--width`, et `possible_layouts()` sert à retrouver le bon
découpage face au matériel réel.

## `parse_5081(payload, channels=8, width=10)`

```python
expected_len = channels * width
if len(payload) != expected_len:
    raise ValueError(f"Longueur invalide : {len(payload)} au lieu de {expected_len}")
if not payload.isdigit():
    raise ValueError("Données non numériques")

values = []
for i in range(channels):
    field = payload[i*width:(i+1)*width]
    values.append(int(field))
return values
```

Un découpage à largeur fixe, c'est tout. La charge utile est une longue suite
de chiffres, on la coupe en `channels` tranches de `width` caractères et on
convertit chaque tranche en entier.

`payload[i*width:(i+1)*width]` : pour `i=0, width=10` → caractères 0 à 9 ; pour
`i=1` → 10 à 19 ; etc.

Les deux contrôles préalables sont **stricts et volontaires** : plutôt rejeter
une trame que rendre des valeurs inventées. Si la longueur ne tombe pas juste,
c'est que l'hypothèse `channels × width` est fausse, ou que la trame est
tronquée — dans les deux cas les nombres seraient faux. La `ValueError`
remonte jusqu'à `Monitor.cycle()`, qui réessaie.

## `parse_5050(payload, address="01")`

Le module ADAM-5050 a 16 voies tout ou rien. Il renvoie leur état sous forme
d'**un mot de 4 chiffres hexadécimaux**, soit 16 bits, un par voie.

```python
if payload.upper().startswith(address.upper()):
    payload = payload[len(address):]          # certains modules réémettent l'adresse

word = payload[:IO_WORD_LENGTH].upper()

if len(word) < IO_WORD_LENGTH or any(c not in "0123456789ABCDEF" for c in word):
    raise ValueError(f"Mot d'état illisible : {payload!r}")

value = int(word, 16)
return [(value >> channel) & 1 for channel in range(IO_CHANNELS)]
```

### Comprendre la dernière ligne

C'est l'opération à connaître quand on lit du matériel. `int(word, 16)` convertit
`"FF00"` en l'entier `65280`. Ensuite, pour chaque voie :

- `value >> channel` décale les bits vers la droite de `channel` positions ;
- `& 1` ne garde que le bit le plus à droite.

Donc `(value >> 3) & 1` isole le bit n°3. La voie 0 est le **bit de poids
faible** (le plus à droite), convention Advantech.

Vérifié en pratique :

```
parse_5050("01FF00")  →  [0,0,0,0,0,0,0,0, 1,1,1,1,1,1,1,1]
                          voies 0 à 7 à 0    voies 8 à 15 à 1
```

(`"01"` est retiré comme étant l'adresse, le mot est `FF00` = `1111111100000000`
en binaire ; le bit 0 vaut 0, les bits 8 à 15 valent 1.)

### Le retrait de l'adresse

Certains modules réémettent leur adresse en tête de charge utile, d'autres non.
Le code accepte les deux formes. ⚠️ Cette souplesse a un défaut réel, décrit
dans la [relecture](10-relecture.md#1-parse_5050-confond-un-mot-détat-avec-ladresse).

### Lecture seule, par conception

`modules.py` n'a **aucune** fonction d'écriture des sorties, et `protocol.py`
n'a aucune commande d'écriture pour le 5050. C'est délibéré : l'ADAM-5050 pilote
des relais physiques, et une commande envoyée par erreur pendant une mise au
point actionnerait du matériel réel. Seule l'image des E/S est lue.

**Ne rajoute pas de fonction d'écriture sans en discuter.**

## `possible_layouts(payload, candidates=(1,2,4,8,16))`

```python
layouts = []
for channels in candidates:
    if not payload or len(payload) % channels:
        continue
    width = len(payload) // channels
    fields = [payload[i*width:(i+1)*width] for i in range(channels)]
    layouts.append((channels, width, fields))
return layouts
```

Outil de mise au point, utilisé uniquement par `cli.show_raw()` (`--raw`).
Quand on ne sait pas comment le module découpe sa réponse, cette fonction rend
**tous les découpages entiers possibles** de la charge utile.

`len(payload) % channels` : si le reste de la division n'est pas nul, ce
découpage est impossible, on passe. Vérifié :

```
possible_layouts("12345678")
→ [(1, 8, ['12345678']),
   (2, 4, ['1234', '5678']),
   (4, 2, ['12', '34', '56', '78']),
   (8, 1, ['1','2','3','4','5','6','7','8'])]
```

C'est ensuite à l'humain de reconnaître le bon découpage. `cli.py` aide en
signalant « mêmes valeurs répétées » : un découpage qui répète la même valeur
d'une voie à l'autre coupe très probablement les champs au mauvais endroit.

## Ajouter un module (5017, 5018…)

C'est le scénario prévu par l'architecture :

1. Écrire `parse_5017(payload, ...)` **ici**, sur le modèle des deux autres.
2. Si sa requête diffère, ajouter la commande dans le paquet `familles`
   ([13-familles.md](13-familles.md)) ; si son accusé diffère, c'est
   `protocol.py` qu'il faut regarder.
3. Si sa boucle diffère, ajouter une sous-classe de `Monitor` comme
   `Monitor5050`.
4. Brancher l'option dans `cli.parse_args()` et `cli.main()`.

Aucune autre couche n'a besoin d'être touchée.
