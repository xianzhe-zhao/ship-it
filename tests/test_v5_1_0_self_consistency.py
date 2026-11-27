#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_v5_1_0_self_consistency.py — v5.1.0 自身一致性修复 验收测试（Step 4，测试员）。

契约：docs/specs/2026-11-24-v5.1.0-skill-self-consistency.md（C1–C10，已签约）。
测试从契约（spec §5 C1–C10）派生，不从代码派生：
  - C1 SKILL.md frontmatter version=5.1.0；正文无"当前 v4.7.1"
  - C2 SKILL.md 文件地图 references 8 个 / scripts 10 个，与 ls 一致
  - C3 SKILL.md 正文提及 role-glossary / check_terms / watchdog_daemon
  - C4 不传 --spec 时 check_docs 选文件名版本号最高（v5.1.0）
  - C5 无版本号时空目录降级日期+mtime+warning（不崩溃）
  - C6 check_text.py docstring 与 argparse 版本一致（5.1.0）
  - C7 SKILL.md 行数 ≤350
  - C8 附录关键词清单全部可在 SKILL.md grep 到（关键词清单运行时从 spec 附录解析）
  - C9 check_text / check_docs(+--spec) 退出码 0
  - C10 两份 CHANGELOG 顶部有 5.1.0 条目

组织：pytest；check_docs/check_text 用 subprocess 跑；其余用文件读取做断言。
只读：不写业务数据；C5 降级用例仅在 tmp/ 下建临时 fixture 并于用例结束时清理。
SKIP：本用例集无条件跳过（SKIP 数=0），避免"退出码 0 + SKIP = 假绿"。

C8 匹配方法（透明、统一、契约意图派生）：spec 附录关键词以紧凑形式书写，SKILL.md 正文
有自然空格；为避免"空格差异"被误判为"规则丢失"，对关键词与 SKILL.md 各自去掉空格/制表符/
全角空格（保留换行以防跨行伪匹配）后做子串包含判定。该方法对所有关键词统一适用，非逐条调参。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIP_DIR = REPO_ROOT / "ship-it"
SKILL_MD = SHIP_DIR / "SKILL.md"
CHECK_DOCS = SHIP_DIR / "scripts" / "check_docs.py"
CHECK_TEXT = SHIP_DIR / "scripts" / "check_text.py"
SPEC_PATH = SHIP_DIR / "docs" / "specs" / "2026-11-24-v5.1.0-skill-self-consistency.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_skill_version() -> str:
    """动态读 ship-it/SKILL.md frontmatter version（单一事实源，与 reliability C2 一致）。"""
    text = _read(SKILL_MD)
    m = re.search(r"^version:\s*(\d+\.\d+\.\d+)\s*$", text, re.MULTILINE)
    assert m is not None, "SKILL.md frontmatter 缺 version 字段"
    return m.group(1)


EXPECTED_VERSION = _read_skill_version()


def _run(script: Path, args, *, cwd=REPO_ROOT, json_out=False):
    """跑脚本，返回 (exit_code, stdout, stderr)。stdout 强制 utf-8 解码。"""
    cmd = [sys.executable, str(script)] + list(args)
    proc = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def _norm_keep_nl(s: str) -> str:
    """去空格/制表符/全角空格，保留换行（防跨行伪匹配）。"""
    return (s.replace("\r\n", "\n").replace("\r", "\n")
            .replace(" ", "").replace("\t", "").replace("\u3000", ""))


def _file_map_section(text: str) -> str:
    """截取 SKILL.md「## 文件地图」节到下一个二级标题之间正文。"""
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "## 文件地图":
            start = i + 1
            break
    assert start is not None, "SKILL.md 缺少「## 文件地图」节"
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].lstrip().startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end])


def _parse_c8_keywords(spec_text: str):
    """从 spec 附录解析 C8 规则关键词清单（" / " 分隔，紧邻斜杠不拆）。"""
    keywords = []
    for ln in spec_text.splitlines():
        if "关键词：" not in ln:
            continue
        header, _, body = ln.partition("：")
        if "关键词" not in header:
            continue
        for kw in body.split(" / "):
            kw = kw.strip()
            if kw:
                keywords.append(kw)
    return keywords


# ---------------------------------------------------------------------------
# C1
# ---------------------------------------------------------------------------

def test_c1_version_consistency():
    """C1：SKILL.md frontmatter version == EXPECTED_VERSION（动态读）；正文无"当前 v4.7.1"，无非当前的"当前 vX"。"""
    text = _read(SKILL_MD)
    fm = re.search(r"^version:\s*(\d+\.\d+\.\d+)\s*$", text, re.MULTILINE)
    assert fm is not None, "SKILL.md frontmatter 缺 version 字段"
    assert fm.group(1) == EXPECTED_VERSION, f"frontmatter version={fm.group(1)}，期望 {EXPECTED_VERSION}"
    # 失败行为：grep "当前 v4.7.1" 有匹配 = FAIL
    assert re.search(r"当前\s*v4\.7\.1", text) is None, "SKILL.md 仍含『当前 v4.7.1』"
    # 后置条件：无非当前的"当前 vX"表述（EXPECTED_VERSION 动态读，版本升级后自动跟进）
    cur_versions = re.findall(r"当前\s*v(\d+\.\d+\.\d+)", text)
    bad = [v for v in cur_versions if v != EXPECTED_VERSION]
    assert not bad, f"SKILL.md 含非 {EXPECTED_VERSION} 的『当前 vX』：{bad}"


# ---------------------------------------------------------------------------
# C2
# ---------------------------------------------------------------------------

def test_c2_file_map_matches_ls():
    """C2：SKILL.md 文件地图 references / scripts 与 ls 一一对应（契约不变式，计数随仓库演进）。

    scripts/ 下的 ``test_*.py`` 是核销用例载体（如 test_v5_2_0_features.py），
    非 skill 功能性脚本工具，仓库惯例不进文件地图（v5.2.0 起既定），
    故 actual_scripts 排除 ``test_*.py`` 后再与文件地图比对。
    """
    text = _read(SKILL_MD)
    section = _file_map_section(text)
    map_refs = set(re.findall(r"references/([\w-]+\.md)", section))
    map_scripts = set(re.findall(r"scripts/([\w-]+\.py)", section))
    actual_refs = {p.name for p in (SHIP_DIR / "references").glob("*.md")}
    actual_scripts = {p.name for p in (SHIP_DIR / "scripts").glob("*.py")
                      if not p.name.startswith("test_")}
    assert actual_refs, "references 目录为空，C2 无法验证"
    assert actual_scripts, "scripts 目录为空，C2 无法验证"
    assert map_refs == actual_refs, (
        f"文件地图 references 与 ls 不一致：仅地图={sorted(map_refs - actual_refs)}，"
        f"仅 ls={sorted(actual_refs - map_refs)}")
    assert map_scripts == actual_scripts, (
        f"文件地图 scripts 与 ls 不一致：仅地图={sorted(map_scripts - actual_scripts)}，"
        f"仅 ls={sorted(actual_scripts - map_scripts)}")


# ---------------------------------------------------------------------------
# C3
# ---------------------------------------------------------------------------

def test_c3_new_artifacts_referenced():
    """C3：SKILL.md 正文（含文件地图）提及 role-glossary / check_terms / watchdog_daemon。"""
    text = _read(SKILL_MD)
    missing = [kw for kw in ("role-glossary", "check_terms", "watchdog_daemon") if kw not in text]
    assert not missing, f"SKILL.md 未提及 v5.0.0 新产物：{missing}"


# ---------------------------------------------------------------------------
# C4
# ---------------------------------------------------------------------------

def test_c4_checkdocs_picks_highest_version():
    """C4：不传 --spec 时 check_docs 选文件名版本号最高者（SemVer），路径在 ship-it/docs/specs/ 下。"""
    rc, out, err = _run(CHECK_DOCS, ["--root", ".", "--json"])
    assert "Traceback" not in err, f"check_docs 崩溃：{err}"
    data = json.loads(out)
    spec = data.get("spec", "")
    assert spec.startswith("ship-it/docs/specs/"), f"选取的 spec 路径异常：{spec}"
    # 解析选中 spec 文件名版本号，应为仓库内文件名版本号最高者（契约：SemVer 最高）
    m = re.search(r"v(\d+\.\d+\.\d+)", spec)
    assert m is not None, f"选取的 spec 文件名无版本号：{spec}"
    picked = tuple(int(x) for x in m.group(1).split("."))
    specs_dir = SHIP_DIR / "docs" / "specs"
    all_versions = []
    for item in specs_dir.glob("*.md"):
        vm = re.search(r"v(\d+\.\d+\.\d+)", item.name)
        if vm:
            all_versions.append(tuple(int(x) for x in vm.group(1).split(".")))
    assert all_versions, "ship-it/docs/specs 下无带版本号的 spec，C4 无法验证"
    highest = max(all_versions)
    assert picked == highest, f"默认选取的 spec 非文件名版本号最高：选中 v{'.'.join(map(str,picked))}，仓库最高 v{'.'.join(map(str,highest))}"


# ---------------------------------------------------------------------------
# C5
# ---------------------------------------------------------------------------

def test_c5_checkdocs_degrades_no_version():
    """C5：无版本号或空 specs 时降级日期+mtime+warning，不崩溃。

    reliability C1/C2 后 check_docs 只扫 ``ship-it/docs/specs/`` 且要求
    ``ship-it/SKILL.md`` 存在（fail closed）。故临时 fixture 放在
    ``ship-it/docs/specs/`` 下并附带最小 SKILL.md，降级语义不变。
    """
    tmp_root = REPO_ROOT / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    fixtures = []
    minimal_skill = "---\nname: ship-it\nversion: 5.2.1\n---\n# ship-it\n"
    try:
        # 子情形 A：所有 spec 文件名无版本号 → 降级取文件名日期最新 + warning
        base_a = Path(tempfile.mkdtemp(prefix="c5_nover_", dir=str(tmp_root)))
        fixtures.append(base_a)
        (base_a / "ship-it" / "docs" / "specs").mkdir(parents=True, exist_ok=True)
        (base_a / "ship-it" / "SKILL.md").write_text(minimal_skill, encoding="utf-8")
        (base_a / "ship-it" / "docs" / "specs" / "2026-01-01-alpha.md").write_text("# alpha\n", encoding="utf-8")
        (base_a / "ship-it" / "docs" / "specs" / "2026-02-01-beta.md").write_text("# beta\n", encoding="utf-8")
        rc, out, err = _run(CHECK_DOCS, ["--root", str(base_a), "--json"])
        assert "Traceback" not in err, f"[A 无版本号] check_docs 崩溃：{err}"
        data_a = json.loads(out)
        assert data_a.get("spec", "") == "ship-it/docs/specs/2026-02-01-beta.md", (
            f"[A 无版本号] 降级应选日期最新 beta，实际：{data_a.get('spec')}")
        warns_a = data_a.get("warnings", [])
        assert any(("降级" in w or "无文件名版本号" in w) for w in warns_a), (
            f"[A 无版本号] 缺降级 warning：{warns_a}")

        # 子情形 B：ship-it/docs/specs 为空 → warning"无 spec"，不崩溃
        base_b = Path(tempfile.mkdtemp(prefix="c5_empty_", dir=str(tmp_root)))
        fixtures.append(base_b)
        (base_b / "ship-it" / "docs" / "specs").mkdir(parents=True, exist_ok=True)
        (base_b / "ship-it" / "SKILL.md").write_text(minimal_skill, encoding="utf-8")
        rc2, out2, err2 = _run(CHECK_DOCS, ["--root", str(base_b), "--json"])
        assert "Traceback" not in err2, f"[B 空 specs] check_docs 崩溃：{err2}"
        data_b = json.loads(out2)
        assert data_b.get("spec", "") == "", f"[B 空 specs] spec 应为空，实际：{data_b.get('spec')}"
        warns_b = data_b.get("warnings", [])
        assert any("没有日期命名的 spec" in w for w in warns_b), (
            f"[B 空 specs] 缺『没有日期命名的 spec』warning：{warns_b}")
    finally:
        for fx in fixtures:
            shutil.rmtree(fx, ignore_errors=True)


# ---------------------------------------------------------------------------
# C6
# ---------------------------------------------------------------------------

def test_c6_checktext_version_unified():
    """C6：check_text.py docstring 与 argparse 版本标识一致（契约失败行为：两处不一致 = FAIL）。"""
    text = _read(CHECK_TEXT)
    doc = re.search(r"check_text\.py\s*[—-]\s*v(\d+\.\d+\.\d+)", text)
    arg = re.search(r'description="v(\d+\.\d+\.\d+)', text)
    assert doc is not None, "check_text.py docstring 未找到版本标识"
    assert arg is not None, "check_text.py argparse description 未找到版本标识"
    assert doc.group(1) == arg.group(1), (
        f"docstring 版本={doc.group(1)} 与 argparse 版本={arg.group(1)} 不一致")


# ---------------------------------------------------------------------------
# C7
# ---------------------------------------------------------------------------

def test_c7_skill_md_under_350():
    """C7：SKILL.md 行数 ≤350（python splitlines）。"""
    text = _read(SKILL_MD)
    n = len(text.splitlines())
    assert n <= 350, f"SKILL.md 行数 {n} > 350"


# ---------------------------------------------------------------------------
# C8
# ---------------------------------------------------------------------------

def test_c8_no_rule_lost():
    """C8：spec 附录关键词清单全部可在 SKILL.md grep 到（无规则丢失）。"""
    spec_text = _read(SPEC_PATH)
    skill_text = _read(SKILL_MD)
    keywords = _parse_c8_keywords(spec_text)
    assert len(keywords) >= 10, f"从 spec 附录解析的关键词过少（{len(keywords)}），解析可能有误"
    skill_norm = _norm_keep_nl(skill_text)
    missing = [kw for kw in keywords if _norm_keep_nl(kw) not in skill_norm]
    # 透明记录：纯字面子串（不去空格）有多少因空格差异未命中，仅供审计
    strict_miss = [kw for kw in keywords if kw not in skill_text]
    assert not missing, (
        f"C8 规则关键词在 SKILL.md 缺失（去空格判定）：{missing}；"
        f"（纯字面差异数={len(strict_miss)}，属空格差异非规则丢失）")


# ---------------------------------------------------------------------------
# C9
# ---------------------------------------------------------------------------

def test_c9_machine_checks_pass():
    """C9：check_text --root . / check_docs --root . / check_docs --root . --spec <v5.1.0 spec> 退出码 0。"""
    rc_text, out_text, err_text = _run(CHECK_TEXT, ["--root", "."])
    assert rc_text == 0, f"check_text --root . 退出码 {rc_text}\nSTDOUT:{out_text}\nSTDERR:{err_text}"
    rc_docs, out_docs, err_docs = _run(CHECK_DOCS, ["--root", "."])
    assert rc_docs == 0, f"check_docs --root . 退出码 {rc_docs}\nSTDOUT:{out_docs}\nSTDERR:{err_docs}"
    rc_spec, out_spec, err_spec = _run(
        CHECK_DOCS, ["--root", ".", "--spec", "ship-it/docs/specs/2026-11-24-v5.1.0-skill-self-consistency.md"])
    assert rc_spec == 0, (
        f"check_docs --root . --spec <v5.1.0 spec> 退出码 {rc_spec}\n"
        f"STDOUT:{out_spec}\nSTDERR:{err_spec}")


# ---------------------------------------------------------------------------
# C10
# ---------------------------------------------------------------------------

def test_c10_changelog_has_v5_1_0():
    """C10：ship-it/CHANGELOG.md 与根 CHANGELOG.md 顶部版本 == SKILL.md frontmatter version（动态读）。"""
    ship_cl = _read(SHIP_DIR / "CHANGELOG.md")
    root_cl = _read(REPO_ROOT / "CHANGELOG.md")
    ship_top = re.search(r"^##\s+v?(\d+\.\d+\.\d+)\b", ship_cl, re.MULTILINE)
    root_top = re.search(r"^\|\s*v?(\d+\.\d+\.\d+)\s*\|", root_cl, re.MULTILINE)
    assert ship_top is not None, "ship-it/CHANGELOG.md 未找到版本节标题"
    assert root_top is not None, "根 CHANGELOG.md 未找到版本索引行"
    assert ship_top.group(1) == EXPECTED_VERSION, (
        f"ship-it/CHANGELOG.md 顶部版本={ship_top.group(1)}，期望 {EXPECTED_VERSION}")
    assert root_top.group(1) == EXPECTED_VERSION, (
        f"根 CHANGELOG.md 顶部版本={root_top.group(1)}，期望 {EXPECTED_VERSION}")
