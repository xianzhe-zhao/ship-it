#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_spec.py — spec 契约闸门（v4.7.0）：退出码即结论。

用法：
    python check_spec.py ship-it/docs/specs/2026-11-19-xxx.md --stage draft|spec|verify|accept
    python check_spec.py ship-it/docs/specs/2026-11-19-xxx.md --print-sign-hash
    python check_spec.py ship-it/docs/specs/2026-11-19-xxx.md --stage spec --git-check --base origin/main [--head <ref>]
    python check_spec.py ship-it/docs/specs/2026-11-18-xxx.md --stage spec            # 旧 spec 自动 legacy
    python check_spec.py ship-it/docs/specs/2026-11-18-xxx.md --stage spec --strict   # 强制新规则
    python check_spec.py ... --json

阶段：
    draft   结构 + 条款/验收编号 + 三问（可不勾）
    spec    draft + 签约块（sign_prompt / sign_quote / sign_hash / confirmed_clauses）
    verify  spec + 5 列核销 + 用例文件 / 用例名 / 测试报告 / 分数来源
    accept  verify + 验收块 + A 全勾 + accepted_items 全覆盖

退出码：0 = 通过；1 = 有错误（不得进入下一步）。
路径安全：所有输入路径 resolve() 后必须落在仓库根内；越界 / 符号链接逃逸 = 非零退出。
编码：UTF-8 输入输出；Windows 兼容；仅 Python 3.8+ 标准库。
"""

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from datetime import date as _date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_hash import HASH_SCOPES, hash_for_scope, scope_for_text  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

NEW_RULES_FROM = _date(2026, 11, 19)
STATUS_VALUES = ("draft", "signed", "paused", "accepted")

REQUIRED_SECTIONS = {
    1: "背景与目标",
    2: "方案自审",
    3: "技术蓝图",
    4: "非目标",
    5: "契约条款",
    6: "验收标准",
    7: "边界与异常",
    8: "三问完整性检查",
    9: "核销记录",
}
CLAUSE_LABELS = ("前置", "后置", "失败", "不变式")
RECON_HEADER = ["条款", "用例名", "用例文件", "结果", "路径真实性"]

COMMON_FM_KEYS = [
    "spec_version",
    "spec_revision",
    "status",
    "sign_prompt",
    "sign_requested_at",
    "signed_by",
    "signed_at",
    "sign_quote",
    "sign_hash",
    "confirmed_clauses",
    "decisions",
]
ACCEPT_FM_KEYS = [
    "accept_prompt",
    "accept_requested_at",
    "accepted_by",
    "accepted_at",
    "accept_quote",
    "accepted_items",
    "accept_commit",
]
SIGN_PROMPT_KEYWORDS = [
    "刚才的说明可能造成误解",
    "是否要签约",
    "发送",
    "签约",
    "两个字",
    "不会开始编码",
    "不要加标点、引号或其他内容",
]
ACCEPT_PROMPT_KEYWORDS = [
    "刚才的说明可能造成误解",
    "是否需要验收",
    "发送",
    "验收",
    "两个字",
    "不会进入 PR",
    "不要加标点、引号或其他内容",
]


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


SECTION1_RE = re.compile(r"^##\s*1[.\u3001\s]")
SECTION9_RE = re.compile(r"^##\s*9[.\u3001\s]")
ACCEPTANCE_CHECK_RE = re.compile(r"^(\s*[-*]\s+\[)[xX](\]\s+\*{0,2}A\d+\b)")


def normalize_acceptance_marks(lines):
    """代码层归一化：- [x] A<n> / - [X] A<n> → - [ ] A<n>；只动 A 行，§9 已排除。"""
    return [ACCEPTANCE_CHECK_RE.sub(r"\1 \2", line) for line in lines]


def signing_body(text):
    """§§1–8 签约正文：## 1. 行到 ## 9. 前一行，按行 \n 连接（CRLF→LF），不额外追加尾随换行。"""
    lines = normalize_newlines(text).split("\n")
    start = None
    for index, line in enumerate(lines):
        if SECTION1_RE.match(line):
            start = index
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if SECTION9_RE.match(lines[index]):
            end = index
            break
    return "\n".join(normalize_acceptance_marks(lines[start:end]))


def signing_hash(text):
    return sha256_hex(signing_body(text))


def unquote(value):
    pairs = {'"': '"', "'": "'", "\u201c": "\u201d", "\u2018": "\u2019"}
    if len(value) >= 2 and value[0] in pairs and value[-1] == pairs[value[0]]:
        value = value[1:-1]
    return value.strip()


def detect_repo_root():
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(Path.cwd()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return Path(os.path.realpath(proc.stdout.strip()))
    except OSError:
        pass
    return Path(os.path.realpath(str(Path.cwd())))


def is_inside(path, root):
    try:
        child = os.path.normcase(os.path.realpath(str(path)))
        parent = os.path.normcase(os.path.realpath(str(root)))
        return os.path.commonpath([child, parent]) == parent
    except (ValueError, OSError):
        return False


def resolve_in_root(raw, root, label, errors, must_exist=False, want_dir=False):
    """resolve() 后必须仍在仓库根内；拒绝 .. 越界、绝对路径越界、符号链接逃逸。"""
    path = Path(str(raw))
    if not path.is_absolute():
        path = Path.cwd() / path
    real = Path(os.path.realpath(str(path)))
    if not is_inside(real, root):
        errors.append("%s 越出仓库根：%s（解析为 %s）；拒绝 .. 越界、绝对路径越界、符号链接逃逸" % (label, raw, real))
        return None
    if must_exist and not real.exists():
        errors.append("%s 不存在：%s" % (label, raw))
        return None
    if must_exist and want_dir and not real.is_dir():
        errors.append("%s 不是目录：%s" % (label, raw))
        return None
    if must_exist and (not want_dir) and not real.is_file():
        errors.append("%s 不是文件：%s" % (label, raw))
        return None
    return real


def read_utf8(path):
    try:
        with io.open(str(path), "r", encoding="utf-8-sig", newline="") as handle:
            return handle.read(), None
    except UnicodeDecodeError as exc:
        return None, "不是合法 UTF-8：%s" % exc
    except OSError as exc:
        return None, "读取失败：%s" % exc


def parse_name_date(name):
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", name)
    if not match:
        return None
    try:
        return _date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def parse_number_set(value, prefix):
    """解析 C1-C13 / C1,C3 / A1–A13 形式的编号集合。"""
    numbers = set()
    bad = []
    if not value:
        return numbers, bad
    text = value
    for old, new in (("\uff0c", ","), ("\u3001", ","), ("\uff1b", ","), (";", ","), ("\u2013", "-"), ("\u2014", "-"), ("\uff5e", "~")):
        text = text.replace(old, new)
    tokens = [token for token in re.split(r"[,\s]+", text) if token]
    for token in tokens:
        item = token.strip()
        match = re.fullmatch(prefix + r"(\d+)\s*[-\u2013\u2014~\u81f3]\s*" + prefix + r"?(\d+)", item, re.IGNORECASE)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            if start <= end:
                numbers.update(range(start, end + 1))
            else:
                bad.append(item)
            continue
        match = re.fullmatch(prefix + r"(\d+)", item, re.IGNORECASE)
        if match:
            numbers.add(int(match.group(1)))
            continue
        bad.append(item)
    return numbers, bad


def has_placeholder(value):
    """识别模板占位符：<中文>、<YYYY-MM-DD>、<vX.Y.Z>、<...>；不误判 HTML 标签。"""
    for match in re.finditer(r"<([^<>\n]{1,40})>", value):
        inner = match.group(1)
        if re.search(r"[\u4e00-\u9fff]", inner):
            return True
        if re.search(r"[A-Z]", inner):
            return True
        if re.fullmatch(r"\.{2,}|\u2026", inner):
            return True
    return False


def strip_code(text):
    """去掉围栏代码块与行内代码，保留行号（每个输入行对应一个输出行）。"""
    output = []
    in_fence = False
    for line in text.split("\n"):
        if re.match(r"^\s*(\x60{3}|~~~)", line):
            in_fence = not in_fence
            output.append("")
            continue
        if in_fence:
            output.append("")
            continue
        output.append(re.sub(r"\x60[^\x60]*\x60", "", line))
    return "\n".join(output)


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

def split_front_matter(text):
    normalized = normalize_newlines(text)
    lines = normalized.split("\n")
    info = {"has": False, "fm": {}, "body": normalized, "problems": []}
    if not lines or lines[0].strip() != "---":
        return info
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        info["problems"].append("front matter 缺少结束的 --- 行")
        return info
    fm = {}
    for line in lines[1:end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            info["problems"].append("front matter 行不是 key: value 形式：" + stripped[:60])
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key in fm:
            info["problems"].append("front matter 重复键：" + key)
        fm[key] = unquote(value.strip())
    info["has"] = True
    info["fm"] = fm
    info["body"] = "\n".join(lines[end + 1:])
    return info


def split_sections(text):
    """返回 {section_number: (title, body)}，标题形如 ## <n>. <title>。"""
    pattern = re.compile(r"^##\s*(\d+)\s*[.\u3001]?\s*(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections = {}
    for index, match in enumerate(matches):
        number = int(match.group(1))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[number] = (match.group(2).strip(), text[match.end():end])
    return sections


def parse_clauses(body):
    """返回 [(n, title, clause_body)]，标题形如 ### C<n> title。"""
    pattern = re.compile(r"^#{3,6}\s*C(\d+)\b[ \t]*(.*)$", re.MULTILINE)
    matches = list(pattern.finditer(body))
    clauses = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        clauses.append((int(match.group(1)), match.group(2).strip(), body[match.end():end]))
    return clauses


def parse_acceptance(body):
    """返回 [(n, checked, text)]，条目形如 - [ ] A<n> ...。"""
    items = []
    for line in body.splitlines():
        match = re.match(r"^\s*[-*]\s+\[([ xX])\]\s*A(\d+)\b(.*)$", line)
        if match:
            items.append((int(match.group(2)), match.group(1).lower() == "x", match.group(3).strip()))
    return items


def split_row(line):
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if all(re.fullmatch(r":?-{2,}:?", cell or "") for cell in cells):
        return []
    return cells


def clean_cell(value):
    text = value.strip()
    text = text.strip("\x60").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


def parse_reconciliation(body):
    """旧规则：首列为 C<n> 的表格行。"""
    rows = []
    for line in body.splitlines():
        cells = split_row(line)
        if not cells:
            continue
        match = re.match(r"^C(\d+)$", cells[0])
        if match:
            rows.append((int(match.group(1)), cells))
    return rows


def question_states(body):
    states = {"\u2460": "missing", "\u2461": "missing", "\u2462": "missing"}
    for line in body.splitlines():
        for mark in states:
            if mark in line:
                match = re.search(r"\[([ xX])\]", line)
                if match:
                    states[mark] = "checked" if match.group(1).lower() == "x" else "unchecked"
                elif states[mark] == "missing":
                    states[mark] = "unchecked"
    return states


# ---------------------------------------------------------------------------
# 结构检查（新旧共用）
# ---------------------------------------------------------------------------

def check_structure(sections, stage, errors, warnings):
    required = dict(REQUIRED_SECTIONS)
    if stage not in ("verify", "accept"):
        required.pop(9, None)
    for number in sorted(required):
        if number not in sections:
            errors.append("缺少第 %d 节「%s」" % (number, required[number]))

    clauses = parse_clauses(sections.get(5, ("", ""))[1]) if 5 in sections else []
    if not clauses:
        errors.append("第 5 节没有契约条款（应为 ### C1 ... 形式）")
    numbers = [item[0] for item in clauses]
    if numbers:
        expected = list(range(numbers[0], numbers[0] + len(numbers)))
        if numbers != expected:
            errors.append("条款编号应连续（C1、C2、C3… 或承接序列 C13、C14…），实际为 %s" % numbers)
    for number, title, clause_body in clauses:
        missing = [label for label in CLAUSE_LABELS if label not in clause_body]
        if missing:
            errors.append("C%d「%s」缺少要素：%s" % (number, title[:24], "、".join(missing)))
        if not title:
            errors.append("C%d 没有标题" % number)

    acceptance = parse_acceptance(sections.get(6, ("", ""))[1]) if 6 in sections else []
    if not acceptance:
        errors.append("第 6 节没有验收项（应为 - [ ] A1 ... 形式）")
    a_numbers = [item[0] for item in acceptance]
    a_expected = list(range(1, len(a_numbers) + 1))
    if a_numbers and a_numbers != a_expected:
        errors.append("验收项编号应连续（A1、A2、A3…），实际为 %s" % a_numbers)

    if 4 in sections:
        meaningful = []
        for line in sections[4][1].splitlines():
            if line.strip().startswith(("-", "*")):
                item = line.strip().lstrip("-* ").strip()
                if item and item not in ("不做：", "不做"):
                    meaningful.append(item)
        if not meaningful:
            warnings.append("第 4 节「非目标」看起来是空的——范围蔓延最容易从这里开始")

    if 8 in sections:
        states = question_states(sections[8][1])
        for mark in ("\u2460", "\u2461", "\u2462"):
            state = states[mark]
            if state == "missing":
                errors.append("三问完整性检查缺少 %s" % mark)
            elif stage in ("spec", "verify", "accept") and state != "checked":
                errors.append("三问 %s 在 spec/verify/accept 阶段必须已勾选" % mark)

    if 7 in sections:
        rows = [line for line in sections[7][1].splitlines() if line.strip().startswith("|") and "---" not in line]
        if len(rows) <= 1:
            warnings.append("第 7 节「边界与异常」没有填写场景")

    placeholders = []
    for number, title, clause_body in clauses:
        if has_placeholder(title) or has_placeholder(clause_body):
            placeholders.append("C%d" % number)
    for number, _checked, item in acceptance:
        if has_placeholder(item):
            placeholders.append("A%d" % number)
    if placeholders:
        if stage in ("spec", "verify", "accept"):
            errors.append("仍有未填占位符：%s" % "、".join(placeholders))
        else:
            warnings.append("仍有未填占位符：%s（模板正常，签约前应填完）" % "、".join(placeholders))
    # C9：条款 revision 完整性校验（criterion amendments 防作弊）
    # 规则：C 条款标题含 revision: <n>；若 n>1（被改过），条款正文必须含"修订台账"
    #       且台账里必须有对应 rev 记录；缺台账/缺 evidence/矛盾台账 = FAIL（fail closed）
    if stage in ("spec", "verify", "accept"):
        for number, title, clause_body in clauses:
            rev_match = re.search(r"revision\s*[:：]\s*(\d+)", title)
            if not rev_match:
                continue  # 无 revision 标注的条款不强制（向后兼容旧 spec）
            rev_num = int(rev_match.group(1))
            if rev_num > 1:
                # 被改过的条款：必须有修订台账
                if "修订台账" not in clause_body and "修订記錄" not in clause_body:
                    errors.append('C%d revision=%d (>1) 但缺修订台账——改标准必须保留原标准并记台账（C9）' % (number, rev_num))
                    continue
                # 台账里必须有对应 rev 记录（至少提到 rev<num> 或 rev<num>）
                if not re.search(r"rev\s*%d\b" % rev_num, clause_body):
                    errors.append("C%d revision=%d 但台账缺 rev%d 记录（C9）" % (number, rev_num, rev_num))
                # 台账缺 evidence/reason（台账条目应有"原因"或"依据"或"authority"）
                ledger_lines = [l for l in clause_body.splitlines() if "rev" in l and (str(rev_num) in l or "rev1" in l)]
                has_evidence = any("原因" in l or "依据" in l or "authority" in l or "evidence" in l.lower() for l in ledger_lines)
                if not has_evidence:
                    errors.append("C%d 修订台账缺 evidence/reason/authority（C9 fail closed）" % number)
    # C6：已验收条款被改强制解冻重跑——由 check_thaw 在 verify/accept 阶段做真正的关联文件比对
    # （原 C16 空壳仅查"解冻"字符串包含+WARNING，已废弃；C6 用 git diff 比对关联文件清单）
    return clauses, acceptance


# ---------------------------------------------------------------------------
# 新规则：front matter / 签约块 / 验收块 / C9 / 长度 / 禁用词
# ---------------------------------------------------------------------------

def load_hard_forbidden(root, warnings):
    candidates = [
        Path(os.path.realpath(str(Path(__file__)))).parent.parent / "references" / "rule-style.md",
        root / "ship-it" / "references" / "rule-style.md",
        root / "references" / "rule-style.md",
    ]
    path = None
    for candidate in candidates:
        if candidate.is_file():
            path = candidate
            break
    if path is None:
        warnings.append("未找到 ship-it/references/rule-style.md，跳过硬禁用词检查")
        return []
    text, error = read_utf8(path)
    if error:
        warnings.append("读取 rule-style.md 失败：%s" % error)
        return []
    words = []
    inside = False
    for line in text.split("\n"):
        stripped = line.strip()
        if "BEGIN:hard-forbidden" in stripped:
            inside = True
            continue
        if "END:hard-forbidden" in stripped:
            inside = False
            continue
        if not inside:
            continue
        if not stripped or stripped.startswith("<!--") or stripped.startswith("#"):
            continue
        if stripped.startswith("\x60\x60\x60") or stripped.startswith("~~~"):
            continue
        word = stripped.lstrip("-* ").strip().strip("\x60").strip()
        if word:
            words.append(word)
    if not words:
        warnings.append("rule-style.md 的 hard-forbidden 块为空，跳过硬禁用词检查")
    return words


def check_pause_records(spec_name, fm, errors, warnings):
    """C8[A4-C]：spec status=paused 时校验 pause/复盘记录存在。

    从 spec 文件名提取日期，校验同日 pause 记录 + 复盘记录存在。
    """
    # 从 spec 文件名提取日期（YYYY-MM-DD-...）
    match = re.match(r"(\d{4}-\d{2}-\d{2})", spec_name)
    if not match:
        warnings.append("C8[A4-C]：无法从 spec 文件名提取日期，跳过 pause/复盘记录校验：%s" % spec_name)
        return
    date_str = match.group(1)
    # 校验 paused_at / pause_reason 字段存在
    paused_at = fm.get("paused_at", "").strip()
    pause_reason = fm.get("pause_reason", "").strip()
    if not paused_at:
        errors.append("C8[A4-C]：paused 状态缺 paused_at 字段")
    if not pause_reason:
        errors.append("C8[A4-C]：paused 状态缺 pause_reason 字段")
    # 校验 pause 记录 + 复盘记录文件存在（相对于仓库根，check_spec 的 root）
    # check_pause_records 不知道 root，由调用方传入；此处用相对 docs/reviews/ 判断
    # 注意：root 在 main 里已知，但 check_front_matter 未传 root；改用 warnings 提示需配合 root 校验
    # 实际文件存在性校验在 main 里补充调用 check_pause_files


def check_pause_files(spec_name, root, errors, warnings):
    """C8[A4-C]：校验 pause 记录 + 复盘记录文件存在（需 root）。"""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", spec_name)
    if not match:
        return
    date_str = match.group(1)
    reviews_dir = os.path.join(root, "docs", "reviews")
    pause_file = os.path.join(reviews_dir, "%s-pause.md" % date_str)
    retro_file = os.path.join(reviews_dir, "%s-retrospective.md" % date_str)
    if not os.path.isfile(pause_file):
        errors.append("C8[A4-C]：pause 记录不存在：%s" % pause_file.replace("\\", "/"))
    if not os.path.isfile(retro_file):
        errors.append("C8[A4-C]：复盘记录不存在：%s" % retro_file.replace("\\", "/"))


def check_front_matter(fm_info, stage, errors, warnings, spec_name=""):
    fm = fm_info["fm"]
    problems = list(fm_info["problems"])
    if not fm_info["has"]:
        if stage == "draft":
            warnings.append("缺少 front matter（新 spec 签约前必须补齐固定键）")
        else:
            errors.append("缺少 front matter（固定键见 spec 第 3 节数据格式）")
        return
    for problem in problems:
        if stage == "draft":
            warnings.append("front matter: " + problem)
        else:
            errors.append("front matter: " + problem)
    status = fm.get("status", "").strip()
    if not status:
        if stage == "draft":
            warnings.append("front matter 缺少 status")
        else:
            errors.append("front matter 缺少 status（draft/signed/accepted）")
    elif status not in STATUS_VALUES:
        errors.append("status 只能是 draft/signed/paused/accepted，实际：%s" % status)
    # C8[A4-C]：paused 状态校验 pause/复盘记录存在
    if status == "paused":
        check_pause_records(spec_name, fm, errors, warnings)
    revision = fm.get("spec_revision", "").strip()
    if not revision:
        if stage == "draft":
            warnings.append("front matter 缺少 spec_revision（签约前必须补齐）")
        else:
            errors.append("front matter 缺少 spec_revision（整数，从 1 开始）")
    elif not re.fullmatch(r"\d+", revision) or int(revision) < 1:
        errors.append("spec_revision 必须是 >=1 的整数，实际：%r" % revision)
    scope = (fm.get("hash_scope") or "").strip().lower()
    if scope:
        if scope not in HASH_SCOPES:
            errors.append("hash_scope 只能是 %s，实际：%r" % ("/".join(HASH_SCOPES), scope))
    elif stage != "draft":
        warnings.append("front matter 缺少 hash_scope，按历史规则推断；新 spec 必须显式写 full_body / sections_1_8 / sections_1_8_a_normalized")
    if stage == "draft":
        for key in COMMON_FM_KEYS + ACCEPT_FM_KEYS:
            if key not in fm:
                warnings.append("front matter 缺少键：%s（签约/验收前必须补齐）" % key)
        return
    for key in COMMON_FM_KEYS:
        if key not in fm:
            errors.append("front matter 缺少键：%s" % key)
    for key in ACCEPT_FM_KEYS:
        if key not in fm:
            if stage == "accept":
                errors.append("front matter 缺少键：%s" % key)
            else:
                warnings.append("front matter 缺少键：%s（验收前补齐）" % key)


def check_sign_block(fm, body_hash, clause_numbers, errors, warnings):
    for key in COMMON_FM_KEYS:
        if key not in fm:
            errors.append("签约块缺字段：%s" % key)
            continue
        value = fm[key].strip()
        if not value:
            errors.append("签约块字段为空：%s" % key)
        elif has_placeholder(value):
            errors.append("签约块字段仍是占位符：%s" % key)
    status = fm.get("status", "").strip()
    if status not in ("signed", "accepted"):
        errors.append("status 必须为 signed（已签约）或 accepted，实际：%s" % (status or "（空）"))
    quote = fm.get("sign_quote", "").strip()
    if quote != "签约":
        errors.append("sign_quote 必须严格等于“签约”，实际：%r" % quote)
    hash_value = fm.get("sign_hash", "").strip().lower()
    if hash_value != body_hash:
        errors.append("sign_hash 与当前 spec §§1–8 不匹配（§§1–8 SHA-256 = %s）；§§1–8 改动后必须回 draft 重签（§9 不参与）" % body_hash)
    prompt = fm.get("sign_prompt", "")
    missing = [keyword for keyword in SIGN_PROMPT_KEYWORDS if keyword not in prompt]
    if missing:
        errors.append("sign_prompt 缺少关键词：%s" % "、".join(missing))
    numbers, bad = parse_number_set(fm.get("confirmed_clauses", ""), "C")
    if bad:
        errors.append("confirmed_clauses 无法解析：%s" % "、".join(bad))
    missing_clauses = sorted(set(clause_numbers) - numbers)
    if missing_clauses:
        errors.append("confirmed_clauses 未覆盖条款：%s" % "、".join("C%d" % n for n in missing_clauses))
    extra = sorted(numbers - set(clause_numbers))
    if extra:
        warnings.append("confirmed_clauses 含未定义条款：%s" % "、".join("C%d" % n for n in extra))


def check_accept_block(fm, acceptance, errors, warnings, current_scope=None):
    scope = (fm.get("hash_scope") or "").strip().lower() or (current_scope or "")
    if scope == "sections_1_8" and acceptance and all(item[1] for item in acceptance):
        errors.append("验收勾选 A 后 hash_scope 必须改为 sections_1_8_a_normalized（front matter 不参与 sign_hash，sign_hash 不变）")
    for key in ACCEPT_FM_KEYS:
        if key not in fm:
            errors.append("验收块缺字段：%s" % key)
            continue
        value = fm[key].strip()
        if not value:
            errors.append("验收块字段为空：%s" % key)
        elif has_placeholder(value):
            errors.append("验收块字段仍是占位符：%s" % key)
    quote = fm.get("accept_quote", "").strip()
    if quote != "验收":
        errors.append("accept_quote 必须严格等于“验收”，实际：%r" % quote)
    prompt = fm.get("accept_prompt", "")
    missing = [keyword for keyword in ACCEPT_PROMPT_KEYWORDS if keyword not in prompt]
    if missing:
        errors.append("accept_prompt 缺少关键词：%s" % "、".join(missing))
    commit = fm.get("accept_commit", "").strip()
    if not commit:
        errors.append("accept_commit 为空（验收时必须写入当前 HEAD SHA）")
    elif not re.fullmatch(r"[0-9a-fA-F]{4,64}", commit):
        errors.append("accept_commit 不是合法 SHA：%s" % commit)
    numbers, bad = parse_number_set(fm.get("accepted_items", ""), "A")
    if bad:
        errors.append("accepted_items 无法解析：%s" % "、".join(bad))
    missing_items = sorted(set(item[0] for item in acceptance) - numbers)
    if missing_items:
        errors.append("accepted_items 未覆盖验收项：%s" % "、".join("A%d" % n for n in missing_items))
    unchecked = [item[0] for item in acceptance if not item[1]]
    if unchecked:
        errors.append("验收阶段 A 项未全勾：%s" % "、".join("A%d" % n for n in unchecked))


def check_entry_inventory(sections, errors, warnings):
    """C8：有 UI 变更时 §2 必须有入口清单；无 UI 变更时显式写“入口清单：无 UI 变更”。"""
    if 3 not in sections:
        return
    ui_line = None
    for line in sections[3][1].splitlines():
        if "前端" in line:
            ui_line = line
            break
    if ui_line is None:
        return
    ui_changed = "无变更" not in ui_line
    section2 = sections.get(2, ("", ""))[1]
    inventory = None
    for line in section2.splitlines():
        if "入口清单" in line:
            inventory = line.strip()
            break
    if ui_changed:
        if inventory is None:
            errors.append("§3 前端有变更，但 §2 没有 入口清单：...（C8：入口清单必须来自架构扫描，不能凭印象）")
        elif "无 UI 变更" in inventory:
            errors.append("§3 前端有变更，但 §2 入口清单写成“无 UI 变更”（C8：两者必须一致）")
    elif inventory is None:
        warnings.append("§2 未写 入口清单：无 UI 变更（C8 要求无 UI 变更也要显式声明）")


def check_new_specific(text, sections, clauses, stage, root, errors, warnings):
    check_entry_inventory(sections, errors, warnings)
    if 2 in sections:
        for match in re.finditer(r"\*\*\s*C(\d+)", sections[2][1]):
            errors.append("§2 不得出现 **C%s 标签（流程规则用 P1..Pn，产品条款用 C1..Cn）" % match.group(1))
    if 1 in sections:
        background = sections[1][1].split("\n")
        stop = None
        for index, line in enumerate(background):
            if "需求澄清记录" in line:
                stop = index
                break
        if stop is not None:
            background = background[:stop]
        line_count = len([line for line in background if line.strip()])
        if line_count > 5:
            errors.append("§1 背景不得超过 5 行（需求澄清记录之前），实际 %d 行" % line_count)
    # C7：§1 需求澄清记录分轮校验（draft 阶段）
    if stage == "draft" and 1 in sections:
        section1 = sections[1][1]
        clar_start = None
        for index, line in enumerate(section1.split("\n")):
            if "需求澄清记录" in line:
                clar_start = index
                break
        if clar_start is not None:
            clar_text = section1.split("\n")[clar_start:]
            # 找分轮序号 R1/R2/...
            round_nums = []
            for line in clar_text:
                for m in re.finditer(r"\bR(\d+)\b", line):
                    round_nums.append(int(m.group(1)))
            if not round_nums:
                errors.append("C7：§1 需求澄清记录无分轮序号（须 R1/R2/…，≥1 轮）")
            else:
                nums = sorted(set(round_nums))
                # 序号连续不跳跃（从 1 开始）
                expected = list(range(1, nums[-1] + 1))
                if nums != expected:
                    errors.append("C7：§1 分轮序号不连续（应 R1..R%d 连续，实际 %s）" % (
                        nums[-1], "、".join("R%d" % n for n in nums)))
                # 每轮须有"查验"和"据此提问"两栏（在含 R<n> 的行或其后续行块里）
                for rn in nums:
                    # 找该轮的文本块（R<n> 到下一个 R<m> 前）
                    block_lines = []
                    capturing = False
                    for line in clar_text:
                        if re.search(r"\bR%d\b" % rn, line):
                            capturing = True
                            block_lines.append(line)
                            continue
                        if capturing and re.search(r"\bR\d+\b", line):
                            break
                        if capturing:
                            block_lines.append(line)
                    block = "\n".join(block_lines)
                    if "查验" not in block:
                        errors.append("C7：R%d 缺'查验'栏（须写本轮查验了什么）" % rn)
                    if "据此提问" not in block and "据此问" not in block:
                        errors.append("C7：R%d 缺'据此提问'栏（须写据此问了什么）" % rn)
                    # C7[B10]：每轮单问题启发式——"据此提问"栏只含一个核心问题（一个问号或一个 Q 标记）
                    question_marks = block.count("？") + block.count("?")
                    q_markers = len(re.findall(r"\bQ\d+\b", block))
                    if question_marks > 1 or q_markers > 1:
                        errors.append("C7[B10]：R%d '据此提问'栏含 %d 个问号/%d 个 Q 标记，每轮只问一个最关键问题" % (rn, question_marks, q_markers))
    for number, _title, clause_body in clauses:
        length = len(clause_body)
        if length > 800:
            errors.append("C%d 条款正文 %d 字符，超过 800 上限（拆分或删废话，保留前置/后置/失败/不变式）" % (number, length))
        elif length > 600:
            warnings.append("C%d 条款正文 %d 字符，超过 600 建议上限" % (number, length))
    words = load_hard_forbidden(root, warnings)
    if words:
        scanned = strip_code(text)
        for word in words:
            hits = list(re.finditer(re.escape(word), scanned))
            for match in hits[:5]:
                line_number = scanned.count("\n", 0, match.start()) + 1
                errors.append("第 %d 行出现硬禁用词「%s」（清单见 ship-it/references/rule-style.md）" % (line_number, word))
            if len(hits) > 5:
                errors.append("硬禁用词「%s」出现 %d 次（仅列出前 5 处）" % (word, len(hits)))


def check_analysis_artifact(text, sections, stage, root, errors, warnings):
    """C9[A5-C]：draft 阶段校验方案分析产出物（先分析后契约）。

    三点校验：
    ① spec §1 或 §2 引用方案分析产出物路径（.html 结尾的相对路径）
    ② 该路径文件存在于仓库
    ③ 该产出物含决策树结构标记 token（选项/推荐/决策树/理由）

    任一不满足 → draft 不通过 → 无法签约（借 draft 先于 sign 的状态机天然保证顺序）。
    """
    if stage != "draft":
        return
    # ① 扫描 §1/§2 正文，找 .html 结尾的相对路径（方案分析产出物）
    candidate_paths = []
    for sec_num in (1, 2):
        if sec_num not in sections:
            continue
        body = sections[sec_num][1]
        for m in re.finditer(r'(docs/reviews/[^\s`"\']+\.(?:html|htm))', body):
            candidate_paths.append(m.group(1))
    if not candidate_paths:
        errors.append("C9[A5-C]：§1/§2 未引用方案分析产出物路径（须含 docs/reviews/*.html 路径）")
        return
    # ② 校验至少一个路径文件存在
    found_path = None
    for rel in candidate_paths:
        real = os.path.join(root, rel.replace("/", os.sep))
        if os.path.isfile(real):
            found_path = rel
            break
    if not found_path:
        errors.append("C9[A5-C]：方案分析产出物文件不存在，引用路径：%s" % "、".join(candidate_paths))
        return
    # ③ 校验产出物含决策树结构标记 token
    real = os.path.join(root, found_path.replace("/", os.sep))
    try:
        with open(real, "r", encoding="utf-8") as fh:
            artifact_text = fh.read()
    except OSError as exc:
        errors.append("C9[A5-C]：方案分析产出物读取失败：%s（%s）" % (found_path, exc))
        return
    tokens = ("选项", "推荐", "决策树", "理由")
    hits = [tok for tok in tokens if tok in artifact_text]
    if len(hits) < 2:
        errors.append("C9[A5-C]：方案分析产出物 %s 缺决策树结构标记（须含 ≥2 个：选项/推荐/决策树/理由，实际 %s）" % (found_path, "、".join(hits) if hits else "无"))


def _is_v5_or_later(spec_version):
    """C13/C31 仅对 v5.0.0+ spec 生效（执行模式节、产出物 schema 是 v5.0.0 新增）。

    spec_version 形如 "5.0.0"（v5+）或 "2"（旧版主版本号）。返回 True 当且仅当
    主版本号 >= 5。无法解析时返回 False（保守不溯及）。
    """
    if not spec_version:
        return False
    match = re.match(r"(\d+)(?:\.\d+)*", spec_version)
    if not match:
        return False
    try:
        return int(match.group(1)) >= 5
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# C13 产出物 schema 化（每步产出必含字段，Python dict 校验，零依赖）
# ---------------------------------------------------------------------------

# 每步产出物的必含字段 schema（C13）。键=步骤号，值=该步产出必须包含的字段名集合。
# 这些字段是"过闸门"的最低产出要求；spec §9 核销表 5 列由既有 check_reconciliation 校验。
STEP_OUTPUT_SCHEMA = {
    1: {"优化后需求", "澄清记录"},
    2: {"方案自审", "技术蓝图"},
    3: {"diff", "自检", "条款追溯"},
    4: {"测试报告"},
    5: {"核销表"},
    6: {"验收清单"},
    7: {"版本号", "CHANGELOG"},
    8: {"发布记录"},
    9: {"清理记录"},
}

# spec 正文中应当出现的关键产出物标记（用于校验 spec 是否声明了每步产出要求）。
_STEP_OUTPUT_MARKERS = {
    3: ("diff", "自检", "条款追溯"),
    5: ("核销记录",),
}


def check_step_output_schema(text, sections, stage, errors, warnings):
    """C13：校验 spec 声明了关键步骤的产出物必含字段。

    check_spec.py 校验的是 spec 契约本身（非运行时产出），故此处校验 spec 正文是否
    "声明了 Step 3 产出必含 diff+自检+条款追溯、Step 5 产出必含核销表 5 列等要求。
    运行时产出由各步汇报与 §9 核销表（check_reconciliation）兜底。零依赖，纯 dict。
    """
    if stage == "draft":
        return
    body = text
    for step, markers in _STEP_OUTPUT_MARKERS.items():
        missing = [m for m in markers if m not in body]
        if missing:
            errors.append(
                "C13 产出物 schema：spec 未声明 Step %d 产出必含字段：%s（每步产出必须含规定字段才能过闸门）"
                % (step, "、".join(missing))
            )


# ---------------------------------------------------------------------------
# C16 每步文件边界机器化（路径白名单校验，白名单由 spec §2 声明）
# ---------------------------------------------------------------------------

# §2 中文件边界声明的解析：形如
#   ### 文件边界
#   - Step 3: ship-it/scripts/*, docs/...
#   - Step 5: docs/specs/*
# 每行 "Step <n>:" 后跟逗号分隔的 glob/前缀。脚本据此校验 git 改动文件不越界。
_FILE_BOUNDARY_HEAD_RE = re.compile(r"^#{2,6}\s*文件边界")
_STEP_BOUNDARY_LINE_RE = re.compile(r"^[-*]\s*Step\s*(\d+)\s*[：:]\s*(.+)$")


def parse_file_boundaries(section2_body):
    """解析 §2「文件边界」小节，返回 {step: [prefix,...]}；无声明返回 {}。"""
    if not section2_body:
        return {}
    lines = section2_body.split("\n")
    boundaries = {}
    in_boundary = False
    for line in lines:
        if _FILE_BOUNDARY_HEAD_RE.match(line):
            in_boundary = True
            continue
        if in_boundary and re.match(r"^#{2,6}\s", line):
            break
        if not in_boundary:
            continue
        match = _STEP_BOUNDARY_LINE_RE.match(line)
        if not match:
            continue
        step = int(match.group(1))
        raw = match.group(2).strip()
        prefixes = []
        for part in re.split(r"[、,，;；\s]+", raw):
            part = part.strip().strip("`").strip()
            if part:
                prefixes.append(part)
        if prefixes:
            boundaries.setdefault(step, []).extend(prefixes)
    return boundaries


def _path_matches_prefix(path, prefix):
    """前缀匹配：支持 glob 通配 * 与目录前缀。"""
    path = path.replace("\\", "/")
    prefix = prefix.replace("\\", "/")
    if "*" in prefix:
        import fnmatch
        return fnmatch.fnmatch(path, prefix)
    if prefix.endswith("/"):
        return path.startswith(prefix)
    return path == prefix or path.startswith(prefix + "/")


def check_file_boundaries(sections, root, base_ref, stage, errors, warnings):
    """C16：若 spec §2 声明了文件边界白名单，则校验 base..HEAD 的改动文件不越界。

    白名单由 spec 声明（非硬编码），脚本只做校验不做拦截决策。无声明时仅 WARN
    （向后兼容既有 spec），有声明白被违反时 FAIL。
    """
    if stage == "draft":
        return
    section2_body = sections.get(2, ("", ""))[1]
    boundaries = parse_file_boundaries(section2_body)
    if not boundaries:
        warnings.append("C16：spec §2 未声明「文件边界」白名单，跳过路径白名单校验（新 spec 应声明每步可改文件）")
        return
    if not base_ref:
        warnings.append("C16：未提供 --base，无法校验文件边界（需 --git-check --base <ref>）")
        return
    code, out, _err = run_git(root, ["diff", "--name-only", "%s..HEAD" % base_ref])
    if code != 0:
        warnings.append("C16：无法读取 %s..HEAD 改动文件清单：%s" % (base_ref, out.strip()))
        return
    changed = [line.strip().replace("\\", "/") for line in out.split("\n") if line.strip()]
    if not changed:
        return
    # 每个改动文件必须落在至少一个步骤的白名单内；未落入任何步骤白名单即越界。
    violations = []
    for path in changed:
        matched = False
        for step, prefixes in boundaries.items():
            if any(_path_matches_prefix(path, p) for p in prefixes):
                matched = True
                break
        if not matched:
            violations.append(path)
    if violations:
        errors.append(
            "C16 文件边界越界：以下文件不在 spec §2 声明的任何步骤白名单内：%s（每步只能改对应步骤的文件）"
            % "、".join(violations[:10])
        )


# ---------------------------------------------------------------------------
# C31 执行模式机器闸门（spec 必须含执行模式节且已选定）
# ---------------------------------------------------------------------------

_EXEC_MODE_HEAD_RE = re.compile(r"^#{2,6}\s*[\d.]*\s*执行模式", re.MULTILINE)
_EXEC_MODE_CHOSEN_RE = re.compile(r"本次执行模式\*{0,2}[：:]\s*\*{0,2}\s*(单干|团队)")


def check_execution_mode(text, stage, errors, warnings):
    """C31：--stage spec 校验 spec 必须含执行模式节且已选定（单干或团队）。

    缺节或未选定即 FAIL，与签约块校验同级。AI 不得自选/默认（C29）。
    """
    if stage == "draft":
        return
    if not _EXEC_MODE_HEAD_RE.search(text):
        errors.append("C31：spec 缺少「执行模式」节（必须由用户在签约前裁定单干或团队，AI 不得自选）")
        return
    match = _EXEC_MODE_CHOSEN_RE.search(text)
    if not match:
        errors.append("C31：spec 执行模式节未选定模式（必须明确「单干」或「团队」，由用户裁定）")
        return
    mode = match.group(1)
    if mode == "团队":
        # 团队模式必须列必派角色清单（C29/C30）
        if "必派角色清单" not in text and "必派" not in text:
            errors.append("C31：团队模式未列必派角色清单（C29/C30 要求至少含代码安全员/监察员/裁判员/测试员）")


# ---------------------------------------------------------------------------
# 核销真实性（verify / accept）
# ---------------------------------------------------------------------------

EVIDENCE_KEYS = ["path", "pre_sha256", "post_sha256", "run_started_at", "run_finished_at"]
EVIDENCE_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\*\*)?(path|pre_sha256|post_sha256|run_started_at|run_finished_at)(?:\*\*)?\s*[：:]\s*(.+?)\s*$"
)
SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token|access[_-]?key|private[_-]?key|client[_-]?secret)\s*[:=]"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}"),
]


def sha256_file(path):
    digest = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_timestamp(value):
    text = clean_cell(value or "")
    match = re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?", text)
    if match:
        raw = match.group(0).replace(" ", "T")
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        raw = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", raw)
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    match = re.search(r"\b(\d{10,13})\b", text)
    if match:
        number = int(match.group(1))
        if number > 10 ** 12:
            number = number / 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc)
    return None


def to_aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return value


def parse_evidence_records(report_text):
    records = []
    current = {}
    for line in normalize_newlines(report_text).split("\n"):
        match = EVIDENCE_FIELD_RE.match(line)
        if not match:
            continue
        key = match.group(1)
        value = clean_cell(match.group(2))
        if key == "path":
            if current.get("path"):
                records.append(current)
                current = {}
            current["path"] = value
        elif current.get("path"):
            current[key] = value
    if current.get("path"):
        records.append(current)
    return records


def check_test_evidence(report_text, case_files, root, errors):
    records = parse_evidence_records(report_text)
    by_path = {}
    for record in records:
        rel = record["path"].replace("\\", "/").strip()
        by_path.setdefault(rel, []).append(record)
    for rel in sorted(set(item.replace("\\", "/").strip() for item in case_files)):
        if rel not in by_path:
            errors.append("测试报告缺少 %s 的证据块（path/pre_sha256/post_sha256/run_started_at/run_finished_at）" % rel)
            continue
        record = by_path[rel][-1]
        missing = [key for key in EVIDENCE_KEYS if not record.get(key)]
        if missing:
            errors.append("测试报告 %s 的证据块缺字段：%s" % (rel, "、".join(missing)))
            continue
        file_real = Path(os.path.realpath(str(Path(root) / rel)))
        if not file_real.is_file():
            continue
        current_hash = sha256_file(file_real)
        pre = record["pre_sha256"].strip().lower()
        post = record["post_sha256"].strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", pre):
            errors.append("测试报告 %s 的 pre_sha256 不是 64 位 SHA-256：%r" % (rel, record["pre_sha256"]))
        elif pre != current_hash:
            errors.append("测试报告 %s 的 pre_sha256 与当前文件 SHA-256 不一致（测试文件在运行后被改动，证据作废）" % rel)
        if not re.fullmatch(r"[0-9a-f]{64}", post):
            errors.append("测试报告 %s 的 post_sha256 不是 64 位 SHA-256：%r" % (rel, record["post_sha256"]))
        elif post != current_hash:
            errors.append("测试报告 %s 的 post_sha256 与当前文件 SHA-256 不一致（测试文件在运行中被改动，证据作废）" % rel)
        started = to_aware(parse_timestamp(record["run_started_at"]))
        finished = to_aware(parse_timestamp(record["run_finished_at"]))
        if started is None or finished is None:
            errors.append("测试报告 %s 的 run_started_at / run_finished_at 不是合法 ISO8601 或 epoch：%r / %r" % (
                rel, record["run_started_at"], record["run_finished_at"]))
            continue
        if finished < started:
            errors.append("测试报告 %s 的 run_finished_at 早于 run_started_at（运行窗口非法）" % rel)
        mtime = datetime.fromtimestamp(file_real.stat().st_mtime, tz=datetime.now().astimezone().tzinfo)
        if mtime > started:
            errors.append("测试报告 %s 的文件 mtime %s 晚于 run_started_at %s（运行窗口内/后修改，证据作废）" % (
                rel, mtime.isoformat(), started.isoformat()))


def strip_clause_body(text, number):
    pattern = re.compile(r"(?ms)^#{3,6}\s*C%d\b.*?(?=^#{2,6}\s|\Z)" % number)
    return pattern.sub(lambda match: "\n" * match.group(0).count("\n"), text)


def strip_acceptance_item(text, number):
    pattern = re.compile(r"(?m)^\s*[-*]\s+\[[ xX]\]\s*A%d\b.*$" % number)
    return pattern.sub("", text)


def scan_secret_text(text, label, errors):
    hits = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            hits.append((line_number, match.group(0)))
    if hits:
        errors.append("%s 含密钥模式：第 %s 行 %r（C13：不得含真实密钥值）" % (
            label,
            ",".join(str(item[0]) for item in hits[:5]),
            hits[0][1],
        ))


def check_reconciliation(section_body, clauses, root, errors, warnings):
    lines = section_body.split("\n")
    header = None
    header_index = None
    for index, line in enumerate(lines):
        cells = split_row(line)
        if cells and cells[0] == "条款":
            header = cells
            header_index = index
            break
    if header is None:
        errors.append("§9 缺少核销表表头（应为 条款 | 用例名 | 用例文件 | 结果 | 路径真实性）")
        return
    if header != RECON_HEADER:
        errors.append("§9 核销表必须 5 列且表头为 %s，实际：%s" % (" | ".join(RECON_HEADER), " | ".join(header)))

    rows = []
    for line in lines[header_index + 2:]:
        cells = split_row(line)
        if not cells:
            continue
        match = re.match(r"^C(\d+)$", cells[0])
        if match:
            rows.append((int(match.group(1)), cells))

    report_path = None
    for line in lines:
        match = re.match(r"^\s*[-*]\s*测试报告\s*[\uff1a:]\s*(.+?)\s*$", line)
        if match:
            report_path = clean_cell(match.group(1))
            break
    if not report_path:
        errors.append("§9 缺少 - 测试报告：<path> footer（报告是全局证据）")

    report_text = None
    if report_path:
        report_real = resolve_in_root(report_path, root, "测试报告", errors, must_exist=True)
        if report_real is not None:
            report_text, report_error = read_utf8(report_real)
            if report_error:
                errors.append("测试报告不是合法 UTF-8：%s" % report_error)
                report_text = None

    rows_by_clause = {}
    for number, cells in rows:
        rows_by_clause.setdefault(number, []).append(cells)

    clause_numbers = [item[0] for item in clauses]
    for number in clause_numbers:
        if number not in rows_by_clause:
            errors.append("C%d 在核销表里没有对应行" % number)

    file_cache = {}
    case_texts = []
    case_files = []
    for number in clause_numbers:
        for cells in rows_by_clause.get(number, []):
            if len(cells) < 5:
                errors.append("C%d 核销行字段不足（需要 条款/用例名/用例文件/结果/路径真实性），实际 %d 列" % (number, len(cells)))
                continue
            case_name = clean_cell(cells[1])
            case_file = clean_cell(cells[2])
            result = cells[3]
            truth = cells[4]
            if not case_name or has_placeholder(case_name):
                errors.append("C%d 用例名为空或是占位符" % number)
                continue
            if "✅" not in result:
                errors.append("C%d 结果不是 ✅：%s" % (number, result or "（空）"))
            if not truth or truth in ("-", "\u2014", "\u65e0", "\u5f85\u586b", "\u5f85\u6d4b"):
                errors.append("C%d 路径真实性未填写" % number)
            if not case_file:
                errors.append("C%d 用例文件为空" % number)
                continue
            case_files.append(case_file)
            case_real = resolve_in_root(case_file, root, "C%d 用例文件" % number, errors, must_exist=True)
            if case_real is None:
                continue
            if case_real not in file_cache:
                case_text, case_error = read_utf8(case_real)
                if case_error:
                    errors.append("C%d 用例文件不是合法 UTF-8：%s" % (number, case_error))
                    file_cache[case_real] = ""
                else:
                    file_cache[case_real] = case_text
                    case_texts.append(case_text)
            case_text = file_cache[case_real]
            if case_name not in case_text:
                errors.append("C%d 用例名 %s 未在用例文件 %s 中出现（疑似虚构用例）" % (number, case_name, case_file))
            if report_text is None:
                continue
            occurrences = [index for index, line in enumerate(report_text.split("\n")) if case_name in line]
            if not occurrences:
                errors.append("C%d 用例名 %s 未在测试报告中出现（报告必须含该用例名与 PASS）" % (number, case_name))
                continue
            report_lines = report_text.split("\n")
            for index in occurrences:
                window = report_lines[max(0, index - 2):index + 3]
                if not any(("PASS" in line) or ("通过" in line) or ("✅" in line) for line in window):
                    errors.append("C%d 用例名 %s 在测试报告第 %d 行附近 ±2 行内没有 PASS/通过/✅" % (number, case_name, index + 1))

    if report_text is not None:
        check_test_evidence(report_text, case_files, root, errors)

    for number in rows_by_clause:
        if number not in clause_numbers:
            warnings.append("核销表有 C%d，但第 5 节没有该条款" % number)

    haystack = (report_text or "") + "\n" + "\n".join(case_texts)
    tokens = []
    for line in lines:
        if "核销率" in line:
            continue
        for match in re.finditer(r"(?<![\d/])\d+/\d+(?![\d/])", line):
            tokens.append(match.group(0))
    for token in sorted(set(tokens)):
        if token not in haystack:
            errors.append("§9 的分数 %s 无法在测试报告或用例文件中找到（分数必须有来源）" % token)


def check_thaw(sections, clauses, fm, root, errors, warnings):
    """C6：已验收条款被改强制解冻重跑（WARNING→ERROR）。

    accept_commit 存在时（spec 曾验收过）：
    1. 从核销表用例文件列 + 条款正文提到的文件路径构建每条款的关联文件清单
    2. git diff --name-only accept_commit..HEAD 取改动文件
    3. 动过的条款，核销表路径真实性列须有"解冻：原因 + 重跑结果"，否则 ERROR
    4. 有解冻原因无重跑结果 → ERROR；无关变更解冻已通过 → ERROR
    """
    commit = fm.get("accept_commit", "").strip()
    if not commit:
        return  # legacy spec 无验收基准，跳过
    code, _out, _err = run_git(root, ["cat-file", "-e", commit + "^{commit}"])
    if code != 0:
        return  # accept_commit 非法，由 check_accept_block 负责
    code, out, _err = run_git(root, ["diff", "--name-only", "%s..HEAD" % commit])
    changed = set(line.strip().replace("\\", "/") for line in out.split("\n") if line.strip())

    if not changed:
        return  # 无改动，无需解冻

    # 解析 §9 核销表行（复用 check_reconciliation 的解析逻辑）
    recon_body = sections.get(9, ("", ""))[1] if isinstance(sections.get(9), tuple) else sections.get(9, "")
    rows_by_clause = {}
    header_seen = False
    for line in recon_body.split("\n"):
        cells = split_row(line)
        if not cells:
            continue
        if cells[0] == "条款":
            header_seen = True
            continue
        if not header_seen:
            continue
        match = re.match(r"^C(\d+)$", cells[0])
        if match and len(cells) >= 5:
            rows_by_clause.setdefault(int(match.group(1)), []).append(cells)

    # 从条款正文提取提到的文件路径（`xxx` 或 xxx.py 形式）
    clause_files = {}
    for number, _title, body in clauses:
        files = set()
        for match in re.finditer(r"`([^`]+\.\w+)`", body):
            files.add(match.group(1).replace("\\", "/"))
        for match in re.finditer(r"\b([\w\-./]+/[\w\-./]+\.\w+)\b", body):
            files.add(match.group(1).replace("\\", "/"))
        clause_files[number] = files

    # 合并核销表用例文件列
    for number, rows in rows_by_clause.items():
        for cells in rows:
            if len(cells) >= 3 and cells[2]:
                case_file = cells[2].strip().strip("`").replace("\\", "/")
                if case_file:
                    clause_files.setdefault(number, set()).add(case_file)

    for number, rows in rows_by_clause.items():
        related = clause_files.get(number, set())
        touched = related & changed
        if not touched:
            continue
        for cells in rows:
            truth = cells[4].strip() if len(cells) >= 5 else ""
            if "解冻" not in truth:
                errors.append(
                    "C%d 关联文件被改（%s）但核销表无解冻记录（须'解冻：原因 + 重跑结果'）" % (
                        number, "、".join(sorted(touched)[:4])))
                continue
            has_rerun = any(kw in truth for kw in ("重跑", "PASS", "通过", "✅"))
            if not has_rerun:
                errors.append("C%d 解冻有原因但无重跑结果（路径真实性列须含重跑/PASS/通过/✅）" % number)


# ---------------------------------------------------------------------------
# 旧规则（legacy，文件名日期 < 2026-11-19）
# ---------------------------------------------------------------------------

def check_legacy_reconciliation(section_body, clauses, errors, warnings):
    rows = parse_reconciliation(section_body)
    by_clause = {}
    for number, cells in rows:
        by_clause.setdefault(number, []).append(cells)
    numbers = [item[0] for item in clauses]
    for number, _title, _body in clauses:
        if number not in by_clause:
            errors.append("C%d 在核销表里没有对应行" % number)
            continue
        cells = by_clause[number][0]
        if len(cells) < 4:
            errors.append("C%d 核销行字段不足（需要 条款/用例/结果/路径真实性）" % number)
            continue
        case, result, truth = cells[1], cells[2], cells[3]
        if not re.search(r"(?<![0-9a-z])c%d(?![0-9])" % number, case, re.IGNORECASE):
            errors.append("C%d 的用例名未带条款号：%s" % (number, case or "（空）"))
        if "✅" not in result:
            errors.append("C%d 结果不是 ✅：%s" % (number, result or "（空）"))
        if not truth or truth in ("-", "\u2014", "\u65e0"):
            errors.append("C%d 路径真实性未填写" % number)
    for number in by_clause:
        if number not in numbers:
            warnings.append("核销表有 C%d，但第 5 节没有该条款" % number)


# ---------------------------------------------------------------------------
# git 校验（spec 先于实现 / 验收后无代码变更）
# ---------------------------------------------------------------------------

def run_git(root, arguments):
    try:
        proc = subprocess.run(
            ["git", "-C", str(root)] + list(arguments),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except OSError as exc:
        return 1, "", str(exc)


def rel_posix(path, root):
    return os.path.relpath(str(path), str(root)).replace("\\", "/")


def is_doc_path(path, spec_rel):
    item = path.replace("\\", "/")
    if item == spec_rel:
        return True
    if item.startswith("docs/specs/") or item.startswith("docs/reviews/"):
        return True
    if item.startswith("ship-it/docs/specs/") or item.startswith("ship-it/docs/reviews/"):
        return True
    if item == "CHANGELOG.md":
        return True
    return False


def is_impl_path(path, spec_rel):
    """C4：docs/ 下仅 spec/reviews 算 docs；README.md、ship-it/**、tests/** 等一律算实现文件。"""
    return not is_doc_path(path, spec_rel)


def is_doc_or_spec(path, spec_rel):
    """C3：accept_commit..HEAD 只允许 docs/、CHANGELOG、spec。"""
    item = path.replace("\\", "/")
    if item == spec_rel:
        return True
    if item.startswith("docs/"):
        return True
    return item.rsplit("/", 1)[-1].upper().startswith("CHANGELOG")


def changed_files(root, commit):
    code, out, _err = run_git(root, ["show", "--name-only", "--pretty=format:", "--no-renames", commit])
    if code != 0:
        return None
    return [line.strip().replace("\\", "/") for line in out.split("\n") if line.strip()]


def is_proposal_commit(root, commit, files, spec_rel):
    """C8：d94613d 等提案提交是 docs-only 提案（可带 CHANGELOG），不算实现提交。"""
    code, out, _err = run_git(root, ["show", "-s", "--format=%s", commit])
    subject = out.strip() if code == 0 else ""
    if not any(marker in subject.lower() or marker in subject for marker in ("proposal", "提案")):
        return False
    return all(is_doc_path(item, spec_rel) or item.endswith("CHANGELOG.md") for item in files)


def check_committed_signature(root, spec_rel, commit, label, errors):
    code, committed_text, _err = run_git(root, ["show", "%s:%s" % (commit, spec_rel)])
    if code != 0:
        errors.append("无法读取 spec %s提交内容：%s" % (label, commit[:12]))
        return None
    info = split_front_matter(committed_text)
    committed_fm = info["fm"]
    committed_scope = scope_for_text(committed_text, spec_rel)
    if committed_scope is None:
        committed_hash = signing_hash(committed_text)
        scope_label = "legacy sections_1_8_a_normalized"
    else:
        committed_hash = hash_for_scope(committed_text, committed_scope)
        scope_label = committed_scope
    if committed_fm.get("status", "").strip() not in ("signed", "accepted"):
        errors.append("spec %s提交 %s 的 status 不是 signed：%r" % (label, commit[:12], committed_fm.get("status", "")))
    if committed_fm.get("sign_quote", "").strip() != "签约":
        errors.append("spec %s提交 %s 的 sign_quote 不是“签约”：%r" % (label, commit[:12], committed_fm.get("sign_quote", "")))
    if committed_fm.get("sign_hash", "").strip().lower() != committed_hash:
        errors.append("spec %s提交 %s 的 sign_hash 与提交内正文不匹配（hash_scope=%s；旧 sign_hash 不得复用；当前 hash=%s）" % (
            label, commit[:12], scope_label, committed_hash))
    return committed_hash


def check_accept_range(root, spec_rel, fm, errors, head="HEAD"):
    """C3：accept_commit 存在且 accept_commit..HEAD 只含 docs/CHANGELOG/spec。"""
    commit = fm.get("accept_commit", "").strip()
    if not commit:
        return
    code, _out, _err = run_git(root, ["cat-file", "-e", commit + "^{commit}"])
    if code != 0:
        errors.append("accept_commit 不是仓库内的提交：%s" % commit)
        return
    code, _out, _err = run_git(root, ["merge-base", "--is-ancestor", commit, head])
    if code != 0:
        errors.append("accept_commit 不是 %s 的祖先：%s" % (head, commit))
        return
    code, out, _err = run_git(root, ["diff", "--name-only", "%s..%s" % (commit, head)])
    changed = [line.strip().replace("\\", "/") for line in out.split("\n") if line.strip()]
    bad = [item for item in changed if not is_doc_or_spec(item, spec_rel)]
    if bad:
        errors.append("验收后代码变更（accept_commit..HEAD）：%s；撤销验收并重跑 verify/accept" % "、".join(bad[:8]))


def check_git(spec_real, root, base, stage, fm, current_body_hash, errors, warnings, head="HEAD"):
    """C4/C8：spec 首次提交 docs-only 且已 signed；最新 docs-only 提交已 signed；实现晚于最新 spec 提交；hash 按各提交 hash_scope。"""
    spec_rel = rel_posix(spec_real, root)
    if not base:
        if stage == "accept":
            check_accept_range(root, spec_rel, fm, errors, head)
            return
        errors.append("--git-check 必须提供 --base <ref>（C4：spec 先于实现）")
        return
    code, _out, _err = run_git(root, ["rev-parse", "--verify", "--quiet", base + "^{commit}"])
    if code != 0:
        errors.append("--base 不是有效提交：%s" % base)
        return
    code, out, _err = run_git(root, ["rev-list", "--reverse", "%s..%s" % (base, head)])
    commits = [line.strip() for line in out.split("\n") if line.strip()]
    if not commits:
        errors.append("--base..%s 没有提交，无法校验 spec 先于实现" % head)
        return

    # 降级:commit 数量异常多(>20)且多为单文件 commit(Contents API 逐文件上传特征),
    # 此时 commit 顺序无法反映 spec-first,降级为只检查最终 spec 状态(signed + sign_hash)。
    if len(commits) > 20:
        warnings.append("检测到 %d 个提交(>20,疑似逐文件上传),降级为只检查最终 spec 状态,跳过 commit 顺序校验" % len(commits))
        # 只检查当前工作区的 spec 状态(已在 check_front_matter/check_sign_block 校验)
        if stage == "accept":
            check_accept_range(root, spec_rel, fm, errors, head)
        return

    spec_commits = []
    first_impl = None
    for index, commit in enumerate(commits):
        files = changed_files(root, commit)
        if files is None:
            errors.append("无法读取提交 %s 的文件清单" % commit[:12])
            continue
        if is_proposal_commit(root, commit, files, spec_rel):
            warnings.append("提案提交 %s 按 legacy 跳过实现顺序校验" % commit[:12])
            continue
        if spec_rel in files:
            spec_commits.append(commit)
            impl_in_spec = [item for item in files if is_impl_path(item, spec_rel)]
            if impl_in_spec:
                errors.append("spec 提交 %s 不是 docs-only（含实现文件：%s）；spec 与实现不得同提交" % (
                    commit[:12], "、".join(impl_in_spec[:6])))
        impl = [item for item in files if is_impl_path(item, spec_rel)]
        if impl and first_impl is None:
            first_impl = (index, commit, impl)

    if not spec_commits:
        code, base_out, _err = run_git(root, ["rev-parse", base + "^{commit}"])
        base_commit = base_out.strip() if code == 0 else ""
        base_files = changed_files(root, base_commit) if base_commit else None
        if base_files is not None and spec_rel in base_files:
            spec_commits = [base_commit]
            warnings.append("--base 即最新 spec 提交（C16 重新签约后的基准）：%s" % base_commit[:12])
        else:
            errors.append("spec 未在 %s..%s 中提交，无法校验 spec 先于实现" % (base, head))
            return

    first_spec = spec_commits[0]
    latest_spec = spec_commits[-1]
    check_committed_signature(root, spec_rel, first_spec, "首次", errors)
    latest_hash = check_committed_signature(root, spec_rel, latest_spec, "最新", errors)
    if latest_hash is not None and current_body_hash and latest_hash != current_body_hash:
        errors.append("spec 正文有未提交的修订：最新 docs-only 提交 %s 的正文 SHA-256=%s，当前工作区=%s；修订必须先提交且已 signed" % (
            latest_spec[:12], latest_hash, current_body_hash))

    if first_impl is not None:
        index, commit, impl = first_impl
        anchors = [item for item in spec_commits if (commits.index(item) if item in commits else -1) < index]
        if not anchors:
            errors.append("实现文件提交 %s 早于任何 signed spec 提交（含：%s）；先 spec 后代码" % (
                commit[:12], "、".join(impl[:6])))
        else:
            anchor_hash = check_committed_signature(root, spec_rel, anchors[-1], "实现前最新", errors)
            if anchor_hash is not None and latest_hash is not None and anchor_hash != latest_hash:
                errors.append("实现文件提交 %s 早于最新 signed spec 修订 %s（正文已变更、sign_hash 已更新；实现必须晚于最新修订）" % (
                    commit[:12], latest_spec[:12]))

    if stage == "accept":
        check_accept_range(root, spec_rel, fm, errors, head)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(description="校验 spec 契约（draft/spec/verify/accept 四态）")
    parser.add_argument("spec", nargs="?", help="spec 文件路径，如 ship-it/docs/specs/2026-11-19-xxx.md")
    parser.add_argument("--spec", dest="spec_opt", help="spec 文件路径（位置参数的等价写法）")
    parser.add_argument("--stage", choices=["draft", "spec", "verify", "accept"], default="spec", help="校验阶段")
    parser.add_argument("--print-sign-hash", action="store_true", help="打印 spec 正文 SHA-256 后退出")
    parser.add_argument("--git-check", action="store_true", help="校验 spec 先于实现（需要 --base）")
    parser.add_argument("--base", help="git 基准 ref，如 origin/main 或某个提交")
    parser.add_argument("--head", default="HEAD", help="校验到哪个提交（默认 HEAD；pre-commit 用临时提交）")
    parser.add_argument("--strict", action="store_true", help="强制新规则（旧 spec 也按新规则）")
    parser.add_argument("--legacy", action="store_true", help="强制旧规则（新 spec 禁止使用）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def emit(result, as_json):
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("spec   : %s" % (result.get("spec") or ""))
        print("stage  : %s" % result.get("stage"))
        print("mode   : %s" % (result.get("mode") or "new"))
        clauses = result.get("clauses") or []
        acceptance = result.get("acceptance") or []
        print("条款   : %s" % (", ".join("C%d" % n for n in clauses) if clauses else "（无）"))
        print("验收   : %s" % (", ".join("A%d" % n for n in acceptance) if acceptance else "（无）"))
        if result.get("sign_hash"):
            print("sign   : %s" % result["sign_hash"])
        if result.get("hash_scope"):
            print("scope  : %s" % result["hash_scope"])
        for warning in result["warnings"]:
            print("WARN   : %s" % warning)
        for error in result["errors"]:
            print("ERROR  : %s" % error)
        print("结果   : %s（%d 错误 / %d 警告）" % ("PASS" if result["ok"] else "FAIL", len(result["errors"]), len(result["warnings"])))
    return 0 if result["ok"] else 1


def main(argv=None):
    args = build_parser().parse_args(argv)
    errors = []
    warnings = []
    result = {
        "spec": args.spec or args.spec_opt or "",
        "stage": args.stage,
        "mode": "",
        "sign_hash": "",
        "hash_scope": "",
        "clauses": [],
        "acceptance": [],
        "errors": errors,
        "warnings": warnings,
        "ok": False,
    }
    if args.strict and args.legacy:
        errors.append("--strict 与 --legacy 不能同时使用")
    raw_spec = args.spec or args.spec_opt
    if not raw_spec:
        errors.append("缺少 spec 路径（位置参数或 --spec）")
        return emit(result, args.json)

    root = detect_repo_root()
    spec_real = resolve_in_root(raw_spec, root, "spec 路径", errors, must_exist=True)
    if spec_real is None:
        return emit(result, args.json)
    result["spec"] = str(spec_real)
    text, read_error = read_utf8(spec_real)
    if read_error:
        errors.append("spec 读取失败：%s" % read_error)
        return emit(result, args.json)

    normalized = normalize_newlines(text)
    fm_info = split_front_matter(normalized)
    current_scope = scope_for_text(normalized, spec_real.name)
    body_hash = hash_for_scope(normalized, current_scope) if current_scope else signing_hash(normalized)
    result["sign_hash"] = body_hash
    result["hash_scope"] = current_scope or ""

    if args.print_sign_hash:
        print(body_hash)
        return 0

    name_date = parse_name_date(spec_real.name)
    if args.strict:
        mode = "new"
    elif args.legacy:
        mode = "legacy"
    elif name_date is not None and name_date < NEW_RULES_FROM:
        mode = "legacy"
    else:
        mode = "new"
    result["mode"] = mode
    if args.legacy and name_date is not None and name_date >= NEW_RULES_FROM:
        errors.append("新 spec（文件名日期 >= 2026-11-19）不得使用 --legacy；旧 spec 才走 legacy")
    if args.base and not args.git_check:
        warnings.append("提供了 --base 但未加 --git-check，已忽略")

    sections = split_sections(normalized)
    clauses, acceptance = check_structure(sections, args.stage, errors, warnings)
    result["clauses"] = [item[0] for item in clauses]
    result["acceptance"] = [item[0] for item in acceptance]

    if mode == "legacy":
        if args.stage == "verify":
            if 9 in sections:
                check_legacy_reconciliation(sections[9][1], clauses, errors, warnings)
        if args.stage == "accept":
            warnings.append("legacy spec 没有验收块：--stage accept 只做旧结构校验（旧 spec 按日期放行）")
            if 9 in sections:
                check_legacy_reconciliation(sections[9][1], clauses, errors, warnings)
        if args.git_check:
            warnings.append("legacy spec 没有签约块：跳过 --git-check")
    else:
        check_front_matter(fm_info, args.stage, errors, warnings, spec_real.name)
        check_new_specific(normalized, sections, clauses, args.stage, root, errors, warnings)
        # C9[A5-C]：draft 阶段校验方案分析产出物（先分析后契约）
        check_analysis_artifact(normalized, sections, args.stage, root, errors, warnings)
        # C8[A4-C]：paused 状态校验 pause/复盘记录文件存在
        if fm_info["fm"].get("status", "").strip() == "paused":
            check_pause_files(spec_real.name, root, errors, warnings)
        # C13/C31 是 v5.0.0 新增校验（执行模式节、产出物 schema）；pre-v5.0.0 spec 不溯及。
        spec_version = (fm_info["fm"].get("spec_version", "") or "").strip().strip('"').strip("'")
        if _is_v5_or_later(spec_version):
            check_step_output_schema(normalized, sections, args.stage, errors, warnings)
            check_execution_mode(normalized, args.stage, errors, warnings)
        if args.git_check:
            check_file_boundaries(sections, root, args.base, args.stage, errors, warnings)
        scan_secret_text(strip_acceptance_item(strip_clause_body(normalized, 13), 13), str(spec_real), errors)
        # C8[A4-C]：paused 状态跳过签约块校验（已作废，不再要求签约字段完整），仅校验 pause 记录
        _is_paused = fm_info["fm"].get("status", "").strip() == "paused"
        if args.stage in ("spec", "verify", "accept") and not _is_paused:
            check_sign_block(fm_info["fm"], body_hash, [item[0] for item in clauses], errors, warnings)
        if args.stage in ("verify", "accept"):
            if 9 in sections:
                check_reconciliation(sections[9][1], clauses, root, errors, warnings)
                check_thaw(sections, clauses, fm_info["fm"], root, errors, warnings)
        if args.stage == "accept":
            check_accept_block(fm_info["fm"], acceptance, errors, warnings, current_scope)
        if args.git_check:
            check_git(spec_real, root, args.base, args.stage, fm_info["fm"], body_hash, errors, warnings, args.head)

    result["ok"] = not errors
    return emit(result, args.json)


if __name__ == "__main__":
    sys.exit(main())
