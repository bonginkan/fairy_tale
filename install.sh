#!/usr/bin/env sh
set -eu

REPO="bonginkan/fairy_tale"
REF="main"
AGENT=""
TARGET=""
SOURCE_DIR=""
DRY_RUN=0
CREATE=0
FORCE=0
ALLOW_OUTSIDE_HOME=0

usage() {
  cat <<'USAGE'
Install Fairy Tale skills without cloning the repository.

Usage:
  install.sh --agent codex|claude|agents [--ref REF] [--dry-run] [--force]
  install.sh --target /absolute/skills/dir [--ref REF] [--dry-run] [--force]

Options:
  --agent NAME           Use a default target: codex, claude, or agents.
  --target PATH          Absolute target skills directory.
  --repo OWNER/REPO      GitHub repository to fetch. Default: bonginkan/fairy_tale.
  --ref REF              Git branch, tag, or commit. Default: main.
  --source PATH          Local source tree, for testing from a checkout.
  --create              Create the target directory if it does not exist.
  --force               Replace existing skill directories whose contents differ.
  --allow-outside-home  Allow a target outside $HOME.
  --dry-run             Print planned actions without writing files.
  --help                Show this help.

Every skill directory under skills/ is installed; there is no separate list to
keep in step. Re-running is safe: a skill that already matches the source is
left alone, and a skill missing from the target is added. --force is needed
only to overwrite a skill that differs from the source, or one whose
destination is a symlink. A destination that cannot be replaced is reported
and leaves the exit status non-zero, but it does not stop the skills after it
from being installed.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --agent) AGENT="${2:-}"; shift 2 ;;
    --target) TARGET="${2:-}"; shift 2 ;;
    --repo) REPO="${2:-}"; shift 2 ;;
    --ref) REF="${2:-}"; shift 2 ;;
    --source) SOURCE_DIR="${2:-}"; shift 2 ;;
    --create) CREATE=1; shift ;;
    --force) FORCE=1; shift ;;
    --allow-outside-home) ALLOW_OUTSIDE_HOME=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$TARGET" ]; then
  case "$AGENT" in
    codex) TARGET="$HOME/.codex/skills" ;;
    claude) TARGET="$HOME/.claude/skills" ;;
    agents) TARGET="$HOME/.agents/skills" ;;
    "") echo "either --agent or --target is required" >&2; exit 2 ;;
    *) echo "unsupported --agent: $AGENT" >&2; exit 2 ;;
  esac
fi

case "$TARGET" in
  /*) ;;
  *) echo "--target must be an absolute path: $TARGET" >&2; exit 2 ;;
esac

if [ "$ALLOW_OUTSIDE_HOME" -eq 0 ]; then
  case "$TARGET" in
    "$HOME"/*) ;;
    *) echo "refusing target outside HOME without --allow-outside-home: $TARGET" >&2; exit 2 ;;
  esac
fi

if [ ! -d "$TARGET" ]; then
  if [ "$CREATE" -eq 1 ]; then
    [ "$DRY_RUN" -eq 1 ] || mkdir -p "$TARGET"
  else
    echo "target directory does not exist: $TARGET" >&2
    echo "create it explicitly, or rerun with --create" >&2
    exit 2
  fi
fi

TMP_DIR=""
cleanup() {
  if [ -n "$TMP_DIR" ] && [ -d "$TMP_DIR" ]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT INT TERM

if [ -n "$SOURCE_DIR" ]; then
  ROOT="$SOURCE_DIR"
else
  command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 2; }
  command -v tar >/dev/null 2>&1 || { echo "tar is required" >&2; exit 2; }
  TMP_DIR="$(mktemp -d)"
  ARCHIVE_URL="https://github.com/$REPO/archive/$REF.tar.gz"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "fetch $ARCHIVE_URL"
    ROOT="$TMP_DIR/source"
  else
    mkdir -p "$TMP_DIR/source"
    curl -fsSL "$ARCHIVE_URL" | tar -xz --strip-components=1 -C "$TMP_DIR/source"
    ROOT="$TMP_DIR/source"
  fi
fi

# The installed set is the source tree itself. A second list kept here would be
# a second thing to remember, and the one that is forgotten is the one that
# stops shipping.
SKILLS_SRC="$ROOT/skills"

if [ ! -d "$SKILLS_SRC" ]; then
  if [ "$DRY_RUN" -eq 1 ] && [ -z "$SOURCE_DIR" ]; then
    # Nothing was fetched, so the set can only be named, not enumerated.
    echo "install every skill under skills/ of $REPO@$REF -> $TARGET"
  else
    echo "missing skills directory in source: $SKILLS_SRC" >&2
    exit 1
  fi
else
  INSTALLED=0
  REFUSED=0
  for SRC in "$SKILLS_SRC"/*; do
    [ -d "$SRC" ] || continue
    SKILL="${SRC##*/}"
    DEST="$TARGET/$SKILL"
    if [ ! -f "$SRC/SKILL.md" ]; then
      echo "missing skill source: $SRC/SKILL.md" >&2
      exit 1
    fi
    if [ -e "$DEST" ] || [ -L "$DEST" ]; then
      if [ "$FORCE" -eq 0 ]; then
        # A refusal is about one destination. Ending the whole run here would
        # keep every later skill out of the target -- the way a lane stays
        # frozen at whatever it was first given.
        if [ -L "$DEST" ]; then
          # What this destination holds is decided elsewhere, and can change
          # after this run without the installer being involved.
          echo "destination is a symlink; use --force to replace: $DEST" >&2
          REFUSED=$((REFUSED + 1))
          continue
        fi
        if command -v diff >/dev/null 2>&1 && diff -r "$SRC" "$DEST" >/dev/null 2>&1; then
          echo "up to date $DEST"
          INSTALLED=$((INSTALLED + 1))
          continue
        fi
        echo "destination exists and differs; use --force to replace: $DEST" >&2
        REFUSED=$((REFUSED + 1))
        continue
      fi
    fi
    echo "install $SRC -> $DEST"
    if [ "$DRY_RUN" -eq 0 ]; then
      if [ -e "$DEST" ] || [ -L "$DEST" ]; then
        rm -rf "$DEST"
      fi
      cp -R "$SRC" "$DEST"
    fi
    INSTALLED=$((INSTALLED + 1))
  done

  if [ "$INSTALLED" -eq 0 ] && [ "$REFUSED" -eq 0 ]; then
    echo "no skills found under $SKILLS_SRC" >&2
    exit 1
  fi
  if [ "$REFUSED" -gt 0 ]; then
    echo "$REFUSED skill(s) left unchanged; rerun with --force to replace them" >&2
    exit 2
  fi
fi

echo "Fairy Tale skills installed in $TARGET"
