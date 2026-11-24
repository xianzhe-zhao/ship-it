#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_terms.py — 角色名词典校验（v5.0.0 / C22）：正文范围不得出现旧角色名。

读取 references/role-glossary.md 的权威角色名（表格第一列）与别名（历史，第二列），
别名即旧名。扫描正文范围文件，正文出现旧名即 FAIL；历史文件（CHANGELOG、
docs/specs/*.md）走 allowlist 放行。

用法：
    python ship-it/scripts/check_terms.py --root .
    python ship-it/scripts/check_terms.py --root . --json

退出码：0 = PASS；1 = FAIL。
"""

from __future__ import annotations

import argparse
import bisect
import fnmatch
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

GLOSSARY_REL = "ship-it/references/role-glossary.md"
BODY_FILES = [
    "ship-it/SKILL.md",
    "ship-it/references/team-mode.md",
    "ship-it/references/spec-template.md",
    "README.md",
    "docs/deploy-runbook.md",
]
ALLOWLIST_FILES = [
    "ship-it/CHANGELOG.md",
    "CHANGELOG.md",
]
ALLOWLIST_GLOBS = [
    "docs/specs/*.md",
]
SEP_RE = re.compile(r"^:?-+:?$")


def is_inside(path, root):
    try:
        child = os.path.normcase(os.path.realpath(str(path)))
        parent = os.path.normcase(os.path.realpath(str(root)))
        return os.path.commonpath([child, parent]) == parent
    except (ValueError, OSError):
        return False


def read_utf8(path):
    try:
        with open(str(path), "r", encoding="utf-8-sig", newline="") as handle:
            return handle.read(), None
    except UnicodeDecodeError as exc:
        return None, "不是合法 UTF-8：%s" % exc
    except OSError as exc:
        return None, "读取失败：%s" % exc


def parse_glossary(text):
    """解析 role-glossary.md 表格，返回 (authoritative_names, aliases)。

    表头行含 角色名；其下一行为 |---|---|---| 分隔行；随后连续的 | ... | 行为
    数据行，第一列为权威角色名，第二列为别名（历史），多别名以 / 或 、 分隔，
    "-" 表示无别名。
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    authoritative = []
    aliases = []
    header_idx = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cells and "角色名" in cells[0]:
                header_idx = i
                break
    if header_idx is None:
        return authoritative, aliases
    idx = header_idx + 1
    n = len(lines)
    if idx < n:
        s = lines[idx].strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cells and all(SEP_RE.match(c) for c in cells if c):
                idx += 1
    while idx < n:
        s = lines[idx].strip()
        if not (s.startswith("|") and s.endswith("|")):
            break
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) >= 2:
            name = cells[0].strip()
            alias_cell = cells[1].strip()
            if name and name not in authoritative:
                authoritative.append(name)
            if alias_cell and alias_cell != "-":
                for a in re.split(r"[/／、]", alias_cell):
                    a = a.strip()
                    if a and a != "-" and a not in aliases:
                        aliases.append(a)
        idx += 1
    return authoritative, aliases


def is_allowlisted(rel):
    rel = rel.replace("\\", "/")
    if rel in ALLOWLIST_FILES:
        return True
    for pat in ALLOWLIST_GLOBS:
        if fnmatch.fnmatch(rel, pat):
            return True
    return False


def scan_text(rel, text, aliases):
    """返回命中列表；长别名优先，覆盖与之重叠的短别名区间，避免重复报告。"""
    hits = []
    ordered = sorted(set(aliases), key=len, reverse=True)
    if not ordered:
        return hits
    line_starts = []
    pos = 0
    for line in text.split("\n"):
        line_starts.append(pos)
        pos += len(line) + 1
    covered = []
    for term in ordered:
        start = 0
        while True:
            idx = text.find(term, start)
            if idx == -1:
                break
            end = idx + len(term)
            overlaps = any(idx < ce and end > cs for cs, ce in covered)
            if not overlaps:
                covered.append((idx, end))
                lineno = bisect.bisect_right(line_starts, idx)
                snippet = text[line_starts[lineno - 1]:].split("\n", 1)[0].strip()
                hits.append({
                    "file": rel,
                    "line": lineno,
                    "term": term,
                    "context": snippet[:160],
                })
            start = end
    hits.sort(key=lambda h: (h["file"], h["line"], h["term"]))
    return hits


def build_parser():
    parser = argparse.ArgumentParser(description="角色名词典校验（v5.0.0 / C22）")
    parser.add_argument("--root", default=".", help="仓库根（默认当前目录）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def emit(result, args):
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("root    : %s" % result["root"])
        print("词典    : %s" % (result["glossary"] or "（缺失）"))
        print("权威名  : %s" % ("、".join(result["authoritative"]) or "（无）"))
        print("旧名    : %s" % ("、".join(result["aliases"]) or "（无）"))
        print("扫描    : %s" % ("、".join(result["scanned"]) or "（无）"))
        if result["allowlisted"]:
            print("放行    : %s" % ("、".join(result["allowlisted"])))
        for h in result["hits"]:
            print("HIT     : %s:%d [%s] %s" % (h["file"], h["line"], h["term"], h["context"]))
        for w in result["warnings"]:
            print("WARN    : %s" % w)
        for e in result["errors"]:
            print("ERROR   : %s" % e)
        print("结果    : %s（%d 处旧名 / %d 错误 / %d 警告）" % (
            "PASS" if result["ok"] else "FAIL",
            len(result["hits"]),
            len(result["errors"]),
            len(result["warnings"]),
        ))
    return 0 if result["ok"] else 1


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    errors = []
    warnings = []
    hits = []
    scanned = []
    allowlisted = []
    authoritative = []
    aliases = []

    result = {
        "ok": False,
        "root": str(root),
        "glossary": "",
        "authoritative": authoritative,
        "aliases": aliases,
        "scanned": scanned,
        "allowlisted": allowlisted,
        "hits": hits,
        "errors": errors,
        "warnings": warnings,
    }

    if not root.is_dir():
        print("ERROR: --root 不是目录：%s" % root)
        return 1

    glossary_path = root / GLOSSARY_REL
    result["glossary"] = GLOSSARY_REL
    if not glossary_path.is_file():
        errors.append("缺权威词典：%s（check_terms.py 依赖 role-glossary.md）" % GLOSSARY_REL)
        result["ok"] = not errors
        return emit(result, args)

    gtext, gerr = read_utf8(glossary_path)
    if gerr:
        errors.append("词典读取失败：%s" % gerr)
        result["ok"] = not errors
        return emit(result, args)

    authoritative[:], aliases[:] = parse_glossary(gtext)
    if not authoritative:
        errors.append("词典解析失败：未在 %s 找到角色名表格（表头需含 角色名 列）" % GLOSSARY_REL)
    elif len(authoritative) < 8:
        warnings.append("词典权威角色名不足 8 个，实际 %d 个：%s" % (
            len(authoritative), "、".join(authoritative)))
    if not aliases:
        warnings.append("词典未解析到别名（旧名），正文旧名检测无目标，视为 PASS")

    for rel in BODY_FILES:
        fpath = root / rel
        if not fpath.is_file():
            warnings.append("正文文件不存在，已跳过：%s" % rel)
            continue
        if is_allowlisted(rel):
            allowlisted.append(rel)
            continue
        text, terr = read_utf8(fpath)
        if terr:
            errors.append("正文文件读取失败 %s：%s" % (rel, terr))
            continue
        scanned.append(rel)
        hits.extend(scan_text(rel, text, aliases))

    for h in hits:
        errors.append("正文残留旧名：%s:%d [%s] %s" % (h["file"], h["line"], h["term"], h["context"]))

    result["ok"] = not errors
    return emit(result, args)


if __name__ == "__main__":
    sys.exit(main())
