#!/usr/bin/env bash
# JobPilot installer for macOS and Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/dheerajkarwasra/jobpilot/main/install.sh | bash
#
# Options (environment variables):
#   JOBPILOT_REPO      GitHub repo to install from      (default dheerajkarwasra/jobpilot)
#   JOBPILOT_REF       branch or tag                     (default main)
#   JOBPILOT_DIR       where the code and venv live      (default ~/.jobpilot)
#   JOBPILOT_EXTRAS    pip extras, e.g. "gsheets"        (default none)
#   JOBPILOT_NO_SETUP  set to 1 to skip the setup wizard
#
# Re-running the installer updates JobPilot. Your workspace (profile, resume,
# tracker, secrets) lives somewhere else and is never touched.
set -euo pipefail

REPO="${JOBPILOT_REPO:-dheerajkarwasra/jobpilot}"
REF="${JOBPILOT_REF:-main}"
DIR="${JOBPILOT_DIR:-$HOME/.jobpilot}"
EXTRAS="${JOBPILOT_EXTRAS:-}"
BIN_DIR="$HOME/.local/bin"

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# 1. Python 3.9 or newer
PY=""
for cand in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PY="$(command -v "$cand")"; break
  fi
done
[ -n "$PY" ] || die "Python 3.9 or newer is needed. Install it (macOS: brew install python, Ubuntu: sudo apt install python3 python3-venv) and run this again."
"$PY" -c 'import venv' 2>/dev/null || die "Python venv module missing. On Ubuntu or Debian run: sudo apt install python3-venv"
say "Using $("$PY" --version) at $PY"

# 2. Get the code. Use the local checkout if the script runs from one.
SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
mkdir -p "$DIR"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/pyproject.toml" ] && grep -q 'name = "jobpilot"' "$SCRIPT_DIR/pyproject.toml"; then
  SRC="$SCRIPT_DIR"
  say "Installing from local folder $SRC"
elif command -v git >/dev/null 2>&1; then
  SRC="$DIR/src"
  if [ -d "$SRC/.git" ]; then
    say "Updating $SRC"
    git -C "$SRC" fetch --depth 1 origin "$REF" && git -C "$SRC" checkout -q FETCH_HEAD
  else
    say "Downloading github.com/$REPO ($REF)"
    rm -rf "$SRC"
    git clone -q --depth 1 --branch "$REF" "https://github.com/$REPO.git" "$SRC"
  fi
else
  SRC="$DIR/src"
  say "Downloading github.com/$REPO ($REF) as an archive"
  rm -rf "$SRC" && mkdir -p "$SRC"
  curl -fsSL "https://codeload.github.com/$REPO/tar.gz/$REF" | tar -xz -C "$SRC" --strip-components 1
fi

# 3. Virtual environment and package
if [ ! -x "$DIR/venv/bin/python" ]; then
  say "Creating virtual environment in $DIR/venv"
  "$PY" -m venv "$DIR/venv"
fi
"$DIR/venv/bin/python" -m pip install -q --upgrade pip
TARGET="$SRC"
[ -n "$EXTRAS" ] && TARGET="$SRC[$EXTRAS]"
say "Installing JobPilot"
"$DIR/venv/bin/python" -m pip install -q --upgrade "$TARGET"

# 4. Put `jobpilot` on PATH
mkdir -p "$BIN_DIR"
ln -sf "$DIR/venv/bin/jobpilot" "$BIN_DIR/jobpilot"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    RC="$HOME/.bashrc"
    case "${SHELL:-}" in */zsh) RC="$HOME/.zshrc" ;; esac
    if ! grep -qs 'jobpilot installer' "$RC"; then
      printf '\n# added by jobpilot installer\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$RC"
      warn "Added ~/.local/bin to PATH in $RC. Open a new terminal or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
    export PATH="$BIN_DIR:$PATH"
    ;;
esac
say "Installed $("$BIN_DIR/jobpilot" --version)"

# 5. Setup wizard. Read answers from the terminal even when piped from curl.
if [ "${JOBPILOT_NO_SETUP:-0}" = "1" ]; then
  say "Skipping setup. Run 'jobpilot setup' when ready."
elif [ -r /dev/tty ] && [ -w /dev/tty ]; then
  say "Starting setup. You can re-run it any time with: jobpilot setup"
  "$BIN_DIR/jobpilot" setup < /dev/tty
else
  say "No terminal found. Run 'jobpilot setup' to finish."
fi
