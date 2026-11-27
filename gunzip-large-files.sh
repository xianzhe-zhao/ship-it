#!/bin/bash
# 解压 main 上的 .gz 文件(Contents API 上传的大文件需 gunzip 覆盖原文件)
# 用法:clone 后运行 bash gunzip-large-files.sh
set -e
echo "解压 .gz 文件覆盖原文件..."
find . -name '*.gz' -not -path './.git/*' -print0 | while IFS= read -r -d '' gz; do
  orig="${gz%.gz}"
  echo "  $gz -> $orig"
  gunzip -f "$gz"
done
echo "解压完成。请 git add -A && git commit && git push 同步解压后的文件。"
