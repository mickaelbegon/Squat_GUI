"""Parser construction for the stable squat-gui CLI contract."""

from __future__ import annotations

import argparse

from .anthropometry import ANTHROPOMETRY_MODES
from .cli_conversion import DEFAULT_SEGMENT_ANGLES_DEG, parse_bool
from .cli_handlers import run_batch, run_condition
from .didactics import DYNAMIC_PHASE_DURATION_OPTIONS, ISOMETRIC_PHASE_DURATION_OPTIONS
from .kinematics import DEFAULT_SAMPLE_PERIOD_S


def add_condition_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared run/batch simulation options in their historical order."""
    parser.add_argument("--condition-id", default="condition_001")
    parser.add_argument("--load-percent-bw", type=float, default=0.0, help="Charge de barre en pourcentage du poids de corps (sujet 70 kg).")
    parser.add_argument("--load", type=float, help="Compatibilite: charge de barre en kg, prioritaire sur --load-percent-bw.")
    parser.add_argument("--subject-profile", choices=("homme", "femme enceinte"), default="homme")
    parser.add_argument("--bar-position", choices=("front", "back", "over-head"), default="back")
    parser.add_argument("--wedge", action="store_true", help="Ajouter une talonnette de 20 deg.")
    parser.add_argument("--shank", type=float, default=0.0, help="Variation longueur tibia en pourcent.")
    parser.add_argument("--thigh", type=float, default=0.0, help="Variation longueur cuisse en pourcent.")
    parser.add_argument("--trunk", type=float, default=0.0, help="Variation longueur tronc en pourcent.")
    parser.add_argument("--anthropometry-mode", choices=ANTHROPOMETRY_MODES, default="longueur seule", help="longueur seule conserve masses/inerties; morphotype recalibre recalcule les masses avec l'hypothese didactique documentee.")
    parser.add_argument("--duration-excentrique", type=float, choices=DYNAMIC_PHASE_DURATION_OPTIONS, default=4.0)
    parser.add_argument("--duration-isometrique", type=float, choices=ISOMETRIC_PHASE_DURATION_OPTIONS, default=2.0)
    parser.add_argument("--duration-concentrique", type=float, choices=DYNAMIC_PHASE_DURATION_OPTIONS, default=4.0)
    parser.add_argument("--frames", type=int, default=0, help=f"Nombre de frames; 0 utilise automatiquement Δt={DEFAULT_SAMPLE_PERIOD_S:.2f} s.")
    parser.add_argument("--q-segment-deg", type=float, nargs=3, default=DEFAULT_SEGMENT_ANGLES_DEG, metavar=("SHANK", "THIGH", "TRUNK"))
    parser.add_argument("--joint-angles-deg", type=float, nargs=3, metavar=("ANKLE", "KNEE", "HIP"), help="Angles articulaires finaux en degres. Prioritaire sur --q-segment-deg.")
    parser.add_argument("--torque-preset", default="anderson", help="anderson ou sportifs.")
    parser.add_argument("--max-cheville", type=float)
    parser.add_argument("--max-genou", type=float)
    parser.add_argument("--max-hanche", type=float)
    parser.add_argument("--angle-adapt", type=parse_bool, default=True)
    parser.add_argument("--velocity-adapt", type=parse_bool, default=True)
    parser.add_argument("--optimize-bar-path", action="store_true", help="Activer la stabilisation expérimentale SLSQP de la trajectoire horizontale de la barre (±5 deg, contraintes CoP).")
    parser.add_argument("--backend", choices=("auto", "analytical", "biorbd"), default="auto")


def add_export_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common CSV export options."""
    parser.add_argument("--csv-mode", choices=("standard", "full"), default="standard", help="standard exporte les variables biomécaniques essentielles; full conserve toutes les colonnes diagnostiques.")


def _add_output_arguments(parser: argparse.ArgumentParser, default_out: str) -> None:
    parser.add_argument("--out", default=default_out)
    parser.add_argument("--summary", default="", help="Résumé JSON optionnel (les métriques étudiantes sont aussi dans Excel).")
    parser.add_argument("--xlsx", default="", help="Classeur Excel global optionnel.")


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser without executing a simulation."""
    parser = argparse.ArgumentParser(description="Exporter rapidement des simulations de squat 2D.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Exporter une condition unique.")
    add_condition_arguments(run_parser)
    add_export_arguments(run_parser)
    _add_output_arguments(run_parser, "exports/squat_results.csv")
    run_parser.set_defaults(func=run_condition)
    batch_parser = subparsers.add_parser("batch", help="Exporter un lot de conditions depuis un CSV.")
    add_condition_arguments(batch_parser)
    add_export_arguments(batch_parser)
    batch_parser.add_argument("conditions", help="CSV de conditions.")
    _add_output_arguments(batch_parser, "exports/squat_batch_results.csv")
    batch_parser.set_defaults(func=run_batch)
    return parser
