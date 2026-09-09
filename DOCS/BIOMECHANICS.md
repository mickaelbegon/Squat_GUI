# Référence biomécanique

Ce document décrit les conventions et hypothèses scientifiques de Squat GUI.
Le modèle est didactique : il facilite des comparaisons contrôlées, mais ne
constitue pas un modèle clinique validé ni une prédiction de performance.

## Modèle et repère

Le corps est représenté dans le plan sagittal par quatre segments combinant les
côtés gauche et droit : pied, jambe, cuisse et tronc-tête-bras. La barre est une
masse ponctuelle attachée au segment supérieur.

- `+x` est horizontal vers l'avant et `+y` vertical vers le haut.
- Les calculs utilisent les mètres, secondes, kilogrammes, newtons et radians.
- Le GUI et les exports pédagogiques affichent les angles en degrés.
- Les orientations absolues sont mesurées depuis `+x`, dans le sens
  anti-horaire positif.
- La flexion dorsale de cheville est positive, la flexion de genou conserve la
  convention historique négative et la flexion de hanche est positive lorsque
  le tronc s'oriente vers l'avant relativement à la cuisse.

## Anthropométrie

La référence est un sujet de 70 kg et 1,70 m. Les masses, centres de masse et
rayons de giration des membres inférieurs suivent les paramètres bilatéraux de
Dempster/Winter : 2,9 % de la masse corporelle pour les pieds, 9,3 % pour les
jambes et 20,0 % pour les cuisses. Référence : Winter, D. A. (2009),
*Biomechanics and Motor Control of Human Movement*, 4e édition, Wiley.

La chaîne est construite du distal vers le proximal. La jambe va de la cheville
au genou et la cuisse du genou à la hanche ; la fraction tabulée depuis
l'articulation proximale est donc convertie en `1 - 0,433 = 0,567`.

Deux modes de variation de longueur sont proposés :

- `longueur seule` conserve les masses et inerties de référence afin d'isoler
  l'effet géométrique ;
- `morphotype recalibré` applique une hypothèse didactique de densité linéique
  constante, renormalise les masses à la masse corporelle, puis recalcule
  `I = m(kL)^2`.

Le second mode est une analyse de sensibilité, pas une régression de population.

## Profils et positions de barre

Les prises `front`, `back` et `over-head` déplacent la barre et le centre de
masse du segment supérieur pour représenter la position des bras. La barre reste
ponctuelle : sa longueur et son inertie propre ne sont pas modélisées.

Le profil `femme enceinte` est un scénario initial non clinique. Il conserve une
masse corporelle totale de 70 kg, déplace le CoM du segment supérieur de 0,060 m
vers l'avant et multiplie son inertie par 1,18. Ces coefficients doivent être
recalibrés avant toute interprétation appliquée à une population enceinte.

## Géométrie du pied, cale et posture debout

La base géométrique s'étend du talon aux orteils. La zone fonctionnelle va de la
projection de la cheville à la tête des métatarsiens, placée à 85 % du segment
talon-orteils faute d'articulation métatarsienne séparée.

La cale relève le talon de 20°. Le contact reste défini sur un sol horizontal :
il s'agit d'une variation de configuration, pas d'un modèle complet de contact
pied-cale. La posture debout est ajustée automatiquement par un faible angle
commun aux segments. Le genou et la hanche restent en extension et la projection
statique du CoM est centrée dans la zone fonctionnelle. Cet endpoint dépend de
l'anthropométrie, de la charge et de la position de barre, mais pas de la posture
basse choisie.

## Trajectoire

La descente et la montée utilisent une interpolation quintique de type Yeadon :

```text
s(x) = 6x^5 - 15x^4 + 10x^3
```

Elle impose des vitesses et accélérations nulles aux positions extrêmes. Une
phase isométrique peut être insérée en position basse. Le pas temporel par défaut
est constant, `Δt = 0,05 s`, et les deux extrémités sont incluses.

La trajectoire de barre affichable est une observation de la trajectoire calculée
entre les positions haute et basse. Par défaut, elle n'impose aucune contrainte
de verticalité au mouvement.

L'option **Stabiliser barre (expérimental)** ajuste avec SLSQP les trois angles
articulaires de la posture basse, dans un intervalle de ±5° autour
de la demande. La loi quintique reste inchangée. L'objectif combine l'intégrale
discrète de la vitesse horizontale de la barre au carré, un faible ancrage sur la
verticale de la position haute et une régularisation des corrections. Les
contraintes sont vérifiées à chaque échantillon : CoP dans la zone fonctionnelle,
GRF verticale positive, limites articulaires et hauteur de hanche basse à ±1 cm.
Une solution infaisable ou l'absence de SciPy laisse strictement la trajectoire
d'origine en place et produit un diagnostic plutôt qu'un résultat non conforme.

## Centres de masse et forces externes

Le CoM global est la moyenne pondérée des CoM segmentaires et de la barre :

```text
x_COM = somme(m_i x_i) / somme(m_i)
y_COM = somme(m_i y_i) / somme(m_i)
```

Les vitesses et accélérations sont obtenues par dérivation analytique de la
géométrie. Le bilan de forces utilise `g = 9,80665 m/s²` :

```text
GRF + poids = masse_totale × accélération_COM
```

Avec le backend analytique, le CoP provient du bilan du moment de la résultante
de contact. Avec `biorbd`, le point est nommé ZMP : il vient de
`CalcZeroMomentPoint` si disponible, sinon du bilan dynamique de secours. Les
exports conservent le libellé et la provenance pour ne pas confondre silencieusement
CoP et ZMP.

## Dynamique inverse

Le backend analytique applique les équations segmentaires 2D. Le backend
optionnel `biorbd` utilise `InverseDynamics`. La décomposition canonique à pied
fixé est :

```text
total = M(q) qddot + termes dépendant de qdot + gravité
```

Le moment du contact externe est exporté séparément comme diagnostic et n'est
pas soustrait du total utilisé pour les puissances ou ratios d'effort. Le résidu
de reconstruction est également exporté.

## Estimation fémoro-patellaire expérimentale

Squat GUI fournit une estimation didactique de la charge fémoro-patellaire à
partir de deux variables déjà calculées : la flexion du genou et le moment net
d'extension issu de la dynamique inverse. Il s'agit d'un modèle analytique 2D
générique, et non d'une mesure du cartilage ou d'une prédiction de douleur.

Le modèle représente les deux membres inférieurs ensemble. Sous l'hypothèse
d'un squat bilatéral symétrique, le moment extenseur attribué à un genou est :

```text
M_ext,genou = max(0, M_genou) / 2
```

Un moment net négatif n'est pas transformé en force compressive : il est ramené
à zéro. Le bras de levier effectif du quadriceps `r_Q`, en mètres, dépend de la
flexion positive `θ` du genou, en degrés :

```text
r_Q = (0,036 θ + 3,0) / 100       pour 0° <= θ < 30°
r_Q = (-0,043 θ + 5,4) / 100      pour 30° <= θ < 60°
r_Q = (-0,027 θ + 4,3) / 100      pour 60° <= θ < 90°
r_Q = 2,0 / 100                   pour θ >= 90°
```

La force du quadriceps, l'angle du mécanisme patellaire et la force de réaction
fémoro-patellaire par genou sont ensuite estimés par :

```text
F_Q = M_ext,genou / r_Q
β = 30,46 + 0,53 θ
F_PF = 2 F_Q sin(β / 2)
```

La relation linéaire utilisée pour `β` reprend la géométrie sagittale publiée
par Matthews, Sonstegard et Henke (1977). Les équations restent ici une
approximation générique de type poulie sans frottement, et non une
reconstruction personnalisée de la patella.

Dans le sinus, `β` est converti en radians. L'aire de contact générique et la
contrainte moyenne estimée sont :

```text
A_PF = 0,0781 θ² + 0,6763 θ + 151,75       [mm²]
σ_PF = F_PF / A_PF                         [N/mm² = MPa]
```

L'interface propose la courbe `contrainte femoro-patellaire`. L'animation
affiche `PF/genou`, et les exports fournissent le moment par côté, le bras de
levier, les forces, l'aire, la contrainte et leur statut de validité. La feuille
Excel `Synthèse` contient notamment le pic de contrainte, son temps, sa frame,
l'angle correspondant et le nombre de frames extrapolées.

### Hypothèses et limites spécifiques

- Le partage droite/gauche est fixé à 50/50. Une asymétrie réelle n'est pas
  observable dans ce modèle sagittal.
- Le moment de dynamique inverse est net. Sans EMG ni optimisation musculaire,
  la cocontraction des ischiojambiers et du gastrocnémien n'est pas estimée ;
  la force réelle du quadriceps peut donc être supérieure.
- Le bras de levier, le mécanisme patellaire et l'aire de contact sont des
  régressions génériques. La géométrie individuelle, le suivi médial-latéral,
  la patella alta, la dysplasie et les lésions cartilagineuses sont absents.
- La contrainte calculée est une moyenne `force/aire`, pas la contrainte locale
  maximale dans le cartilage.
- La normalisation `F_PF / poids corporel` utilise le poids du sujet sans la
  barre, conformément à l'usage biomécanique courant. La charge externe agit
  néanmoins sur le moment du genou et donc sur `F_PF`.
- La plage 0–90° est indiquée comme plage directe. Au-delà de 90°, le calcul est
  conservé pour explorer le squat profond, mais chaque valeur est explicitement
  marquée `extrapolation_flexion_profonde`. En flexion profonde, le contact se
  répartit différemment entre les facettes et l'aire ne suit pas nécessairement
  la régression utilisée ici.
- Aucun seuil de sécurité, de douleur ou de lésion n'est appliqué. Les valeurs
  servent à comparer des conditions simulées sous les mêmes hypothèses.

Références principales :

- Matthews, Sonstegard et Henke (1977), [*Load bearing characteristics of the
  patello-femoral joint*](https://doi.org/10.3109/17453677708989740) ;
- van Eijden et coll. (1986), [*A mathematical model of the patellofemoral
  joint*](https://doi.org/10.1016/0021-9290(86)90154-5) ;
- Wallace et coll. (2002), [squat avec et sans charge
  externe](https://doi.org/10.2519/jospt.2002.32.4.141) ;
- Salem et Powers (2001), [squats de 70 à
  110°](https://doi.org/10.1016/S0268-0033(01)00017-1) ;
- Freedman, Sheehan et Lerner (2015), [aire de contact IRM jusqu'à
  140°](https://doi.org/10.1016/j.knee.2015.06.012).

## Capacité couple-angle-vitesse

La capacité active optionnelle suit Anderson, Madigan et Nussbaum (2007),
doi:`10.1016/j.jbiomech.2007.03.022`. Le facteur angle est :

```text
facteur_angle = max(0, cos(C2 × (angle - C3)))
```

La vitesse signée distingue les régimes concentrique, excentrique et
isométrique à partir de la puissance `couple × vitesse`. Les couples passifs ne
sont pas ajoutés. La capacité affichée vaut :

```text
capacité = maximum saisi × facteur_angle × facteur_vitesse
utilisation = abs(couple requis) / capacité
```

Le preset `Anderson actif x2` additionne les deux membres du modèle 2D. Le preset
`Sportifs` combine plusieurs publications et reste une proposition de travail,
pas une norme physiologique homogène. Par défaut, le preset `Sportifs` est retenu
et les modulations angle-vitesse Anderson sont désactivées : les deux facteurs
restent donc neutres (= 1). Elles restent activables séparément dans l'interface,
les réglages sauvegardés et la CLI.

## Limites d'interprétation

- Modèle plan à segments rigides, pied fixé et barre ponctuelle.
- Pas de mouvement asymétrique, de déformation du pied ni de contact 3D.
- Profil de grossesse non calibré cliniquement.
- Zone fonctionnelle simplifiée sans articulation des orteils.
- Capacités musculaires actives issues de références populationnelles limitées.
- Une alerte signale une incohérence dans les hypothèses du modèle, pas une
  conclusion sur la sécurité d'une personne réelle.

Les paramètres effectivement utilisés, leur provenance et les marges d'appui
sont disponibles dans les couches d'affichage et les exports CSV/Excel/JSON.
