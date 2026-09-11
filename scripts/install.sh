#!/usr/bin/env sh
set -eu

PACKAGE="devdoctor-workstation"
REQUESTED_VERSION="latest"
INSTALL_SOURCE="pypi"
ASSUME_YES=0
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
BASE_DIR="$DATA_HOME/devdoctor"
REPOSITORY="AxiomNode-lab/DevDoctor"

usage() {
  cat <<'EOF'
Usage: install.sh [--version VERSION] [--source pypi|github|git] [--yes]

Installs DevDoctor into a user-owned virtual environment and links
~/.local/bin/devdoctor (or $XDG_BIN_HOME/devdoctor). No sudo is used.

Sources:
  pypi    Install devdoctor-workstation from PyPI.
  github  Download the exact release wheel and SHA256SUMS from GitHub,
          verify the wheel, then install it.
  git     Install straight from the repository with pip (main, or the
          v<VERSION> tag when --version is given). Works before any PyPI
          or GitHub release exists; requires git.

The installer previews the action and asks for confirmation unless --yes is given.
A GitHub release install requires an explicit version.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version)
      [ "$#" -ge 2 ] || { echo "--version requires a value" >&2; exit 2; }
      REQUESTED_VERSION="$2"
      shift 2
      ;;
    --source)
      [ "$#" -ge 2 ] || { echo "--source requires a value" >&2; exit 2; }
      INSTALL_SOURCE="$2"
      shift 2
      ;;
    --yes|-y)
      ASSUME_YES=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$INSTALL_SOURCE" in
  pypi|github|git) ;;
  *)
    echo "Unsupported source: $INSTALL_SOURCE (use pypi, github, or git)" >&2
    exit 2
    ;;
esac

if [ "$INSTALL_SOURCE" = "git" ]; then
  git --version >/dev/null 2>&1 || {
    echo "git is required for a git source install (pip clones the repository)." >&2
    exit 1
  }
fi

if [ "$INSTALL_SOURCE" = "github" ] && [ "$REQUESTED_VERSION" = "latest" ]; then
  echo "GitHub release installs require --version VERSION." >&2
  exit 2
fi

command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required. Install Python 3.11+ with your distribution package manager." >&2
  exit 1
}

PYTHON_OK="$(python3 -c 'import sys; print(int(sys.version_info >= (3, 11)))')"
[ "$PYTHON_OK" = "1" ] || {
  echo "DevDoctor requires Python 3.11 or newer." >&2
  exit 1
}

VENV_PROBE="$(mktemp -d "${TMPDIR:-/tmp}/devdoctor-venv-check.XXXXXX")" || {
  echo "Unable to create a temporary directory for the Python venv preflight." >&2
  exit 1
}
if ! python3 -m venv "$VENV_PROBE/env" >/dev/null 2>&1; then
  rm -rf "$VENV_PROBE"
  cat >&2 <<'EOF'
Python virtual-environment support is required but is not functional.
On Debian/Ubuntu install the matching python3-venv package, then retry.
DevDoctor will not install or modify system packages automatically.
EOF
  exit 1
fi
rm -rf "$VENV_PROBE"

SPEC="$PACKAGE"
if [ "$INSTALL_SOURCE" = "git" ]; then
  GIT_REF="main"
  if [ "$REQUESTED_VERSION" != "latest" ]; then
    GIT_REF="v$REQUESTED_VERSION"
  fi
  SPEC="git+https://github.com/$REPOSITORY.git@$GIT_REF"
elif [ "$REQUESTED_VERSION" != "latest" ]; then
  SPEC="$PACKAGE==$REQUESTED_VERSION"
fi

LINK="$BIN_HOME/devdoctor"
if [ -e "$LINK" ] && [ ! -L "$LINK" ]; then
  echo "Refusing to replace non-symlink file: $LINK" >&2
  exit 1
fi

OLD_LINK_TARGET=""
if [ -L "$LINK" ]; then
  OLD_LINK_TARGET="$(readlink "$LINK" 2>/dev/null || true)"
fi

printf '%s\n' "DevDoctor install preview:" \
  "  source: $INSTALL_SOURCE" \
  "  package: $SPEC" \
  "  data directory: $BASE_DIR" \
  "  command link: $LINK" \
  "  privilege escalation: none"

if [ "$ASSUME_YES" -ne 1 ]; then
  if [ ! -t 0 ]; then
    echo "Refusing non-interactive install without --yes." >&2
    exit 2
  fi
  printf "Continue? [y/N] "
  read -r answer
  case "$answer" in
    y|Y|yes|YES) ;;
    *) echo "Cancelled. No changes made."; exit 0 ;;
  esac
fi

mkdir -p "$BASE_DIR" "$BIN_HOME" "$BASE_DIR/envs" "$BASE_DIR/versions"
LOCK_DIR="$BASE_DIR/.install.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Another DevDoctor installer is already active. Remove $LOCK_DIR only if no installer is running." >&2
  exit 1
fi

INSTALL_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
ENV_DIR="$BASE_DIR/envs/$INSTALL_ID"
DOWNLOAD_DIR="$BASE_DIR/.download-$$"
VERSION_LINK=""
OLD_VERSION_TARGET=""
ENV_CREATED=0
LINK_CHANGED=0
VERSION_LINK_CHANGED=0
ACTIVATED=0

restore_symlink() {
  target="$1"
  link="$2"
  if [ -n "$target" ]; then
    ln -sfn "$target" "$link" 2>/dev/null || true
  else
    rm -f "$link"
  fi
}

cleanup() {
  if [ "$ACTIVATED" -ne 1 ]; then
    if [ "$LINK_CHANGED" -eq 1 ]; then
      restore_symlink "$OLD_LINK_TARGET" "$LINK"
    fi
    if [ "$VERSION_LINK_CHANGED" -eq 1 ] && [ -n "$VERSION_LINK" ]; then
      restore_symlink "$OLD_VERSION_TARGET" "$VERSION_LINK"
    fi
    if [ "$ENV_CREATED" -eq 1 ] && [ -d "$ENV_DIR" ]; then
      rm -rf "$ENV_DIR"
    fi
  fi
  rm -rf "$DOWNLOAD_DIR"
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# ENV_DIR is the virtualenv's permanent path. Never move/rename it after creation;
# Python console-script shebangs embed this absolute path.
python3 -m venv "$ENV_DIR"
ENV_CREATED=1

if [ "$INSTALL_SOURCE" = "github" ]; then
  WHEEL_FILE="devdoctor_workstation-${REQUESTED_VERSION}-py3-none-any.whl"
  RELEASE_BASE="https://github.com/$REPOSITORY/releases/download/v$REQUESTED_VERSION"
  mkdir -p "$DOWNLOAD_DIR"

  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --silent --show-error \
      "$RELEASE_BASE/$WHEEL_FILE" -o "$DOWNLOAD_DIR/$WHEEL_FILE"
    curl --fail --location --silent --show-error \
      "$RELEASE_BASE/SHA256SUMS" -o "$DOWNLOAD_DIR/SHA256SUMS"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$RELEASE_BASE/$WHEEL_FILE" -O "$DOWNLOAD_DIR/$WHEEL_FILE"
    wget -q "$RELEASE_BASE/SHA256SUMS" -O "$DOWNLOAD_DIR/SHA256SUMS"
  else
    echo "curl or wget is required for a GitHub release install." >&2
    exit 1
  fi

  command -v sha256sum >/dev/null 2>&1 || {
    echo "sha256sum is required to verify a GitHub release install." >&2
    exit 1
  }

  grep "  $WHEEL_FILE\$" "$DOWNLOAD_DIR/SHA256SUMS" > "$DOWNLOAD_DIR/WHEEL.SHA256" || {
    echo "Release checksum manifest does not contain $WHEEL_FILE." >&2
    exit 1
  }
  (
    cd "$DOWNLOAD_DIR"
    sha256sum --check WHEEL.SHA256
  )
  INSTALL_SPEC="$DOWNLOAD_DIR/$WHEEL_FILE"
else
  INSTALL_SPEC="$SPEC"
fi

"$ENV_DIR/bin/python" -m pip install --no-cache-dir "$INSTALL_SPEC"
ACTUAL_VERSION="$($ENV_DIR/bin/python -c 'from importlib.metadata import version; print(version("devdoctor-workstation"))')"

if [ "$REQUESTED_VERSION" != "latest" ] && [ "$ACTUAL_VERSION" != "$REQUESTED_VERSION" ]; then
  echo "Installed version $ACTUAL_VERSION does not match requested $REQUESTED_VERSION." >&2
  exit 1
fi

# Validate the exact immutable environment before exposing it through any symlink.
"$ENV_DIR/bin/devdoctor" --version >/dev/null

VERSION_LINK="$BASE_DIR/versions/$ACTUAL_VERSION"
if [ -e "$VERSION_LINK" ] && [ ! -L "$VERSION_LINK" ]; then
  echo "Refusing to replace legacy non-symlink version path: $VERSION_LINK" >&2
  exit 1
fi
if [ -L "$VERSION_LINK" ]; then
  OLD_VERSION_TARGET="$(readlink "$VERSION_LINK" 2>/dev/null || true)"
fi

ln -sfn "$ENV_DIR" "$VERSION_LINK"
VERSION_LINK_CHANGED=1
ln -sfn "$ENV_DIR/bin/devdoctor" "$LINK"
LINK_CHANGED=1

if ! "$LINK" --version >/dev/null; then
  echo "Failed to activate the freshly validated DevDoctor environment." >&2
  exit 1
fi
ACTIVATED=1

trap - EXIT HUP INT TERM
rm -rf "$DOWNLOAD_DIR"
rmdir "$LOCK_DIR" 2>/dev/null || true

printf '%s\n' \
  "Installed DevDoctor $ACTUAL_VERSION." \
  "Environment: $ENV_DIR" \
  "Version pointer: $VERSION_LINK" \
  "Re-running the same version activates a freshly validated immutable environment." \
  "Rollback: repoint $LINK to another environment under $BASE_DIR/envs or use a version pointer under $BASE_DIR/versions."
