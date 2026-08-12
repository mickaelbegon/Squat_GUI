# Importer les questions dans Studium/Moodle

## Option recommandée : GIFT

Le fichier `Banque_questions_Studium_GIFT.txt` contient des QCM et des questions numériques. Dans Studium, aller dans la banque de questions du cours, choisir Importer, puis sélectionner le format GIFT.

Avantages : fichier texte facile à relire, modifier, versionner et régénérer.

## Option alternative : Moodle XML

Le fichier `Banque_questions_Studium_MoodleXML.xml` contient la même banque sous forme XML Moodle. Ce format peut être préférable si l’import GIFT est trop sensible aux caractères spéciaux.

## Vérification après import

Après l’import, vérifier :

1. une question QCM;
2. une question numérique;
3. la tolérance numérique;
4. la rétroaction générale;
5. le barème et la catégorie.

## Recommandation

Créer deux quiz dans Studium :

- Quiz préparatoire : QCM001 à QCM015;
- Quiz d’analyse post-lab : QCM016 à QCM025 et NUM001 à NUM024.