# Squat GUI

Squat GUI est une application pédagogique 2D pour observer la cinématique et la
dynamique inverse d'un squat. Elle permet de comparer des postures, des charges,
des prises de barre et des profils anthropométriques sans écrire de code.

> Cet outil sert à l'enseignement. Il ne fournit ni diagnostic, ni prescription
> clinique ou sportive.

## Démarrage étudiant en 3 étapes

1. **Télécharger** le ZIP Windows ou macOS depuis la
   [dernière release](https://github.com/mickaelbegon/Squat_GUI/releases/latest).
2. **Décompresser et ouvrir** `Squat GUI.exe` sous Windows ou `Squat GUI.app`
   sous macOS. Conserver tout le dossier Windows avec le fichier `.exe`.
3. **Suivre le parcours intégré** en activant `Parcours didactique`, puis avancer
   de l'observation vers la cinématique et la dynamique.

Python, Conda et le terminal ne sont pas nécessaires avec ces versions.

Si macOS bloque une application non signée, faire clic droit sur
`Squat GUI.app`, choisir `Ouvrir`, puis confirmer. Pour un avertissement Windows,
vérifier que le ZIP provient bien de la page Releases du dépôt avant de continuer.

## Parcours conseillé

1. Choisir le profil du sujet et la position de la barre.
2. Régler la charge et les durées, puis déplacer la posture basse.
3. Lire l'animation en mode `OBSERVATION` et formuler une hypothèse.
4. Passer en `CINÉMATIQUE`, puis en `DYNAMIQUE` pour afficher les mesures.
5. Ajouter une condition, la dupliquer et ne modifier qu'un paramètre.
6. Comparer les deux conditions et exporter les résultats au besoin.

## Installation Python facultative

Pour les personnes qui disposent déjà de Python 3.9 ou plus :

```bash
python -m pip install -e .
python -m squat_gui
```

Le solveur analytique fonctionne sans `biorbd`. Les dépendances et procédures de
développement complètes sont documentées séparément.

## Documentation

- [Référence biomécanique](DOCS/BIOMECHANICS.md) : hypothèses, conventions,
  équations et limites du modèle.
- [Guide de développement](DOCS/DEVELOPMENT.md) : environnement, tests, CLI,
  packaging, releases et backend `biorbd`.
- [Recette de distribution](packaging/RECETTE_DISTRIBUTION.md) : contrôles à
  effectuer sur une seconde machine avant diffusion en cours.
- [Historique des versions](CHANGELOG.md).

Pour signaler un problème, joindre la version de l'application, le système
d'exploitation, la configuration utilisée et une capture dans les
[issues GitHub](https://github.com/mickaelbegon/Squat_GUI/issues).
