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

# Resolve a path the way the filesystem will, not the way it is spelled. A
# boundary checked against the written path is not a boundary: a symlink
# anywhere along it leads somewhere the text never mentions.
physical_path() {
  # Walk the path one component at a time and resolve each step that exists.
  # Anything less is a different path than the one the kernel will use: a
  # symlink resolves to somewhere the text never names, and `..` applies to
  # where the previous components actually led -- including through a
  # component that does not exist yet and is about to be created.
  pp_rest="$1"
  case "$pp_rest" in
    /*) pp_out="/" ;;
    *) pp_out="$(pwd -P)" ;;
  esac
  while [ -n "$pp_rest" ]; do
    case "$pp_rest" in
      /*) pp_rest="${pp_rest#/}"; continue ;;
    esac
    pp_head="${pp_rest%%/*}"
    if [ "$pp_head" = "$pp_rest" ]; then
      pp_rest=""
    else
      pp_rest="${pp_rest#*/}"
    fi
    case "$pp_head" in
      '' | .)
        continue
        ;;
      ..)
        pp_out="${pp_out%/*}"
        [ -z "$pp_out" ] && pp_out="/"
        continue
        ;;
    esac
    case "$pp_out" in
      /) pp_next="/$pp_head" ;;
      *) pp_next="$pp_out/$pp_head" ;;
    esac
    if [ -d "$pp_next" ]; then
      pp_out="$(cd "$pp_next" && pwd -P)"
    else
      pp_out="$pp_next"
    fi
  done
  printf '%s\n' "$pp_out"
}

# True when $2 is $1 or lives under it, compared as resolved paths.
path_contains() {
  case "$2/" in
    "$1"/*) return 0 ;;
  esac
  return 1
}

# True when the tree holds a symlink anywhere inside it, and when that cannot
# be established. A skill assembled from links is not a copy: its bytes live
# where the installer never looked, and they can change or vanish after every
# check this script performs has passed.
# 0: holds a symlink. 1: holds none. 2: could not be established.
# The answer has to come from find's own status. Reading it off the end of a
# pipeline reports whatever the last stage made of the silence, and a find
# that failed is silent in exactly the same way as a tree with no links in
# it. "Could not be established" is kept separate from "holds one" so the
# refusal says which of the two happened; both stop the run either way.
holds_symlink() {
  command -v find >/dev/null 2>&1 || return 2
  hs_found="$(find "$1" -type l -print 2>/dev/null)" || return 2
  [ -n "$hs_found" ]
}

TARGET_PHYS="$(physical_path "$TARGET")"

if [ "$ALLOW_OUTSIDE_HOME" -eq 0 ]; then
  HOME_PHYS="$(physical_path "$HOME")"
  if ! path_contains "$HOME_PHYS" "$TARGET_PHYS"; then
    echo "refusing target outside HOME without --allow-outside-home: $TARGET" >&2
    echo "resolves to: $TARGET_PHYS" >&2
    exit 2
  fi
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
  SKILLS_PHYS="$(physical_path "$SKILLS_SRC")"
  # --force removes a destination before copying onto it. When the destination
  # is the source, or holds it, that removal deletes the very tree being
  # installed and the run consumes its own input.
  if path_contains "$SKILLS_PHYS" "$TARGET_PHYS" \
    || path_contains "$TARGET_PHYS" "$SKILLS_PHYS"; then
    echo "refusing a target that overlaps the source tree" >&2
    echo "  target resolves to: $TARGET_PHYS" >&2
    echo "  source resolves to: $SKILLS_PHYS" >&2
    exit 2
  fi

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
    holds_symlink "$SRC" && SRC_LINKS=0 || SRC_LINKS=$?
    if [ -L "$SRC" ] || [ "$SRC_LINKS" -eq 0 ]; then
      echo "source skill is not a plain tree of files: $SRC" >&2
      exit 1
    fi
    if [ "$SRC_LINKS" -eq 2 ]; then
      echo "cannot establish whether the source holds symlinks: $SRC" >&2
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
        holds_symlink "$DEST" && DEST_LINKS=0 || DEST_LINKS=$?
        if [ "$DEST_LINKS" -eq 0 ]; then
          # diff reads through a link, so a destination stitched together from
          # links compares equal while holding none of what it reports.
          echo "destination holds a symlink; use --force to replace: $DEST" >&2
          REFUSED=$((REFUSED + 1))
          continue
        fi
        if [ "$DEST_LINKS" -eq 2 ]; then
          echo "cannot establish whether the destination holds symlinks;" \
            "use --force to replace: $DEST" >&2
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
