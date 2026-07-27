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
  --uninstall) MODE="uninstall" ;;
  --check) MODE="check" ;;
  *) echo "usage: $0 [--dry-run|--uninstall|--check]" >&2; exit 2 ;;
esac

[[ -f "$SOURCE_DIR/SKILL.md" ]] || { echo "missing skill source" >&2; exit 1; }

targets=("$UNIFIED_DIR/$SKILL_NAME")
for base in "$HOME/.codex/skills" "$HOME/.Codex/skills" "$HOME/.claude/skills"; do
  [[ "$base" == "$UNIFIED_DIR" ]] || targets+=("$base/$SKILL_NAME")
done

for target in "${targets[@]}"; do
  if [[ "$MODE" == "check" ]]; then
    [[ -L "$target" ]] && echo "linked $target -> $(readlink "$target")" || echo "missing $target"
  elif [[ "$MODE" == "uninstall" ]]; then
    if [[ -L "$target" ]]; then rm "$target"; echo "removed $target"; elif [[ -e "$target" ]]; then echo "refusing non-symlink: $target" >&2; exit 1; fi
  elif [[ "$MODE" == "dry-run" ]]; then
    echo "would link $target -> $SOURCE_DIR"
  else
    mkdir -p "$(dirname "$target")"
    if [[ -e "$target" && ! -L "$target" ]]; then echo "refusing to replace non-symlink: $target" >&2; exit 1; fi
    ln -sfn "$SOURCE_DIR" "$target"
    echo "linked $target -> $SOURCE_DIR"
  fi
done
