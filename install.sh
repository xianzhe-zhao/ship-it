#!/bin/sh
# 把本仓库的 skills 以 symlink 方式接入全局 skill 目录（~/.agents/skills）
# 真源在仓库：改仓库即生效，不产生第二份会漂移的副本
# 用法: ./install.sh [--force]
set -eu
REPO="$(cd "$(dirname "$0")" && pwd)"
TARGET="$HOME/.agents/skills"
mkdir -p "$TARGET"
FORCE=0
if [ "${1:-}" = "--force" ]; then FORCE=1; fi

for d in "$REPO"/*/; do
  [ -f "$d/SKILL.md" ] || continue
  name="$(basename "$d")"
  dest="$TARGET/$name"
  if [ -L "$dest" ]; then
    if [ "$FORCE" -eq 0 ]; then
      echo "SKIP  $name (already exists; use --force to replace)"
      continue
    fi
    rm "$dest"
  elif [ -e "$dest" ]; then
    echo "ERROR $dest 已存在且不是 symlink，拒绝删除。请先手动移走。" >&2
    exit 1
  fi
  ln -s "${d%/}" "$dest"
  echo "LINK  $name -> ${d%/}"
done
echo "Done. DSH rescans ~/.agents/skills live (no restart needed)."
