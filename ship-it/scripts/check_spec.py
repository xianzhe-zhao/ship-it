#!/usr/bin/env python3
"""check_spec.py — 校验 spec 契约文件，把"靠自觉"的闸门变成退出码。

用法：
    python check_spec.py docs/specs/2026-11-02-xxx.md                # spec 阶段：结构检查
    python check_spec.py docs/specs/2026-11-02-xxx.md --stage verify # 核销阶段：条款→用例→结果
    python check_spec.py docs/specs/2026-11-02-xxx.md --json         # 机器可读输出

退出码：0 = 通过（可带警告）；1 = 有错误，不得进入下一步。

检查项：
    spec 阶段   8 节齐全（含技术蓝图）、C 条款编号连续、每条含前置/后置/失败/不变式、
                A 验收项编号连续、三问完整、非目标非空
    verify 阶段 在 spec 阶段之上，要求第 9 节核销表覆盖每条 C 条款：
               用例名带条款号、结果 ✅、路径真实性已填
"""

import argparse
import io
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REQUIRED_SECTIONS = {
    1: "背景与目标",
    2: "方案自审",
    3: "技术蓝图",
    4: "非目标",
    5: "契约条款",
    6: "验收标准",
    7: "边界与异常",
    8: "三问完整性检查",
}
CLAUSE_LABELS = ("前置", "后置", "失败", "不变式")


def split_sections(text):
    """Return {section_number: (title, body)} for '## <n>. <title>' headings."""
    pattern = re.compile(r"^##\s*(\d+)\s*[.、]?\s*(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections = {}
    for i, m in enumerate(matches):
        number = int(m.group(1))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[number] = (m.group(2).strip(), text[m.end():end])
    return sections


def parse_clauses(body):
    """Return [(n, title, clause_body)] for '### C<n> title' headings."""
    pattern = re.compile(r"^#{3,6}\s*C(\d+)\b[ \t]*(.*)$", re.MULTILINE)
    matches = list(pattern.finditer(body))
    clauses = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        clauses.append((int(m.group(1)), m.group(2).strip(), body[m.end():end]))
    return clauses


def parse_acceptance(body):
    """Return [(n, checked, text)] for '- [ ] A<n> ...' items."""
    items = []
    for line in body.splitlines():
        m = re.match(r"^\s*[-*]\s+\[([ xX])\]\s*A(\d+)\b(.*)$", line)
        if m:
            items.append((int(m.group(2)), m.group(1).lower() == "x", m.group(3).strip()))
    return items


def parse_reconciliation(body):
    """Return [(clause_n, cells)] for table rows whose first cell is C<n>."""
    rows = []
    for line in body.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue
        m = re.match(r"^C(\d+)$", cells[0])
        if m:
            rows.append((int(m.group(1)), cells))
    return rows


def has_placeholder(s):
    """识别模板占位符：<中文>、<YYYY-MM-DD>、<vX.Y.Z>、<...>。

    不能把 <script> / <div> 这类 HTML 标签误判成占位符（条款里出现标签是正常的）。
    """
    for m in re.finditer(r"<([^<>\n]{1,40})>", s):
        inner = m.group(1)
        if re.search(r"[\u4e00-\u9fff]", inner):      # <一句话> / <文件>
            return True
        if re.search(r"[A-Z]", inner):                # <YYYY-MM-DD> / <URL> / <vX.Y.Z>
            return True
        if re.fullmatch(r"\.{2,}|…", inner):          # <...> / <…>
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description="校验 spec 契约文件")
    ap.add_argument("spec", help="spec 文件路径，如 docs/specs/2026-11-02-xxx.md")
    ap.add_argument("--stage", choices=["spec", "verify"], default="spec")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    path = Path(args.spec)
    errors, warnings = [], []
    if not path.is_file():
        errors.append(f"文件不存在：{path}")

    text = io.open(path, encoding="utf-8").read() if path.is_file() else ""
    sections = split_sections(text) if text else {}

    # 1. 必需章节
    for number, name in REQUIRED_SECTIONS.items():
        if number not in sections:
            errors.append(f"缺少第 {number} 节「{name}」")
    if args.stage == "verify" and 9 not in sections:
        errors.append("verify 阶段缺少第 9 节「核销记录」")

    # 2. 条款
    clauses = parse_clauses(sections.get(5, ("", ""))[1]) if 5 in sections else []
    if not clauses:
        errors.append("第 5 节没有契约条款（应为 `### C1 ...` 形式）")
    numbers = [n for n, _, _ in clauses]
    if numbers:
        # 连续即可：支持单 spec 从 C1 起，也支持多 spec 项目按项目级序列承接编号（如 C13、C14、C15）
        expected = list(range(numbers[0], numbers[0] + len(numbers)))
        if numbers != expected:
            errors.append(f"条款编号应连续（C1、C2、C3… 或承接序列 C13、C14…），实际为 {numbers}")
    for n, title, body in clauses:
        missing = [label for label in CLAUSE_LABELS if label not in body]
        if missing:
            errors.append(f"C{n}「{title[:24]}」缺少要素：{'、'.join(missing)}")
        if not title:
            errors.append(f"C{n} 没有标题")

    # 3. 验收项
    acceptance = parse_acceptance(sections.get(6, ("", ""))[1]) if 6 in sections else []
    if not acceptance:
        errors.append("第 6 节没有验收项（应为 `- [ ] A1 ...` 形式）")
    a_numbers = [n for n, _, _ in acceptance]
    a_expected = list(range(1, len(a_numbers) + 1))
    if a_numbers and a_numbers != a_expected:
        errors.append(f"验收项编号应连续（A1、A2、A3…），实际为 {a_numbers}")

    # 4. 非目标非空
    if 4 in sections:
        body = sections[4][1]
        meaningful = [
            line.strip().lstrip("-* ").strip()
            for line in body.splitlines()
            if line.strip().startswith(("-", "*"))
        ]
        meaningful = [m for m in meaningful if m and m not in ("不做：", "不做")]
        if not meaningful:
            warnings.append("第 4 节「非目标」看起来是空的——范围蔓延最容易从这里开始")

    # 5. 三问
    if 8 in sections:
        q_body = sections[8][1]
        for mark in "①②③":
            if mark not in q_body:
                errors.append(f"三问完整性检查缺少 {mark}")
        if args.stage == "verify" and re.search(r"-\s*\[ \]\s*[①②③]", q_body):
            errors.append("verify 阶段三问仍有未勾选项")

    # 6. 边界与异常
    if 7 in sections:
        rows = [
            line for line in sections[7][1].splitlines()
            if line.strip().startswith("|") and "---" not in line
        ]
        if len(rows) <= 1:
            warnings.append("第 7 节「边界与异常」没有填写场景")

    # 7. 核销（verify）
    if args.stage == "verify" and 9 in sections:
        rows = parse_reconciliation(sections[9][1])
        by_clause = {}
        for n, cells in rows:
            by_clause.setdefault(n, []).append(cells)
        for n, _, _ in clauses:
            if n not in by_clause:
                errors.append(f"C{n} 在核销表里没有对应行")
                continue
            cells = by_clause[n][0]
            if len(cells) < 4:
                errors.append(f"C{n} 核销行字段不足（需要 条款/用例/结果/路径真实性）")
                continue
            case, result, truth = cells[1], cells[2], cells[3]
            if not re.search(rf"(?<![0-9a-z])c{n}(?![0-9])", case, re.IGNORECASE):
                errors.append(f"C{n} 的用例名未带条款号：{case or '（空）'}")
            if "✅" not in result:
                errors.append(f"C{n} 结果不是 ✅：{result or '（空）'}")
            if not truth or truth in ("-", "—", "无"):
                errors.append(f"C{n} 路径真实性未填写")
        for n in by_clause:
            if n not in numbers:
                warnings.append(f"核销表有 C{n}，但第 4 节没有该条款")

    # 8. 未填占位符
    placeholders = []
    for n, title, body in clauses:
        if has_placeholder(title) or has_placeholder(body):
            placeholders.append(f"C{n}")
    for n, _, item in acceptance:
        if has_placeholder(item):
            placeholders.append(f"A{n}")
    if placeholders and args.stage == "verify":
        errors.append(f"verify 阶段仍有未填占位符：{', '.join(placeholders)}")
    elif placeholders:
        warnings.append(f"仍有未填占位符：{', '.join(placeholders)}（模板正常，签约前应填完）")

    result = {
        "spec": str(path),
        "stage": args.stage,
        "clauses": [n for n, _, _ in clauses],
        "acceptance": [n for n, _, _ in acceptance],
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"spec   : {path}")
        print(f"stage  : {args.stage}")
        print(f"条款   : {', '.join(f'C{n}' for n in result['clauses']) or '（无）'}")
        print(f"验收   : {', '.join(f'A{n}' for n in result['acceptance']) or '（无）'}")
        for w in warnings:
            print(f"WARN   : {w}")
        for e in errors:
            print(f"ERROR  : {e}")
        print(f"结果   : {'PASS' if not errors else 'FAIL'}（{len(errors)} 错误 / {len(warnings)} 警告）")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
