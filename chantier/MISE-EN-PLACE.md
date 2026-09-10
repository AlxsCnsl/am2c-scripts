# Le dispositif de boucle — ce qui est posé, ce qui te reste

---

# Partie 1 — Ce que j'ai fait, et pourquoi

## Le principe, et il n'y en a qu'un

**La ligne que remplit une IA est un frein, jamais un accélérateur.**

Le feu vert est calculé par [`gardes.sh`](gardes.sh) à partir de faits qu'aucun
agent ne contrôle : code de retour des tests, `grep`, `wc`, chemins touchés.
La ligne `ETAT=` de [`etat.env`](etat.env) ne peut que transformer un vert en
arrêt. Jamais l'inverse.

Cette asymétrie est ce qui te rend ton attention. Un agent optimiste ne peut
pas fabriquer un feu vert : le vert vient des tests, qu'il ne contrôle pas. Un
agent pessimiste arrête la boucle — c'est la panne sûre. Tu n'as donc plus à te
demander si un agent est honnête : sa malhonnêteté n'a plus de prise.

Le jour où tu ajoutes un champ qui *autorise* le passage, tout retombe au
niveau de confiance d'un LLM qui s'auto-évalue. C'est la seule pièce à ne
jamais toucher.

## Les pièces

| Fichier | Rôle |
|---|---|
| [`gardes.sh`](gardes.sh) | Les constats mécaniques. Le seul à pouvoir dire « continue ». |
| [`etapes.conf`](etapes.conf) | Le périmètre d'écriture par étape. Source unique, lue par le script **et** par le hook. |
| [`etat.env`](etat.env) | Le frein. Quatre valeurs, écrites par l'agent. |
| [`boucle.sh`](boucle.sh) | Le pilote : développeur → gardes → frein → todo → documenter → commit + tag. |
| [`deroule.py`](deroule.py) | Rend lisible, au fil de l'eau, ce que fait l'agent. Sans lui la boucle est muette jusqu'à la fin de l'étape. |
| [`permissions-boucle.json`](permissions-boucle.json) | Ce que les agents ont le droit de lancer **pendant** la boucle. Liste blanche. |
| [`trouver-claude.sh`](trouver-claude.sh) | Où est l'exécutable `claude` quand il n'est pas dans le `PATH`. |
| [`../lancer-boucle.sh`](../lancer-boucle.sh) | Le contrôle avant vol, puis le lancement. |
| [`CONVENTIONS.md`](CONVENTIONS.md) | Les neuf règles d'autonomie. Trois sont vérifiées mécaniquement. |
| [`traces/`](traces/) | Une trace par étape, définitive. |
| [`suivi.sh`](suivi.sh) | Vue en direct des étapes. Recompte les cases, ne recopie pas le tableau. |
| [`journal.sh`](journal.sh) | Vue en direct du frein et du journal. |
| [`JOURNAL.md`](JOURNAL.md) | Une ligne par étape. Ne se lit que si ça s'est arrêté. |
| [`.claude/hooks/perimetre-garde.py`](../.claude/hooks/perimetre-garde.py) | Refuse l'écriture hors périmètre **avant** qu'elle parte. |
| [`.claude/agents/developpeur.md`](../.claude/agents/developpeur.md) | Exécute une étape. Ne touche ni `TODO.md` ni `docs/`. |
| [`.claude/agents/todo.md`](../.claude/agents/todo.md) | Coche, et seulement si le fait est constaté. |

## Les quatre états, et celui que tu n'avais pas prévu

`OK`, `BLOQUE`, `MATERIEL` — tes trois cas. J'ai ajouté **`PLAN_FAUX`**, et
c'est le plus important des quatre.

`BLOQUE` veut dire « je ne sais pas faire ». `PLAN_FAUX` veut dire « je saurais
faire, mais seulement en m'écartant de ce que tu as écrit ». C'est l'issue la
plus probable de ton chantier : le `TODO.md` a été écrit avant que le code
bouge, et ses ancres (`monitor.py:78`, `cli.py:284`) meurent au premier
renommage. Sans ce quatrième état, un agent face à un plan périmé choisit `OK`
— parce qu'il *a* produit quelque chose — et la dérive devient invisible.

## Ce que les gardes vérifient réellement

Passé sur ton code actuel, tout est vert sauf ce qui doit l'être :

| Garde | Ce qu'elle constate |
|---|---|
| Périmètre | Aucun fichier touché hors de la ligne de l'étape. |
| Plan intact | `TODO.md` n'a changé que par des cases et des lignes de tableau. |
| Cliquet des tests | Le nombre de fonctions `test_` n'a jamais baissé. |
| I2 | Aucune trame `%` hors de `configuration.py` / `protocol.py` / `familles/`. |
| I3 | Pas de `flush_input` dans `monitor.py`. |
| I4 | Aucun `print(` sous la couche `cli`. |
| I5 | `HUPCL` et `tcdrain` toujours dans `serial_port.py`. |
| I6 | Aucun import hors bibliothèque standard (liste blanche). |
| I7 | `--scan` avant `--enable-checksum` et `--raw` dans le dispatch. |
| I8 | Aucune clé `port` dans `config.json`. |
| Suite | `python3 -m unittest discover -s tests` en vert. |
| Critère d'étape | Le « Fin d'étape » des étapes 2, 3, 5 et 6, mécanisé. |

**Le cliquet mérite une phrase.** Tu voulais interdire à un agent de toucher
aux tests. Trop rigide : un renommage déplace légitimement des imports. Ce
qu'on interdit, c'est que le filet *rétrécisse*. Le compte des `test_` est
stocké dans `cliquet-tests` et ne redescend jamais. C'est la seule faille par
laquelle cette boucle pourrait mentir en vert, et elle est fermée.

## Prévenir plutôt que constater

Tu avais déjà écrit la bonne pièce sans le savoir :
[`documenter-garde.py`](../.claude/hooks/documenter-garde.py). Cent quatre-vingt-douze
lignes qui n'émettent aucun jugement et rendent *impossible* ce que le prompt
se contente de demander. `perimetre-garde.py` est cette idée à l'échelle du
chantier : l'agent reçoit le refus et son motif, il se corrige dans le tour, et
tu n'as rien à arbitrer.

Une différence assumée avec ton hook existant : **je ne filtre pas les
commandes shell.** Ta liste blanche autorise `python3` et tente de le
neutraliser par expression régulière sur `-c` — ça tient pour un agent de doc,
ça ne généralise pas (`python3 -m truc` et `python3 script.py` passent sous les
motifs), et l'agent de développement a de toute façon besoin d'exécuter du
Python. Le périmètre porte donc sur ce qui est vérifiable — les chemins écrits
— et pas sur ce qui ne l'est pas.

## Le mode `-p` n'a personne pour répondre « oui »

Le point qui empêchait la boucle de tourner, et qui ne se voit pas en la
lisant. `boucle.sh` appelle les agents en `claude -p` : aucun humain n'est
devant. Une demande de permission n'attend donc pas — elle est **refusée
d'office**. `--permission-mode acceptEdits` couvre les écritures de fichier,
rien d'autre : le premier `cd serie && python3 -m unittest discover -s tests`
du `developpeur` partait au refus, et l'agent traversait son étape sans jamais
pouvoir vérifier son propre travail.

D'où [`permissions-boucle.json`](permissions-boucle.json), passé par
`--settings`. Deux propriétés à ne pas perdre de vue :

- **C'est une liste blanche.** Ce qui n'y figure pas est refusé, et un refus
  arrête l'agent au lieu de le laisser improviser. C'est la panne sûre, la même
  que partout ailleurs ici. Élargir cette liste est donc le seul geste du lot
  qui demande de la prudence.
- **`deny` ne protège qu'une chose : l'historique git.** `commit`, `add`,
  `reset`, `checkout`, `tag`, `push`… appartiennent à `boucle.sh`, qui commite
  et pose `etape-<N>` à chaque étape franchie. Un agent qui commite lui-même
  fait sauter le seul moyen de revenir en arrière.

`--settings` a été préféré à un `.claude/settings.json` de projet précisément
parce qu'il ne bride que la boucle : tes sessions interactives ne voient pas ce
fichier. Et il est hors du périmètre d'écriture des étapes 3 à 11 — un agent ne
peut donc pas s'élargir ses propres droits.

Deux autres manques, plus prosaïques, réglés au passage : `claude` n'est pas
dans le `PATH` d'un terminal quand Claude Code tourne comme extension VS Code
(d'où [`trouver-claude.sh`](trouver-claude.sh), qui va chercher le binaire dans
le dossier de l'extension), et un agent qui ne rendrait jamais la main figerait
la boucle sans rien écrire dans `etat.env` (d'où le `timeout` d'une heure par
appel, réglable par la variable `DELAI`).

## Pourquoi les invariants ne sont pas devenus un fichier de tests

Je t'avais proposé `tests/test_invariants.py`. J'ai mis les invariants dans
`gardes.sh` à la place, pour deux raisons : ils doivent mordre **avant** que
l'étape 1 existe, et un fichier de test vit *dans* le paquet — donc il est
déplacé, renommé et restructuré par le chantier qu'il est censé surveiller. Un
garde-fou que le chantier déplace n'est pas un garde-fou. En shell, hors du
paquet, il survit au renommage.

## Ce que ce dispositif ne fait pas

À lire aussi attentivement que le reste.

1. **Il n'attrape pas la médiocrité.** Une porte mécanique ne voit que ce que
   tu as pensé à vérifier. Du code qui passe les tests, respecte les greps,
   tient sous 170 lignes et incarne quand même une mauvaise idée franchira
   onze fois sans un bruit. C'est le prix de la suppression du vérificateur
   agentique, et il se paie par une relecture à la fin (partie 2, point 8).
2. **Trois invariants sur neuf restent à ta charge** : le français, la lecture
   seule du diagnostic *dans son intention*, et surtout **l'absence de
   commande d'écriture vers un module tout ou rien**. Celui-là ne se mécanise
   pas honnêtement — la grammaire d'écriture ressemble trop à celle de lecture
   — et c'est le seul dont l'échec claque physiquement dans une armoire. Il est
   écrit en toutes lettres dans les conventions, il n'est pas gardé par un
   script. Vérifie-le toi, à la fin, sur le diff complet.
3. **Je n'ai pas lancé `boucle.sh`.** Les gardes et le hook sont testés — greps
   passés sur le code réel, hook éprouvé dans les trois cas (hors boucle,
   chemin permis, chemin refusé). Le pilote, non : le lancer aurait fait
   travailler des agents dans ton dépôt sans que tu l'aies demandé. La forme
   exacte de l'appel `claude -p` est à vérifier chez toi (partie 2, point 5).
4. **Il ne remplace pas ton jugement sur `PLAN_FAUX`.** Quand un agent
   s'arrête là-dessus, c'est toi qui tranches. C'est voulu : voir le point 6.

---

# Partie 2 — Ce que tu dois faire à la main

Dans cet ordre. Les points 1 à 4 sont à faire avant le premier lancement.

## 1. Commiter le dispositif

`gardes.sh` compte les fichiers non suivis comme hors périmètre — c'est normal,
il constate un arbre sale. `boucle.sh` refuse d'ailleurs de démarrer sur un
arbre non propre, ce qui t'y force.

```sh
git add chantier .claude
git commit -m "chantier : dispositif de boucle (gardes, périmètre, agents)"
```

## 2. Le renommage, à la main, hors de la boucle

**C'est le point qui compte le plus dans cette liste.** L'étape 2 du TODO
(`adam5000` → `dcon`, `ADAM/` → `serie/`) n'a aucun contenu de conception, et
c'est l'étape qui invalide *toutes* les gardes des autres étapes : chemins,
greps, listes blanches. L'automatiser, c'est demander à la boucle de se
réécrire elle-même en cours de route. Le pire rapport risque/valeur du
chantier.

Dix minutes :

```sh
git mv ADAM serie && git mv serie/adam5000 serie/dcon
grep -rln 'adam5000' --exclude-dir=.git . | xargs sed -i 's/adam5000/dcon/g'
grep -rln 'ADAM/' --exclude-dir=.git . | xargs sed -i 's|ADAM/|serie/|g'
grep -rn 'adam5000\|ADAM/' --exclude-dir=.git .    # doit ne rien rendre
cd serie && python3 -m dcon --help
```

⚠️ Le second `sed` va aussi toucher des mentions légitimes. Relis le diff avant
de commiter — « ADAM-5000 » et « ADAM-5050 » sont des références matérielles et
restent. `gardes.sh` et `perimetre-garde.py` détectent le paquet tout seuls :
ils fonctionnent avant comme après, tu n'as rien à y changer.

Puis coche les cases de l'étape 2 dans `TODO.md` et lance la boucle à partir de
3 — c'est le défaut de `boucle.sh`.

## 3. L'étape 1, faite puis relue par toi, ligne à ligne

La sûreté entière du dispositif repose sur la qualité de ce filet, et ce filet
serait produit par un agent du même genre que ceux qu'il doit surveiller. Un
filet faible, et tes dix verts suivants ne prouvent rien.

C'est le seul endroit où une heure de ton temps achète onze étapes de
tranquillité. Fais écrire l'étape 1 en session interactive, puis relis chaque
test en te demandant : *est-ce qu'il échouerait si le comportement changeait ?*
Un test qui passe quoi qu'il arrive est pire que pas de test — il fait du
bruit vert.

`boucle.sh` refuse de démarrer tant que `tests/` n'existe pas.

## 4. Une séance au port série, au début

Pour convertir « le matériel bloque quatre étapes » en « une séance au début,
une séance à la fin ».

```sh
cd serie
python3 -m dcon --port /dev/ttyUSB0 --slot 0 --raw          > tests/trames/5081-slot0.txt
python3 -m dcon --port /dev/ttyUSB0 --slot 2 --5050 --raw   > tests/trames/5050-slot2.txt
```

Ces trames réelles rendent mécaniquement vérifiable presque tout ce que tu
croyais dépendre du matériel — y compris la lecture du rack de l'étape 7, via
un faux port qui les rejoue (pur standard, invariant 6 respecté).

**Elles ne remplacent pas la validation finale.** Le câblage, le semi-duplex,
le DTR, la temporisation : aucun faux port ne te les dira. Elles réduisent le
nombre d'arrêts, elles ne le mettent pas à zéro.

C'est aussi cette séance qui tranche `EXPECTED_CHANNELS` : la longueur de la
charge utile te donne la réponse, et la décision 8 du TODO devient un fait
observé.

## 5. Vérifier la forme de l'appel aux agents

C'est maintenant une commande :

```sh
./lancer-boucle.sh --essai
```

Elle fait le contrôle avant vol, puis un vrai appel d'agent qui n'écrit que
`chantier/traces/etape-0.md`. Tu vérifies d'un coup que le binaire répond, que
le fichier de permissions est accepté, que le sous-agent est trouvé, que le
hook mord et que la trace atterrit au bon endroit. Supprime la trace après.

Au passage : `developpeur` tourne en `model: opus`, `todo` et `documenter` en
`sonnet`. C'est un choix de coût, il est dans le frontmatter, change-le si tu
veux.

## 6. Trancher : qui corrige le plan sur `PLAN_FAUX` ?

Je te laisse la question parce qu'elle a une bonne réponse et une piégeuse.

Si tu donnes à un agent le droit d'écrire dans `TODO.md` pour réparer un plan
faux, tu lui rends par la porte de derrière l'accélérateur que tout le
dispositif lui retire. Un agent qui répare le plan qu'il exécute s'auto-délivre
son mandat.

Tel que c'est posé : `PLAN_FAUX` arrête la boucle, tu lis la trace, tu corriges
le plan toi-même (avec `/todo` si tu veux), tu relances à partir de l'étape
courante. C'est un arrêt de plus, et c'est délibéré.

## 7. Le lancement

```sh
./lancer-boucle.sh --verifier    # contrôle avant vol seul, ne lance rien
./lancer-boucle.sh 3 11          # contrôle, puis lance
./lancer-boucle.sh --fond 3 11   # détaché : survit à la fermeture du terminal
```

`sh chantier/boucle.sh 3 11` marche toujours et fait exactement le travail :
`lancer-boucle.sh` ne fait que constater avant, parce qu'une boucle qui tourne
des heures ne doit pas s'arrêter à l'étape 7 pour une raison qu'on pouvait voir
en dix secondes. Ce qu'il constate : l'exécutable `claude` et sa version, le
fichier de permissions, l'arbre propre, la suite verte et son cliquet, les
hooks exécutables, les trois sous-agents, et une ligne d'`etapes.conf` par
étape demandée.

Pendant qu'elle tourne, deux vues à laisser dans un volet — elles ne changent
rien, elles regardent : `sh chantier/suivi.sh` (les étapes) et
`sh chantier/journal.sh` (le frein et le journal).

`suivi.sh` recompte les cases de `TODO.md` et des `TODO/part*.md` au lieu de
recopier le tableau de bord — le tableau est tenu par l'agent `todo`, les cases
sont le fait, et l'écart entre les deux est précisément ce qu'on veut voir.

Ne lance pas `sh chantier/gardes.sh 3` en espérant du vert avant de partir : le
critère propre à l'étape 3 est ce que l'étape 3 *produit*. Il est rouge tant
qu'elle n'est pas faite, et c'est normal. `boucle.sh` ne consulte les gardes
qu'après le passage de l'agent.

À la fin d'un arrêt, tu as toujours de quoi revenir :

```sh
git reset --hard etape-6         # annule tout ce qui a suivi l'étape 6
```

Un tag par étape franchie. C'est ce qui manquait à ton design initial : tu
avais prévu de quoi *savoir* où ça avait cassé, pas de quoi *revenir* avant.

## 8. À la fin : la relecture que la boucle ne fait pas

```sh
git diff etape-2..HEAD
/code-review high
```

C'est là que se rattrape ce que le point « ce que le dispositif ne fait pas »
laisse passer. La revue est *hors* de la boucle et *après* : elle ne peut rien
débloquer, donc elle n'a aucun intérêt à être complaisante. C'est exactement
pour ça qu'elle vaut mieux qu'un vérificateur-portier.

Vérifie à ce moment-là, toi, sur le diff complet : **aucune trame ne commande
une sortie physique.**

## 9. Les cases (toi) du TODO

Étapes 7 et 11 : lecture continue du 5050, `--scan` sur un port muet, lecture
complète du rack depuis `config.json`. Elles attendent une main humaine et
aucune étape ne les attend pour avancer — c'est écrit dans `TODO.md`, et
`ETAT=MATERIEL` est là pour que la boucle te les remonte au lieu de les cocher.

## En résumé de ce que ça te coûte

| Quand | Ce que tu fais | Combien |
|---|---|---|
| Avant | Renommage à la main | 10 min |
| Avant | Étape 1 relue ligne à ligne | 1 h — le meilleur investissement du lot |
| Avant | Une séance au port série | 20 min |
| Pendant | Rien, sauf arrêt | une ligne de journal par étape |
| Sur arrêt | Lire une trace, trancher, relancer | quelques minutes |
| Après | Relire le diff complet | 1 h |

Ton attention n'est pas supprimée : elle est déplacée aux deux endroits où elle
a du levier, le filet au début et le diff à la fin. Méfie-toi de qui te
promettra zéro.
