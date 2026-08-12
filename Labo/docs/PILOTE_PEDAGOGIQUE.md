# Pilote pédagogique Squat GUI 0.2.0

## Objectif et participants

Faire tester la compréhension et la fluidité du parcours, pas les connaissances des
participants. Prévoir 3 à 5 étudiants représentatifs, individuellement, pendant
35 à 45 minutes. L'observateur intervient seulement lorsqu'un participant est bloqué
plus de deux minutes et note alors l'aide fournie.

## Scénario sans démonstration préalable

1. Lancer l'application et identifier le sujet, la prise de barre et la charge.
2. En Observation, formuler une hypothèse sur l'effet du passage `back` → `front`.
3. En Cinématique, retrouver le temps et la phase de la position basse, puis lire un
   angle articulaire et une coordonnée dans l'infobulle.
4. En Dynamique, identifier CoM, CoP/ZMP, base fonctionnelle, GRF et articulation la
   plus sollicitée.
5. Ajouter la condition, la dupliquer, changer uniquement la prise de barre et vérifier
   les `Variables contrôlées`.
6. Exporter le classeur Excel, retrouver l'anthropométrie et une métrique choisie.
7. Exporter puis lire le MP4.

## Mesures à recueillir

Pour chaque tâche, noter `réussie sans aide`, `réussie avec aide` ou `non réussie`, le
temps approximatif, les erreurs observées et les mots employés spontanément. Terminer
par quatre questions :

- Quelle information était la plus facile à trouver ?
- Quelle étape était la moins claire ?
- Quelle grandeur ou quel terme semblait ambigu ?
- Que changeriez-vous avant d'utiliser l'outil seul en laboratoire ?

Ne collecter aucune donnée de santé ni information personnelle inutile. Identifier les
participants par P01, P02, etc.

## Critères d'acceptation

- Au moins 80 % des tâches essentielles sont réussies sans aide : navigation des trois
  niveaux, curseur/phase, duplication contrôlée et export Excel.
- Tous les participants peuvent expliquer la différence entre CoM et CoP/ZMP après le
  parcours, sans exiger une formulation identique au tutoriel.
- Aucun crash, perte de conditions ou export illisible.
- Aucun même blocage critique observé chez deux participants ou plus.

Classer les observations avant correction : `P0` empêche le laboratoire, `P1` provoque
une erreur scientifique ou un blocage répété, `P2` ralentit ou prête à confusion,
`P3` est cosmétique. Conserver le gel 0.2.0 intact pendant le pilote; affecter les
corrections retenues à 0.2.1, sauf P0 confirmé.
