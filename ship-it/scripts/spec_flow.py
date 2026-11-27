#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec_flow.py — spec 契约流转编排器（v5.2.1 / C3）：sign/accept/reconcile 一条命令。

把"算 hash + 写 front matter + 跑 check_spec 自校验 + FAIL 回滚"固化为原子操作，
消除手填 sign_hash/accept_commit/accepted_items 的易错环节。

用法：
    python ship-it/scripts/spec_flow.py sign <spec>
    python ship-it/scripts/spec_flow.py accept <spec>
    python ship-it/scripts/spec_flow.py reconcile <spec>

设计：
    - sign：import spec_hash 算 hash → 写 sign 系列字段 → 跑 check_spec --stage spec → FAIL 回滚
    - accept：写 accept 系列字段（accept_commit 取 git rev-parse HEAD）→ 跑 check_spec --stage accept → FAIL 回滚
      accept 时若 hash_scope=sections_1_8，改为 sections_1_8_a_normalized（front matter 不参与 sign_hash）
    - reconcile：校验核销表用例名在测试文件中存在、报告路径真实（只读校验，回填由主脑编辑）
    - 字段定义单点对齐 check_spec.py 的 COMMON_FM_KEYS/ACCEPT_FM_KEYS，不维护第二份
    - sign 只写 front matter，不改 §5（防脚本帮改契约的越权）
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import spec_hash  # noqa: E402

# 字段定义单点对齐 check_spec.py（import 而非复制，避免第二份漂移）
sys.path.insert(0, str(SCRIPT_DIR))
from check_spec import (  # noqa: E402
    COMMON_FM_KEYS,
    ACCEPT_FM_KEYS,
    SIGN_PROMPT_KEYWORDS,
    ACCEPT_PROMPT_KEYWORDS,
)

SIGN_PROMPT_TEXT = (
    "刚才的说明造成误解：是否要签约？如果需要签约，请发送\"签约\"两个字才可以；"
    "不发送\"签约\"两个字，我不会开始编码。只发送这两个字，不要加标点、引号或其他内容。"
)
ACCEPT_PROMPT_TEXT = (
    "刚才的说明可能造成误解：是否需要验收？如果需要验收，请发送\"验收\"两个字才可以；"
    "不发送\"验收\"两个字，我不会进入 PR。只发送这两个字，不要加标点、引号或其他内容。"
)


def run_git(args, cwd=None):
    proc = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def git_head(cwd):
    code, out, err = run_git(["rev-parse", "HEAD"], cwd=cwd)
    if code != 0:
        raise RuntimeError("git rev-parse HEAD 失败：%s" % err)
    return out


def now_iso():
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def split_front_matter(text):
    """返回 (fm_lines, body_lines, has_fm)。保留原换行结构以便回写。"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        return [], lines, False
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index], lines[index + 1:], True
    return [], lines, False


def join_front_matter(fm_lines, body_lines):
    return "---\n" + "\n".join(fm_lines) + "\n---\n" + "\n".join(body_lines)


def parse_fm_dict(fm_lines):
    """简易解析为 dict（值去引号）。"""
    result = {}
    for line in fm_lines:
        line = line.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        match = re.match(r"^([^:]+):\s*(.*)$", line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
                value = value[1:-1]
            result[key] = value
    return result


def set_fm_field(fm_lines, key, value):
    """就地设置 front matter 字段（已存在则更新，不存在则在末尾追加）。"""
    pattern = re.compile(r"^(\s*" + re.escape(key) + r"\s*:\s*)(.*)$")
    for index, line in enumerate(fm_lines):
        if pattern.match(line):
            fm_lines[index] = "%s%s\"%s\"" % (pattern.match(line).group(1), "", value) \
                if False else "%s: \"%s\"" % (key, value)
            return
    fm_lines.append("%s: \"%s\"" % (key, value))


def backup_and_write(spec_path, text):
    """写前备份，返回备份路径。"""
    backup = spec_path.with_suffix(spec_path.suffix + ".spec_flow.bak")
    shutil.copy2(spec_path, backup)
    spec_path.write_text(text, encoding="utf-8")
    return backup


def restore(spec_path, backup):
    shutil.copy2(backup, spec_path)
    backup.unlink()


def run_check_spec(spec_path, stage, root, extra_args=None):
    """跑 check_spec.py 指定阶段，返回 (exit_code, stdout)。extra_args 附加命令行参数。"""
    cmd = [sys.executable, str(SCRIPT_DIR / "check_spec.py"), str(spec_path), "--stage", stage]
    if extra_args:
        cmd.extend(extra_args)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=root)
    return proc.returncode, proc.stdout + proc.stderr


def run_cmd(cmd, cwd=None):
    """跑任意命令，返回 (exit_code, stdout)。"""
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=cwd)
    return proc.returncode, proc.stdout + proc.stderr


def extract_clauses(body_lines):
    """从正文提取 C 条款编号列表。"""
    numbers = []
    for line in body_lines:
        match = re.match(r"^###\s+C(\d+)\b", line)
        if match:
            numbers.append(int(match.group(1)))
    return numbers


def extract_acceptance(body_lines):
    """从正文提取 A 验收项编号列表。"""
    numbers = []
    for line in body_lines:
        match = re.match(r"^\s*[-*+]\s*\[[ xX]\]\s*\*{0,2}A(\d+)\b", line)
        if match:
            numbers.append(int(match.group(1)))
    return numbers


def cmd_sign(args):
    spec_path = Path(args.spec).resolve()
    root = Path(args.root).resolve()
    if not spec_path.is_file():
        print("ERROR: spec 不存在：%s" % spec_path, file=sys.stderr)
        return 1
    text = spec_path.read_text(encoding="utf-8")
    fm_lines, body_lines, has_fm = split_front_matter(text)
    if not has_fm:
        print("ERROR: spec 无 front matter", file=sys.stderr)
        return 1
    fm = parse_fm_dict(fm_lines)
    status = fm.get("status", "").strip()
    if status == "signed":
        print("WARN: spec 已签约（status=signed），sign 将覆盖原签约块", file=sys.stderr)

    # C3[B1]：sign 前置三闸门——draft + check_docs + print-sign-hash dry-run，任一非 0 不得签约
    gate1_code, gate1_out = run_check_spec(spec_path, "draft", root)
    if gate1_code != 0:
        print("FAIL: 闸门① check_spec --stage draft 退出码 %d，不得签约" % gate1_code, file=sys.stderr)
        print(gate1_out, file=sys.stderr)
        return 1
    gate2_code, gate2_out = run_cmd([sys.executable, str(root / "ship-it" / "scripts" / "check_docs.py"), "--root", str(root), "--spec", str(spec_path)], root)
    if gate2_code != 0:
        print("FAIL: 闸门② check_docs 退出码 %d，不得签约" % gate2_code, file=sys.stderr)
        print(gate2_out, file=sys.stderr)
        return 1
    gate3_code, gate3_out = run_check_spec(spec_path, "spec", root, extra_args=["--print-sign-hash"])
    if gate3_code != 0:
        print("FAIL: 闸门③ check_spec --stage spec --print-sign-hash 退出码 %d，不得签约" % gate3_code, file=sys.stderr)
        print(gate3_out, file=sys.stderr)
        return 1

    # 算 hash
    body_hash = spec_hash.sign_hash(text, str(spec_path))
    if not body_hash:
        print("ERROR: 无法计算 sign_hash（spec_hash 返回 None，可能 hash_scope 缺失）", file=sys.stderr)
        return 1

    clauses = extract_clauses(body_lines)
    confirmed = ",".join("C%d" % n for n in sorted(clauses))
    ts = now_iso()

    # 写 sign 系列字段
    set_fm_field(fm_lines, "status", "signed")
    set_fm_field(fm_lines, "sign_requested_at", ts)
    set_fm_field(fm_lines, "signed_by", "用户（lead 会话）")
    set_fm_field(fm_lines, "signed_at", ts)
    set_fm_field(fm_lines, "sign_quote", "签约")
    set_fm_field(fm_lines, "sign_hash", body_hash)
    set_fm_field(fm_lines, "confirmed_clauses", confirmed)
    if not fm.get("decisions"):
        set_fm_field(fm_lines, "decisions", "")

    new_text = join_front_matter(fm_lines, body_lines)
    backup = backup_and_write(spec_path, new_text)

    # 自校验
    code, out = run_check_spec(spec_path, "spec", root)
    if code != 0:
        restore(spec_path, backup)
        print("FAIL: check_spec --stage spec 退出码 %d，已回滚 front matter" % code, file=sys.stderr)
        print(out, file=sys.stderr)
        return 1
    print("OK: sign 完成，sign_hash=%s，confirmed_clauses=%s" % (body_hash, confirmed))
    print("check_spec --stage spec PASS")
    return 0


def cmd_accept(args):
    spec_path = Path(args.spec).resolve()
    root = Path(args.root).resolve()
    if not spec_path.is_file():
        print("ERROR: spec 不存在：%s" % spec_path, file=sys.stderr)
        return 1
    text = spec_path.read_text(encoding="utf-8")
    fm_lines, body_lines, has_fm = split_front_matter(text)
    if not has_fm:
        print("ERROR: spec 无 front matter", file=sys.stderr)
        return 1
    fm = parse_fm_dict(fm_lines)
    status = fm.get("status", "").strip()
    if status != "signed":
        print("ERROR: spec 未签约（status=%s），accept 前必须先 sign" % status, file=sys.stderr)
        return 1

    # accept_commit 取 HEAD
    try:
        head = git_head(root)
    except RuntimeError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    acceptance = extract_acceptance(body_lines)
    accepted = ",".join("A%d" % n for n in sorted(acceptance))
    ts = now_iso()

    # accept 时若 hash_scope=sections_1_8，改为 sections_1_8_a_normalized
    scope = fm.get("hash_scope", "").strip().lower()
    if scope == "sections_1_8":
        set_fm_field(fm_lines, "hash_scope", "sections_1_8_a_normalized")

    # 写 accept 系列字段
    set_fm_field(fm_lines, "status", "accepted")
    set_fm_field(fm_lines, "accept_requested_at", ts)
    set_fm_field(fm_lines, "accepted_by", "用户（lead 会话）")
    set_fm_field(fm_lines, "accepted_at", ts)
    set_fm_field(fm_lines, "accept_quote", "验收")
    set_fm_field(fm_lines, "accept_commit", head)
    set_fm_field(fm_lines, "accepted_items", accepted)

    new_text = join_front_matter(fm_lines, body_lines)
    backup = backup_and_write(spec_path, new_text)

    # 自校验
    code, out = run_check_spec(spec_path, "accept", root)
    if code != 0:
        restore(spec_path, backup)
        print("FAIL: check_spec --stage accept 退出码 %d，已回滚 front matter" % code, file=sys.stderr)
        print(out, file=sys.stderr)
        return 1
    print("OK: accept 完成，accept_commit=%s，accepted_items=%s" % (head, accepted))
    print("check_spec --stage accept PASS")
    return 0


def cmd_reconcile(args):
    """校验核销表用例名在测试文件中存在、报告路径真实（只读校验）。"""
    spec_path = Path(args.spec).resolve()
    root = Path(args.root).resolve()
    if not spec_path.is_file():
        print("ERROR: spec 不存在：%s" % spec_path, file=sys.stderr)
        return 1
    text = spec_path.read_text(encoding="utf-8")
    fm_lines, body_lines, has_fm = split_front_matter(text)
    if not has_fm:
        print("ERROR: spec 无 front matter", file=sys.stderr)
        return 1

    # 找 §9 核销表
    section9 = None
    for index, line in enumerate(body_lines):
        if re.match(r"^##\s*9[.\u3001\s]", line):
            section9 = body_lines[index:]
            break
    if section9 is None:
        print("ERROR: spec 无 §9 核销记录", file=sys.stderr)
        return 1

    # 解析核销表行
    errors = []
    rows = []
    header_seen = False
    for line in section9:
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if "|" in line else []
        if not cells:
            continue
        if cells[0] == "条款":
            header_seen = True
            continue
        if not header_seen:
            continue
        match = re.match(r"^C(\d+)$", cells[0]) if cells else None
        if match and len(cells) >= 4:
            # 去 markdown 反引号包裹
            cleaned = [c.strip().strip("`") for c in cells]
            rows.append((int(match.group(1)), cleaned))

    # 找测试报告路径
    report_path = None
    for line in section9:
        match = re.match(r"^\s*[-*]\s*测试报告\s*[\uff1a:]\s*(.+?)\s*$", line)
        if match:
            report_path = match.group(1).strip().strip("`")
            break

    # 校验用例名在用例文件中存在
    for number, cells in rows:
        case_name = cells[1] if len(cells) > 1 else ""
        case_file = cells[2] if len(cells) > 2 else ""
        if case_name and case_file:
            case_file_path = root / case_file
            if not case_file_path.is_file():
                errors.append("C%d 用例文件不存在：%s" % (number, case_file))
                continue
            content = case_file_path.read_text(encoding="utf-8", errors="replace")
            # C3[B5]：精确匹配 def <name>( ，允许前导空白（类方法缩进），不允许子串模糊匹配（防假绿）
            def_pattern = r"^\s*def\s+%s\s*\(" % re.escape(case_name)
            if not re.search(def_pattern, content, re.MULTILINE):
                errors.append("C%d 用例名 '%s' 在 %s 中未以 `def %s(` 精确匹配（C3[B5]）" % (number, case_name, case_file, case_name))

    # 校验报告路径真实
    if report_path:
        report_real = root / report_path
        if not report_real.is_file():
            errors.append("测试报告不存在：%s" % report_path)
    else:
        errors.append("§9 缺少 - 测试报告：<path>")

    if errors:
        for e in errors:
            print("ERROR: %s" % e, file=sys.stderr)
        return 1
    print("OK: reconcile 校验通过，%d 条核销行，用例名均在测试文件中存在，报告路径真实" % len(rows))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="spec 契约流转编排器（v5.2.1 / C3）")
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("sign", "accept", "reconcile"):
        p = sub.add_parser(cmd, help="%s spec" % cmd)
        p.add_argument("spec", help="spec 文件路径")
        p.add_argument("--root", default=".", help="仓库根（默认当前目录）")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "sign":
        return cmd_sign(args)
    if args.command == "accept":
        return cmd_accept(args)
    if args.command == "reconcile":
        return cmd_reconcile(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
