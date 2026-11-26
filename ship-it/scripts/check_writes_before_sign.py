#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_writes_before_sign.py — 规划期只读保护（事前拦截，C5）。

用法：
    python check_writes_before_sign.py docs/specs/2026-11-25-xxx.md
    python check_writes_before_sign.py docs/specs/2026-11-25-xxx.md --root .
    python check_writes_before_sign.py docs/specs/2026-11-25-xxx.md --json

退出码：0 = spec 已签约或无违禁改动；1 = 发现签约前实现文件被改（不得编码）。
原理：读 spec 的 status；非 signed 时扫 git 工作区，凡改动落在"实现文件"
      （命中 IMPL_PREFIXES 且不在 ALLOW_PREFIXES）即报错。
      与 check_spec.py --git-check 互补：后者管提交时间线，前者管工作区实时状态。
路径安全：所有输入路径 resolve() 后必须落在仓库根内；越界 / 符号链接逃逸 = 非零退出。
编码：UTF-8 输入输出；Windows 兼容；仅 Python 3.8+ 标准库。
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 实现文件判定：这些路径前缀算"实现"，签约前不许动
IMPL_PREFIXES = (
    "src/", "lib/", "app/", "server/", "backend/", "frontend/",
    "components/", "pages/", "views/", "router/", "stores/", "composables/",
    "api/", "services/", "models/", "schemas/", "migrations/",
    "scripts/", "tools/",
)
# 白名单：这些前缀即使被改也算"文档/流程"，不拦截
ALLOW_PREFIXES = (
    "docs/", "docs/specs/", "docs/reviews/",
    ".agents/", ".dsh-project-memory/",
    "ship-it/",
    "CHANGELOG.md", "README.md", "CLAUDE.md", "AGENTS.md",
)


def parse_frontmatter(text):
    """简易 YAML front matter 解析（只要 status 字段）。"""
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        kv = line.split(":", 1)
        if len(kv) == 2:
            fm[kv[0].strip()] = kv[1].strip().strip("\"'")
    return fm


def git_changed_files(root):
    """git status --porcelain 取工作区改动文件列表。"""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain"],
            encoding="utf-8", errors="replace", timeout=30,
        )
    except Exception:
        return []
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()  # 跳过 XY 状态码
        if "->" in path:
            path = path.split("->")[1].strip()  # rename
        files.append(path)
    return files


def is_impl_file(path):
    """判定是否实现文件：命中 IMPL_PREFIXES 且不在 ALLOW_PREFIXES。"""
    norm = path.replace("\\", "/")
    for ap in ALLOW_PREFIXES:
        if norm.startswith(ap):
            return False
    for ip in IMPL_PREFIXES:
        if norm.startswith(ip):
            return True
    # 兜底：根目录的源码扩展名也算实现（排除 tests/tmp 下的 spec 派生物）
    if re.search(r"\.(py|js|ts|tsx|jsx|vue|go|rs|java|rb|php)$", norm, re.I):
        if norm.startswith("tests/") or norm.startswith("tmp/"):
            return False
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description="规划期只读保护（C5）")
    ap.add_argument("spec", help="spec 文件路径")
    ap.add_argument("--root", default=".", help="仓库根（默认当前目录）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    spec = Path(args.spec).resolve()
    # 路径安全：必须在仓库根内
    try:
        spec.relative_to(root)
    except ValueError:
        msg = "[FAIL] spec 越界: %s（根: %s）" % (spec, root)
        if args.json:
            import json
            print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
        else:
            print(msg, file=sys.stderr)
        sys.exit(1)

    if not spec.is_file():
        msg = "[FAIL] spec 不存在: %s" % spec
        if args.json:
            import json
            print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
        else:
            print(msg, file=sys.stderr)
        sys.exit(1)

    text = spec.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text)
    status = fm.get("status", "draft")

    # 已签约/已验收 → 不拦截（编码合法）
    if status in ("signed", "accepted"):
        msg = "[OK] spec status=%s，已签约，放行编码。" % status
        if args.json:
            import json
            print(json.dumps({"ok": True, "status": status, "violations": []}, ensure_ascii=False))
        else:
            print(msg)
        sys.exit(0)

    # draft / paused → 扫工作区
    changed = git_changed_files(root)
    violations = [f for f in changed if is_impl_file(f)]
    if violations:
        msg = "spec status=%s（未签约），以下实现文件已被改动：" % status
        if args.json:
            import json
            print(json.dumps({"ok": False, "status": status, "violations": violations}, ensure_ascii=False))
        else:
            print("[FAIL] " + msg, file=sys.stderr)
            for f in violations:
                print("  - %s" % f, file=sys.stderr)
            print('签约前不得改实现文件。请先完成 spec 并获用户"签约"。', file=sys.stderr)
        sys.exit(1)

    msg = "[OK] spec status=%s，工作区无非授权实现改动。" % status
    if args.json:
        import json
        print(json.dumps({"ok": True, "status": status, "violations": []}, ensure_ascii=False))
    else:
        print(msg)
    sys.exit(0)


if __name__ == "__main__":
    main()