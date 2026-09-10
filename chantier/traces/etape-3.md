# Étape 3 — Rendre `protocol.py` réellement générique

## Fait
`protocol.py` ne garde que l'enveloppe (`TERMINATOR`, `ACK`, `CONFIG_ACK`,
`DEFAULT_ADDRESS`, `checksum_ascii`, `build_frame`, `verify_frame`), en-tête
récrit en ce sens. `read_command`, `build_command`, `digital_read_command` et
`ENABLE_CHECKSUM` sont partis dans `serie/dcon/familles.py`, sans changer un
caractère des trames. Les six importateurs sont recâblés. 72 tests verts,
compte inchangé.

## Décidé
- **`serie/dcon/familles.py`, module plat** : le périmètre de l'étape 3
  (`@PAQ@/*.py @BASE@/tests/*`) n'autorise pas `familles/`, réservé à l'étape 4.
  Le module porte le nom de la destination et se remplacera par le paquet sans
  retoucher les importateurs. Écarté : parquer dans `modules.py`, qui mélangerait
  « comment on demande » et « comment on décode ».
- **`build_command` déménage aussi**, non nommé par le TODO : il fabrique
  `#<adresse>S<slot>`, donc il tombe sous la liste « ne garder que ».
- **Tests déplacés, pas récrits** : la classe `Commandes` passe telle quelle de
  `test_protocol.py` à `tests/test_familles.py` (le fichier annonçait lui-même ce
  déménagement). Aucune assertion touchée, aucun `test_` perdu.
- **Rien du descripteur `Famille`** (classe, registre, `adam5000`/`autonome`,
  `IO_SLOTS`) : c'est l'étape 4.

## Pourquoi PLAN_FAUX
`ENABLE_CHECKSUM` ne peut pas atterrir dans un fichier plat : la garde I2 de
`gardes.sh` refuse toute trame `%` hors de `configuration.py`, `protocol.py` et
du **répertoire** `/familles/` — vérifié, elle signale aujourd'hui
`serie/dcon/familles.py`. Or l'étape 3 ne peut pas créer `familles/`.
`TODO/part3.md` (ancienne numérotation) dit : « on ne peut pas vider
`protocol.py` sans donner une destination à ce qui en sort : cette étape crée
donc les familles **et** déménage » ; la coupure 3/4 de `TODO.md` a séparé les
deux. Trois issues : ouvrir `@PAQ@/familles/*` à l'étape 3 (le travail est alors
fini d'un `git mv`) ; élargir I2 au fichier `familles.py` ; ou laisser
`ENABLE_CHECKSUM` dans `protocol.py` jusqu'à l'étape 4 — toléré par les gardes,
interdit par les deux premiers points du TODO.

## Remarqué, pas traité
- `TODO.md` renvoie pour l'étape 4 vers `TODO/part3.md`, d'ancienne numérotation
  (le détail à jour est `TODO/part4.md`) ; l'étape 7 renvoie à `TODO/part6.md`,
  absent. Liens du plan, pas mon métier.
- Aucune trace d'étape 1 ni 2 : je n'ai hérité d'aucun contexte écrit.
- `docs/` cite encore `protocol.read_command` : à l'agent `documenter`.

## Pour l'étape suivante
En créant `familles/`, **supprimer `serie/dcon/familles.py`** : un fichier resté
là serait masqué en silence par le paquet. Les cinq cas de `test_familles.py`
figent les trames caractère par caractère.
