#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_text.py — v4.7.1 文本质量闸门（C1–C4）：行数、禁词、重复标题、矛盾计数、互引、边界语。

用法：
    python ship-it/scripts/check_text.py [--root .] [--git-push PATH] [--retro PATH] [--json]
    python ship-it/scripts/check_text.py --allow-missing-git-push   # CI 无全局 skill 时跳过该文件

检查对象：
    ship-it/SKILL.md                          <= 350 行
    git-push-firewall/SKILL.md                <= 60 行（默认 $HOME/.dsh/skills/git-push-firewall/SKILL.md）
    docs/reviews/2026-11-19-retrospective.md  <= 150 行
退出码：0 = PASS；1 = FAIL。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_GIT_PUSH = Path.home() / ".dsh" / "skills" / "git-push-firewall" / "SKILL.md"
DEFAULT_RETRO = "docs/reviews/2026-11-19-retrospective.md"
LIMITS = {"ship-it/SKILL.md": 350, "git-push-firewall/SKILL.md": 60, "retrospective": 150}
FALLBACK_BANNED = ["尽量", "适当", "必要时", "原则上", "一般来说", "视情况", "酌情", "看情况", "最好"]
BOUNDARY_SHIP = ["上传工具", "PR 仅在验收后", "合并仅用户"]
BOUNDARY_GIT_PUSH = ["不由此 skill 决定"]
GIT_PUSH_AUTH = ["可创建 PR", "可合并"]
FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
INLINE_RE = re.compile(r"`[^`\n]*`")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def read_text(path: Path):
    return path.read_text(encoding="utf-8")


def strip_code(text: str) -> str:
    text = FENCE_RE.sub("", text)
    return INLINE_RE.sub("", text)


def load_banned(root: Path):
    rule = root / "ship-it" / "references" / "rule-style.md"
    if not rule.is_file():
        return list(FALLBACK_BANNED)
    text = read_text(rule)
    match = re.search(r"<!--\s*BEGIN:hard-forbidden\s*-->(.*?)<!--\s*END:hard-forbidden\s*-->", text, re.S)
    if not match:
        return list(FALLBACK_BANNED)
    words = []
    for line in match.group(1).splitlines():
        word = line.strip().strip("`").strip()
        if word and not word.startswith("```") and re.search(r"[\u4e00-\u9fff]", word):
            if word not in words:
                words.append(word)
    return words or list(FALLBACK_BANNED)


def check_file(label: str, path: Path, text: str, limit: int, banned, errors, warnings):
    lines = text.splitlines()
    if len(lines) > limit:
        errors.append("%s %d 行 > %d" % (label, len(lines), limit))
    scanned = strip_code(text)
    for word in banned:
        if word in scanned:
            errors.append("%s 含硬禁用词：%s" % (label, word))
    headings = [match.group(1) + " " + match.group(2) for match in HEADING_RE.finditer(text)]
    duplicates = sorted({heading for heading in headings if headings.count(heading) > 1})
    if duplicates:
        errors.append("%s 重复标题：%s" % (label, "、".join(duplicates)))
    if "用户确认 = 签约" in text or "用户确认=签约" in text:
        errors.append("%s 含旧口径：用户确认 = 签约" % label)


def check_contradictions(ship_text: str, errors):
    pairs = [
        (r"C1[–\-]C17", r"C1[–\-]C18", "C1–C17 与 C1–C18"),
        (r"A1[–\-]A18", r"A1[–\-]A19", "A1–A18 与 A1–A19"),
        (r"C1[–\-]C5", r"C1[–\-]C10", "C1–C5 与 C1–C10"),
    ]
    for left, right, label in pairs:
        if re.search(left, ship_text) and re.search(right, ship_text):
            errors.append("ship-it/SKILL.md 矛盾计数：%s" % label)


def main(argv=None):
    parser = argparse.ArgumentParser(description="v4.7.1 文本质量闸门（行数/禁词/重复/矛盾/互引/边界）")
    parser.add_argument("--root", default=".")
    parser.add_argument("--git-push", default=str(DEFAULT_GIT_PUSH))
    parser.add_argument("--retro", default=DEFAULT_RETRO)
    parser.add_argument("--allow-missing-git-push", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    errors = []
    warnings = []
    banned = load_banned(root)
    ship = root / "ship-it" / "SKILL.md"
    retro = Path(args.retro)
    if not retro.is_absolute():
        retro = root / retro
    git_push = Path(args.git_push)

    texts = {}
    if not ship.is_file():
        errors.append("缺文件：%s" % ship)
    else:
        texts["ship-it/SKILL.md"] = read_text(ship)
    if not retro.is_file():
        errors.append("缺文件：%s" % retro)
    else:
        texts["retrospective"] = read_text(retro)
    if git_push.is_file():
        texts["git-push-firewall/SKILL.md"] = read_text(git_push)
    elif args.allow_missing_git_push:
        warnings.append("git-push-firewall/SKILL.md 不存在，按 --allow-missing-git-push 跳过：%s" % git_push)
    else:
        errors.append("缺文件：%s（CI 无全局 skill 时加 --allow-missing-git-push）" % git_push)

    if "ship-it/SKILL.md" in texts:
        check_file("ship-it/SKILL.md", ship, texts["ship-it/SKILL.md"], LIMITS["ship-it/SKILL.md"], banned, errors, warnings)
    if "git-push-firewall/SKILL.md" in texts:
        check_file("git-push-firewall/SKILL.md", git_push, texts["git-push-firewall/SKILL.md"],
                   LIMITS["git-push-firewall/SKILL.md"], banned, errors, warnings)
    if "retrospective" in texts:
        check_file("docs/reviews/2026-11-19-retrospective.md", retro, texts["retrospective"],
                   LIMITS["retrospective"], banned, errors, warnings)

    ship_text = texts.get("ship-it/SKILL.md", "")
    git_text = texts.get("git-push-firewall/SKILL.md", "")
    if "git-push-firewall" in ship_text:
        errors.append("ship-it/SKILL.md 引用了 git-push-firewall（两 skill 互不引用）")
    if "ship-it" in git_text:
        errors.append("git-push-firewall/SKILL.md 引用了 ship-it（两 skill 互不引用）")
    for phrase in BOUNDARY_SHIP:
        if phrase not in ship_text:
            errors.append("ship-it/SKILL.md 缺少边界语：%s" % phrase)
    for phrase in BOUNDARY_GIT_PUSH:
        if git_text and phrase not in git_text:
            errors.append("git-push-firewall/SKILL.md 缺少边界语：%s" % phrase)
    for phrase in GIT_PUSH_AUTH:
        if phrase in git_text:
            errors.append("git-push-firewall/SKILL.md 含 PR/合并授权语：%s" % phrase)
    check_contradictions(ship_text, errors)

    result = {"ok": not errors, "errors": errors, "warnings": warnings,
              "files": {str(path): len(text.splitlines()) for path, text in texts.items()},
              "banned": banned}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for path, count in result["files"].items():
            print("OK   : %s %d 行" % (path, count))
        for warning in warnings:
            print("WARN : %s" % warning)
        for error in errors:
            print("ERROR: %s" % error)
        print("结果 : %s（%d 错误 / %d 警告）" % ("PASS" if result["ok"] else "FAIL", len(errors), len(warnings)))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
