#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-/tmp/squat_gui_pyinstaller}"
PYTHON_BIN="${PYTHON_BIN:-python}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python introuvable: $PYTHON_BIN"
  echo "Activez l'environnement conda ou relancez avec PYTHON_BIN=/chemin/vers/python."
  exit 1
fi

ensure_python_module() {
  local module_name="$1"
  local package_name="$2"
  if ! "$PYTHON_BIN" -c "import ${module_name}" >/dev/null 2>&1; then
    echo "Module ${module_name} absent; installation de ${package_name}..."
    "$PYTHON_BIN" -m pip install --no-build-isolation "$package_name"
  fi
}

ensure_python_module PyInstaller pyinstaller
ensure_python_module PIL pillow

"$PYTHON_BIN" -m PyInstaller --clean --noconfirm packaging/squat_gui.spec
SQUAT_GUI_SMOKE_TEST=1 "dist/Squat GUI/Squat GUI"

cat <<'MSG'

Build termine.

Sorties principales:
- dist/Squat GUI.app
- dist/Squat GUI/

Pour distribuer aux etudiants sur macOS:
1. compresser "dist/Squat GUI.app" en .zip;
2. envoyer le .zip;
3. l'etudiant dezippe puis ouvre "Squat GUI.app".

Si macOS bloque l'ouverture car l'application n'est pas signee:
clic droit sur "Squat GUI.app" > Ouvrir > Ouvrir.
MSG
