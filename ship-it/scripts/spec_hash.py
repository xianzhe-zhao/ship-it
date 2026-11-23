#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec_hash.py — spec 正文 hash_scope（v4.7.1 C8）：一份定义，check_spec/check_roles 共用。

scope：
    full_body                  front matter 之后全文（含 §9）
    sections_1_8               ## 1. 到 ## 9. 前一行，A 复选框保持原样
    sections_1_8_a_normalized  同上，但 - [x] A<n> 归一化为 - [ ] A<n>

历史兼容（front matter 未写 hash_scope 时）：
    - 文件名日期 < 2026-11-19：legacy，返回 None（check_spec 跳过 --git-check）
    - docs/specs/2026-11-19-contract-gates-and-concision.md 的 spec_revision <= 3：full_body
    - 其他 2026-11-19 spec：sections_1_8_a_normalized
    - 2026-11-20 及以后：sections_1_8（v4.7.1 rev1 口径）
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

HASH_SCOPES = ("full_body", "sections_1_8", "sections_1_8_a_normalized")
SECTION1_RE = re.compile(r"^##\s*1[.\u3001\s]")
SECTION9_RE = re.compile(r"^##\s*9[.\u3001\s]")
ACCEPTANCE_CHECK_RE = re.compile(r"^(\s*[-*+]\s+\[)[xX](\]\s+\*{0,2}A\d+\b)")
DATE_PREFIX_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_front_matter(text: str):
    """返回 (front_matter_text, body_text, has_front_matter)。"""
    normalized = normalize_newlines(text)
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        return "", normalized, False
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1:]), True
    return "", normalized, False


def front_value(fm: str, key: str) -> str:
    match = re.search(r"(?m)^\s*" + re.escape(key) + r"\s*:\s*(.*)$", fm)
    if not match:
        return ""
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
        value = value[1:-1]
    return value.strip()


def spec_date_from_name(filename: str):
    match = DATE_PREFIX_RE.match(Path(filename).name)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def full_body(text: str) -> str:
    _fm, body, has_fm = split_front_matter(text)
    return body if has_fm else normalize_newlines(text)


def sections_1_8(text: str, normalize_a: bool = False) -> str:
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
    body = "\n".join(lines[start:end])
    if normalize_a:
        body = "\n".join(ACCEPTANCE_CHECK_RE.sub(r"\1 \2", line) for line in body.split("\n"))
    return body


def hash_for_scope(text: str, scope: str) -> str:
    if scope == "full_body":
        return sha256_hex(full_body(text))
    if scope == "sections_1_8":
        return sha256_hex(sections_1_8(text, normalize_a=False))
    if scope == "sections_1_8_a_normalized":
        return sha256_hex(sections_1_8(text, normalize_a=True))
    raise ValueError("unknown hash_scope: " + str(scope))


def infer_scope(text: str, filename: str):
    spec_date = spec_date_from_name(filename)
    if spec_date is None or spec_date < date(2026, 11, 19):
        return None
    fm, _body, _has_fm = split_front_matter(text)
    revision_text = front_value(fm, "spec_revision")
    revision = int(revision_text) if revision_text.isdigit() else 1
    if spec_date == date(2026, 11, 19):
        # 只有真实的 v4.7.0 历史 spec 的 rev1–3 用 full_body；测试/新 fixture 必须显式写 hash_scope。
        if Path(filename).name == "2026-11-19-contract-gates-and-concision.md" and revision <= 3:
            return "full_body"
        return "sections_1_8_a_normalized"
    return "sections_1_8" if revision <= 3 else "sections_1_8_a_normalized"


def scope_for_text(text: str, filename: str):
    fm, _body, _has_fm = split_front_matter(text)
    scope = front_value(fm, "hash_scope").lower()
    if scope in HASH_SCOPES:
        return scope
    return infer_scope(text, filename)


def sign_hash(text: str, filename: str):
    scope = scope_for_text(text, filename)
    if scope is None:
        return None
    return hash_for_scope(text, scope)
