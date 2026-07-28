#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
SKILL_NAME="sudis-aaai-submission-reviewer"
SOURCE_DIR="$ROOT_DIR/$SKILL_NAME"
UNIFIED_DIR="${SUDIS_SKILLS_DIR:-$HOME/.agents/skills}"
MODE="install"

case "${1:-}" in
  "") ;;
  --dry-run) MODE="dry-run" ;;
  --check) MODE="check" ;;
  --uninstall) echo "automatic uninstall is disabled; removal requires an exact target list, backup, recoverability statement, and explicit user approval" >&2; exit 2 ;;
  *) echo "usage: $0 [--dry-run|--check]" >&2; exit 2 ;;
esac

[[ -f "$SOURCE_DIR/SKILL.md" ]] || { echo "missing skill source" >&2; exit 1; }

targets=("$UNIFIED_DIR/$SKILL_NAME")
for base in "$HOME/.codex/skills" "$HOME/.Codex/skills" "$HOME/.claude/skills"; do
  [[ "$base" == "$UNIFIED_DIR" ]] || targets+=("$base/$SKILL_NAME")
done

for target in "${targets[@]}"; do
  if [[ "$MODE" == "check" ]]; then
    if [[ -L "$target" ]]; then
      current_target="$(readlink "$target")"
      if [[ "$current_target" == "$SOURCE_DIR" ]]; then
        echo "linked $target -> $current_target"
      else
        echo "mismatch $target -> $current_target (expected $SOURCE_DIR)" >&2
        exit 1
      fi
    elif [[ -e "$target" ]]; then
      echo "occupied $target" >&2
      exit 1
    else
      echo "missing $target"
    fi
  elif [[ "$MODE" == "dry-run" ]]; then
    if [[ -L "$target" && "$(readlink "$target")" == "$SOURCE_DIR" ]]; then
      echo "already linked $target -> $SOURCE_DIR"
    elif [[ -e "$target" || -L "$target" ]]; then
      echo "would refuse existing target $target" >&2
    else
      echo "would link $target -> $SOURCE_DIR"
    fi
  else
    mkdir -p "$(dirname "$target")"
    if [[ -L "$target" && "$(readlink "$target")" == "$SOURCE_DIR" ]]; then
      echo "already linked $target -> $SOURCE_DIR"
    elif [[ -e "$target" || -L "$target" ]]; then
      echo "refusing to replace existing target: $target" >&2
      exit 1
    else
      ln -s "$SOURCE_DIR" "$target"
      echo "linked $target -> $SOURCE_DIR"
    fi
  fi
done
