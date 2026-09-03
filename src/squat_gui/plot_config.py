"""Shared labels and colours for the plot controllers."""

DETAILED_PLOT_CHOICE = "couples detailles"
SYNCHRONIZED_KINEMATICS_CHOICE = "cinematique synchronisee"

TORQUE_COMPONENT_KEYS = {
    "M(q) qddot": "mass_acceleration",
    "termes qdot": "velocity",
    "gravité": "gravity",
    "contact externe (signé)": "external_contact",
    "total ID": "total",
}

PLOT_CHOICES = [
    "cinematique articulaire",
    "centre de masse",
    SYNCHRONIZED_KINEMATICS_CHOICE,
    "force reaction sol",
    "couples articulaires",
    "couples normalises",
    DETAILED_PLOT_CHOICE,
    "puissances articulaires",
]

JOINT_COLORS = {
    "cheville": "#2e7d54",
    "genou": "#b46d22",
    "hanche": "#6d5ea8",
    "horizontal": "#2a8ca6",
    "vertical": "#8a5a22",
}
