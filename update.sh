#!/bin/sh
# 一键更新：拉取 ship-it 最新版本
# 用法: ./update.sh
# 前提: 已通过 git clone 安装本仓库（不是 .skill 解压安装）
set -eu
REPO="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO"

echo "拉取最新版本..."
git pull

echo ""
echo "已更新到最新版本。"
echo "DSH / Codex 会自动重扫 ~/.agents/skills，无需重启。"
echo "Claude Code 用户需确认 ~/.claude/skills/ship-it 链接仍指向本仓库。"
echo ""
echo "确认当前版本："
SKILL_MD="$REPO/ship-it/SKILL.md"
if [ -f "$SKILL_MD" ]; then
    grep '^version:' "$SKILL_MD"
fi
