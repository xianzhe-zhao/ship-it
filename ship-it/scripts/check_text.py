#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_text.py — v5.1.0 文本质量闸门（C1–C4）：行数、禁词、重复标题、矛盾计数、互引、边界语。

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


def is_inside(path, root):
    try:
        child = os.path.normcase(os.path.realpath(str(path)))
        parent = os.path.normcase(os.path.realpath(str(root)))
        return os.path.commonpath([child, parent]) == parent
    except (ValueError, OSError):
        return False


def resolve_inside(raw, root):
    path = Path(str(raw))
    if not path.is_absolute():
        path = root / path
    real = Path(os.path.realpath(str(path)))
    return real if is_inside(real, root) else None
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
    """C21（B7-G1）：通用条款区间校验。

    解析 SKILL.md 全部 "C1-Cn"/"An-An" 区间（分隔可为 –/-/—/~/至/../…），
    自动检测同文档内不一致区间：同一系列、同一左端、右端不同即矛盾。
    原 3 组硬编码逻辑保留为子集（不删除），通用解析在其之上兜底。
    仅检测同文档内区间，不跨文件。
    """
    # 原 3 组硬编码区间（保留为子集，确保旧行为不退化）。
    pairs = [
        (r"C1[–\-]C17", r"C1[–\-]C18", "C1–C17 与 C1–C18"),
        (r"A1[–\-]A18", r"A1[–\-]A19", "A1–A18 与 A1–A19"),
        (r"C1[–\-]C5", r"C1[–\-]C10", "C1–C5 与 C1–C10"),
    ]
    for left, right, label in pairs:
        if re.search(left, ship_text) and re.search(right, ship_text):
            errors.append("ship-it/SKILL.md 矛盾计数：%s" % label)

    # 通用解析：抽取全部 C<a>-C<b> / A<a>-A<b> 区间，按 (系列, 左端) 分组比较右端。
    interval_re = re.compile(
        r"\b([CA])\s*(\d+)\s*(?:[–\-—～~]|\.\.|…)\s*\1\s*(\d+)\b"
    )
    by_key = {}
    for match in interval_re.finditer(ship_text):
        series, start, end = match.group(1), int(match.group(2)), int(match.group(3))
        if end < start:
            continue
        by_key.setdefault((series, start), set()).add(end)
    for (series, start), ends in sorted(by_key.items()):
        if len(ends) > 1:
            ends_sorted = sorted(ends)
            label = "%s%d–%s%d 与 %s%d–%s%d" % (
                series, start, series, ends_sorted[0],
                series, start, series, ends_sorted[-1]
            )
            msg = "ship-it/SKILL.md 矛盾计数：%s" % label
            if msg not in errors:
                errors.append(msg)


def check_doc_quality(texts, errors, warnings):
    """C15：验收前文档质量检查——废话词/术语统一/跨文件分歧/前后矛盾。"""
    # 1. 废话词（主观形容词无判定方式）
    FLUFF_WORDS = ["更加", "更好地", "完善的", "合理的", "适当", "进一步", "尽可能", "尽量", "原则上", "一般来说", "基本上", "大致", "差不多"]
    for label, text in texts.items():
        for word in FLUFF_WORDS:
            if word in text:
                idx = text.index(word)
                ctx = text[max(0, idx-15):idx+25].replace("\n", " ")
                warnings.append("%s 含废话词'%s'：%s" % (label, word, ctx))

    # 2. 跨文件术语统一：同一概念在不同 md 文件应用词一致
    # 读所有 references/*.md
    refs_dir = Path(__file__).resolve().parent.parent / "references"
    ref_texts = {}
    if refs_dir.is_dir():
        for md in refs_dir.glob("*.md"):
            ref_texts[md.name] = read_text(md)
    ship = texts.get("ship-it/SKILL.md", "")

    # C5[B3]：术语对从 term-glossary.md 词典读（消除第二份硬编码源）
    # term-glossary.md 表格格式：| 术语 | 别名（顿号分隔） | 定义 |
    # 解析出 (别名, 权威术语) 对——同一概念不应两种写法并存于不同文件
    TERM_PAIRS = []
    glossary_path = refs_dir / "term-glossary.md"
    if glossary_path.is_file():
        glossary_text = read_text(glossary_path)
        in_table = False
        for line in glossary_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("| 术语") and "别名" in stripped:
                in_table = True
                continue
            if in_table and stripped.startswith("|") and not stripped.startswith("|---"):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if len(cells) >= 2 and cells[0] and cells[1]:
                    canonical = cells[0]
                    aliases = [a.strip() for a in cells[1].split("、") if a.strip()]
                    for alias in aliases:
                        TERM_PAIRS.append((alias, canonical))
            elif in_table and not stripped.startswith("|"):
                in_table = False
    all_docs = dict(ref_texts)
    all_docs.pop("role-glossary.md", None)
    all_docs.pop("term-glossary.md", None)  # C5：流程术语词典，别名是设计，不判分歧
    all_docs.pop("security-kb.md", None)  # 历史安全库用旧角色名
    if ship:
        all_docs["SKILL.md"] = ship
    if getattr(args, 'skip_term_divergence', False):
        warnings.append("跳过跨文件术语分歧检查（--skip-term-divergence）")
    else:
        for a, b in TERM_PAIRS:
            files_with_a = [name for name, t in all_docs.items() if a in t]
            files_with_b = [name for name, t in all_docs.items() if b in t]
            if files_with_a and files_with_b:
                errors.append("术语分歧：'%s'（%s）与 '%s'（%s）在不同文件并存，应统一" %
                              (a, ",".join(files_with_a), b, ",".join(files_with_b)))

    # 3. 前后矛盾：同一文件内数值/计数前后不一致
    # 检查"X 条 C"/"X 条优化"等计数在不同位置是否一致
    import re as _re
    for label, text in all_docs.items():
        # 找所有"NN 条 C"/"NN 条优化"/"NN 个角色"等计数
        count_patterns = [
            (_re.compile(r"(\d+)\s*条\s*C"), "条 C"),
            (_re.compile(r"(\d+)\s*条\s*优化"), "条优化"),
            (_re.compile(r"(\d+)\s*个\s*角色"), "个角色"),
            (_re.compile(r"(\d+)\s*条\s*轨道"), "条轨道"),
        ]
        for pat, unit in count_patterns:
            nums = set(pat.findall(text))
            if len(nums) > 1:
                errors.append("%s 前后矛盾：'%s'计数不一致 %s" % (label, unit, "/".join(sorted(nums))))


def main(argv=None):
    parser = argparse.ArgumentParser(description="v5.1.0 文本质量闸门（行数/禁词/重复/矛盾/互引/边界）")
    parser.add_argument("--root", default=".")
    parser.add_argument("--git-push", help="显式上传 skill 路径；必须在 --root 内（默认全局 skill 为兼容例外）")
    parser.add_argument("--retro", help="复盘文件路径；必须在 --root 内")
    parser.add_argument("--allow-missing-git-push", action="store_true")
    parser.add_argument("--skip-term-divergence", action="store_true",
                        help="跳过跨文件术语分歧检查(临时:远程文件版本不一致时用)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    errors = []
    warnings = []
    if not root.is_dir():
        print("ERROR: --root 不是目录：%s" % root)
        return 1
    banned = load_banned(root)
    ship = root / "ship-it" / "SKILL.md"
    retro_raw = args.retro if args.retro else DEFAULT_RETRO
    retro = resolve_inside(retro_raw, root)
    if retro is None:
        errors.append("--retro 越出仓库根（C4）：%s（root=%s）" % (retro_raw, root))
        retro = root / DEFAULT_RETRO
    if args.git_push:
        git_push = resolve_inside(args.git_push, root)
        if git_push is None:
            errors.append("--git-push 越出仓库根（C4）：%s（root=%s）" % (args.git_push, root))
            git_push = root / "git-push-firewall" / "SKILL.md"
    else:
        git_push = Path(os.path.realpath(str(DEFAULT_GIT_PUSH)))

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
    check_doc_quality(texts, errors, warnings)

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
