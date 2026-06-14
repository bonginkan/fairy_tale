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
  --force               Replace existing fairy-tale skill directories.
  --allow-outside-home  Allow a target outside $HOME.
  --dry-run             Print planned actions without writing files.
  --help                Show this help.
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

for SKILL in fairy-tale fairy-tale-legal-feedback; do
  SRC="$ROOT/skills/$SKILL"
  DEST="$TARGET/$SKILL"
  if [ "$DRY_RUN" -eq 0 ] && [ ! -f "$SRC/SKILL.md" ]; then
    echo "missing skill source: $SRC" >&2
    exit 1
  fi
  if [ -e "$DEST" ] && [ "$FORCE" -eq 0 ]; then
    echo "destination exists; use --force to replace: $DEST" >&2
    exit 2
  fi
  echo "install $SRC -> $DEST"
  if [ "$DRY_RUN" -eq 0 ]; then
    if [ -e "$DEST" ]; then
      rm -rf "$DEST"
    fi
    cp -R "$SRC" "$DEST"
  fi
done

echo "Fairy Tale skills installed in $TARGET"
