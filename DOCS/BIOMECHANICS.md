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
entre les positions haute et basse. Elle n'impose actuellement aucune contrainte
de verticalité au mouvement.

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
pas une norme physiologique homogène.

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
