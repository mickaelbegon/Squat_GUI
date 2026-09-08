# Proposition — silhouettes vectorielles Canvas

## But et constat

Conserver les PNG raffinés comme rendu de référence, tout en disposer d'une
silhouette vectorielle lisible et légère pour les interactions rapides. Cette
proposition ne remplace aucun asset ni le chemin de rendu actuel.

Les quatre JSON de `assets/side_view_segments/` sont déjà le format le plus
proche de Tkinter Canvas : ils portent des sommets locaux, des ancrages
articulaires et des chemins ouverts ou fermés. `segment_shapes.draw_segment`
les transforme directement et appelle `create_polygon` ou `create_line`.
`scene_pose.draw_skeleton` les utilise déjà comme repli si les sprites Pillow
ne sont pas disponibles (et pour l'aperçu de glissement). Les PNG sont, eux,
mis à l'échelle puis tournés par Pillow avant `create_image`.

Les SVG actuels sont des sorties Matplotlib de prévisualisation : ils
contiennent notamment des `path` cubiques (`C`), des `clipPath` et des groupes.
Ils sont utiles comme référence visuelle, mais ne sont pas lus à l'exécution et
ne constituent pas un sous-ensemble SVG Canvas directement exploitable.

## Direction artistique proposée

Une silhouette pédagogique, anatomiquement évocatrice à taille écran, plutôt
qu'une vectorisation automatique des PNG : contour externe net, volumes simples
et seulement deux détails internes par membre. Cette cohérence est plus robuste
au pivotement et au redimensionnement qu'un grand nombre de petits tracés.

| Élément | Proposition |
| --- | --- |
| Peau / vêtements | Deux thèmes sobres : peau `#E6B08B` + ombre `#C98567`, ou tenue `#5A7894` + ombre `#38546D`. La sélection de thème reste une option future, pas une donnée biomécanique. |
| Contour | `#24313A`, 1.5 à 2 px, `round` aux jonctions et extrémités. À faible échelle, le contour seul maintient la lisibilité. |
| Ombre | Un unique polygone fermé, plus sombre et légèrement transparent si la plateforme le permet ; sinon une couleur opaque atténuée. Pas de dégradé. |
| Détails | Ligne ouverte de tibia / quadriceps et, au besoin, petite forme de mollet ou fessier. Aucun détail facial ni texture. |
| Articulations | Les marqueurs Canvas existants restent au-dessus de la silhouette ; les nouvelles formes ne doivent jamais déplacer les ancrages. |

Composition par segment, de l'arrière vers l'avant : (1) ombre éventuelle,
(2) contour principal rempli, (3) accent interne, (4) bras/barre dans le segment
tronc. Le pied conserve une semelle très fine et une pointe arrondie ; le tibia
reste volontairement plus rectiligne, la cuisse plus fuselée, et le tronc se
compose d'un bassin, torse, tête et bras simplifiés. Les quatre ancrages actuels
restent la source de vérité : cheville, genou, hanche et épaule. Les variantes
de tronc (profil et position de barre) doivent être des calques de silhouette
partageant exactement les mêmes ancrages, jamais des poses complètes.

## Sous-ensemble SVG compatible

Pour de nouveaux dessins sources, limiter chaque fichier à un `svg` avec
`viewBox`, des `path` et éventuellement `polygon`, `polyline`, `line` ou
`circle`. Conserver les coordonnées dans l'espace local actuel : origine sur
l'ancrage distal, axe local Y vers le proximal, longueur de référence égale à
1 pour tibia/cuisse/tronc. Le pied peut conserver ses proportions de référence
(`1.07` dans le code actuel).

- Autoriser : `M`, `L`, `H`, `V`, `Z`; `Q` et `C` seulement si le convertisseur
  les échantillonne de façon déterministe (6 à 10 segments par courbe).
- Éviter : `A`, `S`, `T`, transformations SVG, `use`, CSS externe, texte,
  images embarquées, filtres, `clipPath`, masques, motifs et dégradés.
- Utiliser des couleurs littérales (`fill`, `stroke`, `stroke-width`) par
  calque, sans dépendre de l'héritage CSS. Un ordre DOM explicite définit
  l'ordre de peinture.
- N'utiliser que des chemins fermés non auto-intersectants pour les remplissages.
  Les trous ne sont pas portables avec `create_polygon`; les représenter par un
  calque de la couleur du fond seulement si nécessaire, ce qui est déconseillé.

Cette discipline évite d'introduire un moteur SVG dans l'application et produit
des formes faciles à relire et à versionner.

## Conversion SVG vers polygones Canvas

Le runtime ne devrait pas parser du SVG. Une petite conversion de développement
sans dépendance lourde suffit : `xml.etree.ElementTree` lit le SVG, un parseur
de commandes minimal transforme chaque chemin en points, puis écrit un JSON
dans le schéma déjà consommé par `draw_segment`.

```text
SVG source strict → validation d'ancrages et de commandes → échantillonnage Q/C
→ {paths, joints, style} JSON → transform_point → create_polygon/create_line
```

Le JSON généré devrait associer à chaque chemin son rôle (`fill`, `shadow`,
`detail`, `bar`) et son style local. Le renderer actuel applique un style unique
par segment ; le prototype peut donc commencer par un contour + un détail dans
ce format existant. Une deuxième étape, seulement si les ombres sont retenues,
ajouterait des styles par chemin tout en gardant les mêmes primitives Canvas.
Pour une courbe de Bézier, le point `B(t)` est évalué pour `t = 0..1` avec un
nombre fixe de pas : c'est léger, déterministe et indépendant de Pillow.

La conversion doit refuser (avec un message précis) toute commande ou tout
élément hors sous-ensemble, plutôt que produire une silhouette partiellement
fausse. Un test unitaire vérifie : ancrages présents, chemins fermés valides,
absence de NaN, et distance de référence distal-proximal égale à 1 pour les
segments longs.

## Niveaux de fidélité

| Niveau | Contenu | Usage recommandé |
| --- | --- | --- |
| V0 — geste | Contour unique + barre + marqueurs d'articulation | Glissement à très haute réactivité ; correspond à la capacité actuelle. |
| V1 — pédagogique | Contour, une ombre et une ou deux lignes anatomiques | Alternative vectorielle par défaut lorsque les PNG ne sont pas désirés. |
| V2 — raffiné | V1 + variantes de tronc et détails localisés (coiffure/tenue très sobres) | Choix explicite de l'utilisateur ; ne vise pas le photoréalisme des PNG. |
| PNG raffiné | Assets existants, cache de transformations | Référence visuelle finale et qualité maximale. |

V1 est le meilleur compromis : environ 12 à 24 sommets pour un contour et 3 à
6 pour un détail par segment. Au-delà, le gain esthétique est faible à la taille
du Canvas et complique l'entretien des formes.

## Limites assumées de Tkinter Canvas

Tkinter Canvas dessine très bien polygones, lignes, ovales et texte, mais n'est
pas un renderer SVG : pas de dégradé vectoriel, de masque, de découpage complexe,
de filtre, de composition alpha avancée ni de texte le long d'un chemin. Les
ombres proposées sont donc des polygones plats; l'antialiasing dépend de Tk et
du système. Les libellés restent des objets `create_text` existants, jamais du
texte converti dans une silhouette. Une silhouette vectorielle offre surtout un
gain de coût de transformation et de stabilité géométrique, pas une copie exacte
des textures/anatomies des PNG raffinés.

## Plan de prototype réversible

1. Dessiner hors runtime un `thigh_v1.svg` strict et son JSON généré, en
   conservant `thigh.json` intact; comparer à l'asset actuel à plusieurs angles.
2. Ajouter un convertisseur de développement et des tests de validation du
   sous-ensemble SVG, sans l'appeler depuis Tkinter.
3. Ajouter, sous un indicateur de rendu expérimental, le support de styles par
   chemin nécessaire à l'ombre; vérifier que les coordonnées articulaires et
   la dynamique ne changent pas.
4. Produire les autres segments et variantes de tronc, puis effectuer une revue
   visuelle Windows aux résolutions déjà listées dans `DOCS/DEVELOPMENT.md`.
5. Ne proposer le mode V1 aux utilisateurs qu'après comparaison visuelle avec
   les PNG raffinés et mesure de la réactivité pendant le glissement.

Le rollback est immédiat : garder les JSON actuels et les PNG comme chemins
indépendants, et retirer simplement l'indicateur expérimental.
