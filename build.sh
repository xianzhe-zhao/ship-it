#!/bin/sh
# 从源码构建 .skill 打包文件（输出到 dist/）
# 用法: ./build.sh
set -eu
REPO="$(cd "$(dirname "$0")" && pwd)"
DIST="$REPO/dist"
mkdir -p "$DIST"

# 优先用 DSH 内置 Python，否则用 PATH 中的 python
PY_CANDIDATE="$HOME/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe"
if [ -x "$PY_CANDIDATE" ]; then PY="$PY_CANDIDATE"; else PY="python"; fi

# 用 skill-creator 的打包器（本仓库不含 skill-creator，从作者的已装版本取）
PACKAGER="$HOME/.agents/skills/skill-creator"
if [ ! -d "$PACKAGER" ]; then
    echo "未找到 skill-creator（打包器来源）。请先安装 skill-creator，或手动 zip ship-it 目录。" >&2
    echo "手动替代：zip -r dist/ship-it.zip ship-it/*，再改后缀为 .skill" >&2
    exit 1
fi

cd "$PACKAGER"
"$PY" -m scripts.package_skill "$REPO/ship-it" "$DIST"
echo "Done:"
ls -la "$DIST"/*.skill 2>/dev/null | awk '{print "  " $9 " (" $5 " bytes)"}'
