"""Human-readable metadata for the stable export contract."""

from __future__ import annotations

from .export_contract import ColumnDefinition, JOINTS


DESCRIPTION_OVERRIDES = {
    "schema_version": "Version du contrat d'export Squat GUI.",
    "condition_id": "Identifiant stable de la condition simulée.",
    "frame": "Indice entier de l'échantillon, à partir de zéro.",
    "time_s": "Temps physique écoulé depuis le début de la simulation.",
    "delta_time_s": "Pas de temps local entre échantillons adjacents.",
    "normalized_time_percent": "Temps normalisé sur la durée totale du mouvement.",
    "phase": "Phase du mouvement: excentrique, isométrique ou concentrique.",
    "backend": "Backend ayant effectivement produit les résultats.",
    "frames": "Nombre total d'échantillons de la condition.",
    "support_point_label": "Nature du point d'appui exporté: CoP ou ZMP.",
    "support_point_source": "Méthode exacte utilisée pour calculer le point d'appui.",
    "contact_source": "Méthode effectivement utilisée pour calculer le diagnostic de contact externe.",
    "support_point_x_m": "Abscisse du CoP ou ZMP sur le plan du sol.",
    "torque_body_mass_normalized_Nm_kg": "Moment articulaire divisé par la masse corporelle du sujet.",
    "squat_com_x_m": "Abscisse moyenne du CoM pendant la phase isométrique; à défaut, valeur à la hauteur minimale du CoM.",
    "squat_cop_x_m": "Abscisse moyenne du point d'appui CoP/ZMP pendant la phase isométrique; à défaut, valeur à la hauteur minimale du CoM.",
    "zmp_x_min_m": "Abscisse minimale du point d'appui CoP/ZMP sur la trajectoire.",
    "zmp_x_max_m": "Abscisse maximale du point d'appui CoP/ZMP sur la trajectoire.",
    "zmp_excursion_m": "Étendue max-min du point d'appui CoP/ZMP sur la trajectoire.",
    "zmp_outside_support_frames": "Nombre de frames où le point d'appui sort de la base fonctionnelle.",
    "zmp_outside_support_percent": "Pourcentage de frames où le point d'appui sort de la base fonctionnelle.",
    "cop_outside_foot_frames": "Nombre de frames où le point d'appui sort de la base géométrique du pied.",
    "cop_outside_foot_percent": "Pourcentage de frames où le point d'appui sort de la base géométrique du pied.",
    "over_limit_frames": "Nombre de frames où au moins une demande articulaire dépasse la capacité active.",
    "peak_grf_y_N": "Valeur absolue maximale de la force de réaction verticale.",
    "peak_abs_torque_Nm": "Valeur absolue maximale du moment articulaire.",
    "peak_abs_torque_body_mass_normalized_Nm_kg": "Valeur absolue maximale du moment articulaire normalisé par la masse corporelle.",
    "peak_abs_power_W": "Valeur absolue maximale de la puissance articulaire.",
    "peak_utilization_ratio": "Valeur maximale du ratio demande/capacité U.",
    "peak_utilization_percent": "Valeur maximale de U exprimé en pourcentage.",
    "maximum_utilization_ratio": "Maximum de U parmi toutes les articulations et frames.",
    "maximum_utilization_percent": "Maximum de U exprimé en pourcentage.",
    "limiting_joint": "Articulation associée au maximum de U.",
    "limiting_frame": "Frame associée au maximum de U.",
    "limiting_time_s": "Temps associé au maximum de U.",
    "limiting_phase": "Phase associée au maximum de U.",
    "exceeds_capacity": "Vrai si une demande articulaire dépasse la capacité active.",
    "undefined_capacity_events": "Nombre de demandes non nulles pour lesquelles la capacité active est nulle ou indéfinie.",
    "weight_magnitude_N": "Norme du poids total, calculée comme masse totale multipliée par g.",
    "dynamic_moment_z_Nm": "Dérivée du moment cinétique autour de l'axe z global.",
    "max_available_Nm": "Capacité de couple actif selon les facteurs angle et vitesse sélectionnés; elle n'inclut pas le couple passif.",
    "capacity_base_torque_Nm": "Amplitude de couple de base avant facteurs angle-vitesse; sa provenance est donnée par torque_preset et les colonnes max_*_Nm de la condition.",
    "capacity_angle_rad": "Angle fourni à Anderson: dorsiflexion/flexion positive; la flexion du genou Squat_GUI est donc inversée.",
    "capacity_angular_velocity_rad_s": "Vitesse dans la direction d'action du groupe testé; positive concentrique, négative excentrique.",
    "capacity_angle_factor": "Multiplicateur couple-angle actif d'Anderson.",
    "capacity_velocity_factor": "Multiplicateur couple-vitesse actif d'Anderson.",
    "capacity_regime": "Régime déduit de la vitesse de capacité: concentrique, excentrique ou isométrique.",
    "capacity_regime_source": "Règle utilisée pour relier vitesse, couple, puissance et régime de capacité.",
    "capacity_angle_in_domain": "Vrai si l'angle appartient au lobe positif de la relation active d'Anderson.",
    "capacity_model": "Nom du modèle de capacité effectivement appliqué.",
    "capacity_source": "Référence primaire des paramètres de capacité.",
    "capacity_defined": "Vrai si la capacité active est strictement positive et U calculable.",
    "utilization_ratio": "U = valeur absolue du couple requis divisée par la capacité active disponible.",
    "utilization_percent": "Utilisation demande/capacité U exprimée en pourcentage.",
    "utilization_exceeds_capacity": "Vrai si U > 1, ou si un couple non nul est requis alors que la capacité active est nulle.",
    "effort_percent": "Alias de compatibilité de utilization_percent.",
    "inverse_dynamics_total_Nm": "Couple de dynamique inverse du modèle à pied fixé, reconstruit par M(q)qddot + termes dépendant de qdot + gravité.",
    "mass_acceleration_Nm": "Terme M(q)qddot projeté dans la convention des moments articulaires.",
    "velocity_dependent_Nm": "Termes de dynamique inverse dépendant de qdot, isolés à qddot nul.",
    "gravity_Nm": "Terme gravitaire de dynamique inverse, évalué à qdot=qddot=0.",
    "external_contact_effect_Nm": "Effet signé du moment de GRF: opposé de la colonne legacy contact_Nm; hors reconstruction du modèle contraint à pied fixé.",
    "inverse_dynamics_reconstruction_residual_Nm": "Résidu total - [M(q)qddot + vitesse + gravité]; attendu nul à la tolérance numérique.",
    "segment": "Nom canonique du segment ou de la barre.",
    "mass_kg": "Masse effectivement utilisée pour le segment.",
    "mass_fraction_body": "Fraction de la masse corporelle effectivement attribuée au segment; sans objet pour la barre.",
    "length_m": "Longueur effectivement utilisée pour le segment.",
    "com_fraction": "Position longitudinale du CoM en fraction de longueur segmentaire.",
    "com_transverse_offset_m": "Décalage transverse du CoM dans le repère segmentaire.",
    "radius_of_gyration_fraction": "Rayon de giration en fraction de longueur segmentaire.",
    "inertia_kg_m2": "Moment d'inertie planaire effectivement utilisé.",
    "anthropometry_mode": "Mode de sensibilité anthropométrique sélectionné pour la condition.",
    "anthropometry_scaling_rule": "Règle exacte reliant variations de longueur, masses et inerties.",
    "scaling_mode": "Mode anthropométrique appliqué à cette ligne segmentaire.",
    "scaling_rule": "Règle de recalibrage effectivement appliquée à cette ligne segmentaire.",
    "attachment_anterior_offset_m": "Décalage antérieur de l'attache de barre relativement à l'épaule.",
    "attachment_longitudinal_offset_m": "Décalage longitudinal de l'attache de barre relativement à l'épaule.",
}

LEGACY_COLUMNS = {
    "cop_x_m",
    "zmp_posterior_limit_m",
    "zmp_anterior_limit_m",
    "zmp_in_support",
    "cop_in_foot",
    "contact_Nm",
    "inertial_nonlinear_Nm",
    "effort_percent",
}


def _unit(column: str) -> str:
    suffixes = (
        ("_kg_m2", "kg·m²"),
        ("_kg_m", "kg·m"),
        ("_Nm_kg", "N·m/kg"),
        ("_deg_s2", "deg/s²"),
        ("_rad_s", "rad/s"),
        ("_rad", "rad"),
        ("_m_s2", "m/s²"),
        ("_deg_s", "deg/s"),
        ("_m_s", "m/s"),
        ("_Nm", "N·m"),
        ("_N", "N"),
        ("_kg", "kg"),
        ("_deg", "deg"),
        ("_m", "m"),
        ("_W", "W"),
        ("_percent", "%"),
        ("_fraction", "1"),
    )
    for suffix, unit in suffixes:
        if column.endswith(suffix):
            return unit
    return "1"


def _sign_convention(column: str) -> str:
    if "orientation_deg" in column:
        return "positif antihoraire depuis l'axe global +x"
    if any(
        token in column for token in ("_x_", "_vx_", "_ax_", "anterior", "posterior")
    ):
        return "+x vers l'avant; une marge positive indique l'intérieur de la limite"
    if any(token in column for token in ("_y_", "_vy_", "_ay_")):
        return "+y vers le haut"
    if any(
        token in column
        for token in (
            "torque",
            "moment",
            "contact",
            "mass_acceleration",
            "velocity_dependent",
            "gravity_Nm",
            "inverse_dynamics",
        )
    ):
        return "positif selon la convention de dynamique inverse documentée; axe +z hors du plan"
    if "power" in column:
        return "positive pour une puissance articulaire génératrice, négative pour absorbante"
    if "capacity_angular_velocity" in column:
        return "positive concentrique, négative excentrique pour le groupe musculaire modélisé"
    if any(
        token in column for token in ("angle_deg", "velocity_deg", "acceleration_deg")
    ):
        return "angles articulaires relatifs selon la convention cinématique documentée"
    return "sans objet"


def column_definition(column: str) -> ColumnDefinition:
    """Return the dictionary entry for a canonical or legacy column."""
    description = DESCRIPTION_OVERRIDES.get(column)
    if description is None:
        for joint in JOINTS:
            prefix = f"{joint}_"
            if column.startswith(prefix):
                description = DESCRIPTION_OVERRIDES.get(column[len(prefix) :])
                if description is not None:
                    description = f"{joint.capitalize()}: {description}"
                break
    if description is None:
        description = (
            column.replace("_", " ")
            .replace("com", "CoM")
            .replace("grf", "GRF")
            .capitalize()
            + "."
        )
    return ColumnDefinition(
        unit=_unit(column),
        definition=description,
        sign_convention=_sign_convention(column),
        status=(
            "compatibilité legacy"
            if column in LEGACY_COLUMNS
            or any(column.endswith(f"_{legacy}") for legacy in LEGACY_COLUMNS)
            else "canonique"
        ),
    )
