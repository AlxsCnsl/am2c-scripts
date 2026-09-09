# Conventions d'autonomie

Tu tournes sans personne pour te relire au moment où tu écris. Ces règles ne
sont pas des recommandations : trois d'entre elles sont vérifiées
mécaniquement par [gardes.sh](gardes.sh) et par le hook `perimetre-garde.py`,
et leur violation arrête la boucle.

Lis-les en entier avant d'écrire la première ligne.

---

## 1. Tu ne fais que ce que l'étape demande

Le périmètre de ton étape est une ligne de [etapes.conf](etapes.conf). Tu
n'écris nulle part ailleurs, et le hook te refusera l'écriture avant même
qu'elle parte.

Ce que tu ne fais pas, même si c'est manifestement une bonne idée :

- corriger un bogue que tu remarques et qui appartient à une autre étape ;
- améliorer, reformater, renommer, réordonner ce que tu n'avais pas à toucher ;
- ajouter un test, une option, un message, une garde que le TODO ne demande pas ;
- documenter — c'est le métier de l'agent `documenter`, qui passe après toi ;
- cocher une case du TODO — c'est le métier de l'agent `todo`.

Un refus du hook n'est pas un incident. C'est la limite qui fonctionne. Tu
corriges ta cible ; tu ne cherches jamais à la contourner.

**Ce que tu fais de ce que tu as remarqué :** tu l'écris dans ta trace, sous
« Remarqué, pas traité ». C'est là que ça sert, et nulle part ailleurs.

## 2. Le doute s'arrête, il ne s'arrange pas

C'est la règle qui rend l'autonomie tenable. Devant une décision que le TODO
ne tranche pas :

- si un usage évident du dépôt la tranche à ta place, tu suis cet usage et tu
  l'écris dans ta trace ;
- sinon, **tu t'arrêtes**. `ETAT=BLOQUE` ou `ETAT=PLAN_FAUX`, et tu expliques.

Tu ne devines jamais une intention. Un arrêt coûte quelques minutes à
l'utilisateur ; une intention devinée à l'étape 4 se paie à l'étape 9, quand
plus personne ne sait d'où vient le problème.

## 3. Le plan est en lecture seule

Tu ne réécris jamais `TODO.md` ni `TODO/part*.md`. Ni pour corriger une
coquille, ni pour réparer un lien mort, ni pour ajuster une formulation qui te
semble fausse. La garde le vérifie ligne à ligne.

Si le plan est faux — et il le sera, il a été écrit avant que le code bouge —
c'est `ETAT=PLAN_FAUX`, avec dans ta trace ce que tu aurais écrit à la place.
L'utilisateur tranche. Un agent qui répare le plan qu'il est en train
d'exécuter s'auto-délivre son mandat.

⚠️ Les liens du TODO pointent vers des numéros de ligne (`monitor.py:78`) qui
sont **périmés** dès que le code a bougé. Un numéro faux n'est pas un plan
faux : trouve la bonne cible par son nom, et signale la dérive dans ta trace.
Si c'est la *chose demandée* qui n'existe plus, alors c'est `PLAN_FAUX`.

## 4. Tu ne touches pas à la mesure pour la faire passer

Le filet de tests est ce qui rend cette boucle possible. Tu peux l'étendre et
l'adapter — un renommage déplace légitimement des imports. Tu ne peux jamais
le réduire : le nombre de fonctions `test_` ne redescend pas, un fichier de
test ne disparaît pas. Un cliquet le vérifie.

Un test qui devient rouge parce que le comportement a changé exprès se
**réécrit dans le même commit que le changement**, et ta trace dit ce qui a
bougé et pourquoi. Un test qu'on supprime pour passer au vert est la seule
façon dont cette boucle peut mentir. Ne l'ouvre pas.

## 5. Les neuf invariants priment sur l'étape

Ils sont dans `TODO.md`. Si l'étape que tu exécutes ne peut aboutir qu'en
cassant un invariant, ce n'est pas l'invariant qui plie : c'est `PLAN_FAUX`.

Six d'entre eux sont vérifiés mécaniquement. Trois ne le sont pas — la langue
française, l'absence de commande d'écriture vers un module tout ou rien, la
lecture seule du diagnostic dans son intention. Ceux-là reposent sur toi.
Le premier surtout : **aucune trame ne commande jamais une sortie physique.**
Un relais qui claque dans une armoire n'a pas d'annulation.

## 6. Tu écris ta trace avant de rendre la main

`chantier/traces/etape-<N>.md`, quarante lignes au plus. Elle a deux lecteurs :
l'utilisateur, qui ne la lira que si quelque chose a cassé, et **l'agent de
l'étape suivante**, qui part sans aucun souvenir de ce que tu as fait. Écris
pour le second ; le premier s'y retrouvera.

```markdown
# Étape <N> — <titre>

## Fait
<Ce qui a changé, en trois lignes. Pas la liste des fichiers, git l'a déjà.>

## Décidé
<Chaque choix que le TODO ne dictait pas : ce que j'ai retenu, ce que j'ai
écarté, et pourquoi. C'est la seule partie irremplaçable de ce fichier —
git montre le quoi, jamais le pourquoi.>

## Remarqué, pas traité
<Ce que j'ai vu et laissé, avec l'étape à laquelle ça appartient.>

## Pour l'étape suivante
<Ce que je devrais savoir si je reprenais ce chantier sans mémoire.>
```

Ta trace est définitive. Tu ne réécris jamais celle d'une étape franchie, y
compris la tienne si tu repasses. Si une trace est fausse, on ajoute
`etape-<N>-rectificatif.md` — l'erreur reste lisible, c'est tout l'intérêt.

## 7. Puis tu poses le frein

`chantier/etat.env`, deux lignes :

```
ETAT=OK|BLOQUE|MATERIEL|PLAN_FAUX
RAISON=une phrase
```

Sache ce que fait cette ligne : elle peut seulement **arrêter** la boucle. Le
feu vert vient des gardes mécaniques, que tu ne contrôles pas. Écrire `OK`
n'atteste de rien et n'ouvre rien — c'est l'absence de frein, pas un verdict.
Tu n'as donc aucune raison d'être optimiste, et aucun gain à l'être.

Dans le doute entre `OK` et autre chose : ce n'est pas `OK`.

## 8. Ce que tu ne peux pas vérifier, tu ne l'affirmes pas

`/dev/ttyUSB0` n'est pas ouvrable depuis la session. Aucun agent de cette
boucle ne valide un comportement matériel — pas même « ça devrait marcher ».
Tout ce qui exige le port : `ETAT=MATERIEL`, et la manipulation exacte à faire
dans ta trace.

Pour tout le reste, tu vérifies avant d'affirmer : une fonction pure, tu la
lances ; une constante, tu la lis. Jamais une déduction à partir d'un nom.

## 9. Français

Code, commentaires, messages, traces, documentation. Les drapeaux de ligne de
commande restent en anglais, comme les existants.
