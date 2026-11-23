#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.7.1 文本质量契约测试（C1–C5 / A1–A4）。

契约：docs/specs/2026-11-20-skill-concision.md
覆盖：git-push-firewall 传输边界、ship-it 远端写边界、check_text 的行数/禁词/互引/
      复盘 150 行、PR/合并授权语、重复标题、矛盾计数、必含短语。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support.harness import ROOT, invoke_script

CHECK_TEXT = ROOT / "ship-it" / "scripts" / "check_text.py"
CHECK_DOCS = ROOT / "ship-it" / "scripts" / "check_docs.py"
CHECK_SPEC = ROOT / "ship-it" / "scripts" / "check_spec.py"
SKILL = ROOT / "ship-it" / "SKILL.md"
RETRO = ROOT / "docs" / "reviews" / "2026-11-19-retrospective.md"
REAL_SPEC = ROOT / "docs" / "specs" / "2026-11-20-skill-concision.md"
REAL_SPEC_472 = ROOT / "docs" / "specs" / "2026-11-21-v4.7.2-fixes.md"
GPF = Path.home() / ".dsh" / "skills" / "git-push-firewall" / "SKILL.md"
GPF_SCRIPT = Path.home() / ".dsh" / "skills" / "git-push-firewall" / "push-via-api.js"

BANNED = ["尽量", "适当", "必要时", "原则上", "一般来说", "视情况", "酌情", "看情况", "最好"]
SHIP_REQUIRED = ["上传工具", "PR 仅在验收后", "合并仅用户"]

SHIP_BASE = (
    "---\n"
    "name: ship-it\n"
    "version: 4.7.1\n"
    "---\n"
    "\n"
    "# ship-it\n"
    "\n"
    "## Step 7 提交 PR\n"
    "\n"
    "- 远端写前读上传工具的实际参数，确认目标分支。\n"
    "- PR 仅在验收后创建。\n"
    "- 合并仅用户。\n"
)

GPF_BASE = (
    "# git-push-firewall\n"
    "\n"
    "只提供上传方法；可传任意分支（含 main）；具体合到哪个分支、是否 PR、是否合并，不由此 skill 决定；按原计划执行。\n"
    "\n"
    "## Method\n"
    "\n"
    "- 显式 `--branch <branch>` 或 `GH_BRANCH=<branch>`；缺失即失败。\n"
)

RETRO_BASE = "# 2026-11-19 复盘\n\n- 一句能说清不写两句。\n"


def pad_lines(text: str, count: int) -> str:
    lines = text.rstrip("\n").split("\n")
    index = 1
    while len(lines) < count:
        lines.append("- 规则行 %d：必须执行，禁止空转。" % index)
        index += 1
    return "\n".join(lines[:count]) + "\n"


def write_fixture(directory: str, *, ship: str = SHIP_BASE, gpf: str = GPF_BASE,
                  retro: str = RETRO_BASE):
    root = Path(directory) / "repo"
    gpf_path = root / "gpf" / "SKILL.md"
    retro_path = root / "docs" / "reviews" / "2026-11-19-retrospective.md"
    for path, text in ((root / "ship-it" / "SKILL.md", ship),
                       (gpf_path, gpf), (retro_path, retro)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root, gpf_path, retro_path


def run_check(root: Path, gpf: Path, retro: Path):
    root_real = Path(root).resolve()
    args = ["--root", str(root)]
    if Path(gpf).resolve().is_relative_to(root_real):
        args += ["--git-push", str(gpf)]
    args += ["--retro", str(retro)]
    return invoke_script(CHECK_TEXT, args, ROOT)


def check_fixture(**overrides):
    with tempfile.TemporaryDirectory(prefix="shipit-text-") as directory:
        root, gpf, retro = write_fixture(directory, **overrides)
        return run_check(root, gpf, retro)


class TextQualityTest(unittest.TestCase):
    maxDiff = None

    def assert_pass(self, result, label: str) -> None:
        self.assertEqual(
            result.returncode, 0,
            label + "：期望退出码 0，实际 " + str(result.returncode)
            + "\nSTDOUT:\n" + (result.stdout or "") + "\nSTDERR:\n" + (result.stderr or ""),
        )

    def assert_fail(self, result, label: str) -> None:
        self.assertNotEqual(
            result.returncode, 0,
            label + "：期望非零退出，实际 0\nSTDOUT:\n" + (result.stdout or ""),
        )

    # C1 git-push-firewall 传输边界
    def test_c1_transport_boundary(self) -> None:
        self.assertTrue(GPF.is_file(), "缺少 git-push-firewall/SKILL.md：" + str(GPF))
        self.assertTrue(GPF_SCRIPT.is_file(), "缺少 push-via-api.js：" + str(GPF_SCRIPT))
        text = GPF.read_text(encoding="utf-8")
        self.assertIn("不由此 skill 决定", text, "C1：必须写明目的地/PR/合并不由该 skill 决定")
        self.assertNotIn("ship-it", text, "C1：git-push-firewall 不得引用 ship-it")
        self.assertNotIn("可创建 PR", text, "C1：不得出现 PR 授权语")
        self.assertNotIn("可合并", text, "C1：不得出现合并授权语")
        self.assertLessEqual(len(text.splitlines()), 60, "C1：SKILL.md 不得超过 60 行")
        script = GPF_SCRIPT.read_text(encoding="utf-8")
        for token in ("--branch", "GH_BRANCH", "GET", "git/ref", "repo=${repo}", "branch=${branch}"):
            self.assertIn(token, script, "C1：push-via-api.js 缺 " + token)
        self.assertNotIn("默认 main", script, "C1：脚本不得静默默认 main")

    # C2 ship-it 远端写边界
    def test_c2_remote_write_boundary(self) -> None:
        self.assertTrue(SKILL.is_file(), "缺少 ship-it/SKILL.md")
        text = SKILL.read_text(encoding="utf-8")
        for phrase in SHIP_REQUIRED:
            self.assertIn(phrase, text, "C2：ship-it/SKILL.md 缺 " + phrase)
        self.assertNotIn("git-push-firewall", text, "C2：ship-it 不得点名 git-push-firewall")
        self.assertLessEqual(len(text.splitlines()), 350, "C2：ship-it/SKILL.md 不得超过 350 行")
        step7 = text[text.find("Step 7"):]
        self.assertIn("读", step7, "C2：Step 7 必须要求远端写前读上传工具")
        self.assertIn("分支", step7, "C2：Step 7 必须要求确认目标分支")

    # C3 文本质量（真实文件）
    def test_c3_text_quality(self) -> None:
        ship = SKILL.read_text(encoding="utf-8")
        gpf = GPF.read_text(encoding="utf-8")
        retro = RETRO.read_text(encoding="utf-8")
        self.assertLessEqual(len(ship.splitlines()), 350, "C3：ship-it ≤350 行")
        self.assertLessEqual(len(gpf.splitlines()), 60, "C3：git-push-firewall ≤60 行")
        self.assertLessEqual(len(retro.splitlines()), 150, "C3：复盘文件 ≤150 行")
        for name, text in (("ship-it", ship), ("git-push-firewall", gpf), ("retro", retro)):
            for word in BANNED:
                with self.subTest(file=name, word=word):
                    self.assertNotIn(word, text, name + " 含禁词：" + word)
        self.assertNotIn("git-push-firewall", ship, "C3：两 skill 不得互引")
        self.assertNotIn("ship-it", gpf, "C3：两 skill 不得互引")
        for rel in ("ship-it/SKILL.md", "README.md", "ship-it/references/spec-template.md"):
            self.assertNotIn("尽早", (ROOT / rel).read_text(encoding="utf-8"), rel + " 不得写“尽早”")

    # C4 机器检查（check_text 行为）
    def test_c4_check_text(self) -> None:
        real = run_check(ROOT, GPF, RETRO)
        self.assert_pass(real, "C4：真实仓库 check_text 应 PASS")
        self.assert_pass(check_fixture(), "C4：基线 fixture 应 PASS")

        self.assert_pass(check_fixture(ship=pad_lines(SHIP_BASE, 350)), "C4：ship-it 350 行应 PASS")
        self.assert_fail(check_fixture(ship=pad_lines(SHIP_BASE, 351)), "C4：ship-it 351 行应 FAIL")
        self.assert_pass(check_fixture(gpf=pad_lines(GPF_BASE, 60)), "C4：git-push 60 行应 PASS")
        self.assert_fail(check_fixture(gpf=pad_lines(GPF_BASE, 61)), "C4：git-push 61 行应 FAIL")
        self.assert_pass(check_fixture(retro=pad_lines(RETRO_BASE, 150)), "C4：复盘 150 行应 PASS")
        self.assert_fail(check_fixture(retro=pad_lines(RETRO_BASE, 151)), "C4：复盘 151 行应 FAIL")

        for word in BANNED:
            with self.subTest(banned=word):
                self.assert_fail(check_fixture(ship=SHIP_BASE + "\n- " + word + "处理。\n"),
                                 "C4：ship-it 禁词应 FAIL：" + word)
                self.assert_fail(check_fixture(gpf=GPF_BASE + "\n- " + word + "处理。\n"),
                                 "C4：git-push 禁词应 FAIL：" + word)

        self.assert_fail(check_fixture(ship=SHIP_BASE + "\n见 git-push-firewall。\n"),
                         "C4：ship-it 互引应 FAIL")
        self.assert_fail(check_fixture(gpf=GPF_BASE + "\n见 ship-it。\n"),
                         "C4：git-push 互引应 FAIL")
        self.assert_fail(check_fixture(gpf=GPF_BASE + "\n- 可创建 PR。\n"), "C4：PR 授权语应 FAIL")
        self.assert_fail(check_fixture(gpf=GPF_BASE + "\n- 可合并。\n"), "C4：合并授权语应 FAIL")
        for phrase in SHIP_REQUIRED:
            with self.subTest(missing=phrase):
                self.assert_fail(check_fixture(ship=SHIP_BASE.replace(phrase, "")),
                                 "C4：ship-it 缺必含短语应 FAIL：" + phrase)
        self.assert_fail(check_fixture(gpf=GPF_BASE.replace("不由此 skill 决定", "")),
                         "C4：git-push 缺边界短语应 FAIL")
        self.assert_fail(check_fixture(ship=SHIP_BASE + "\n## Step 7 提交 PR\n"),
                         "C4：重复标题应 FAIL")
        self.assert_fail(check_fixture(ship=SHIP_BASE + "\n范围 C1–C17；范围 C1–C18。\n"),
                         "C4：矛盾 C 计数应 FAIL")
        self.assert_fail(check_fixture(ship=SHIP_BASE + "\n范围 A1–A18；范围 A1–A19。\n"),
                         "C4：矛盾 A 计数应 FAIL")

        with tempfile.TemporaryDirectory(prefix="shipit-text-") as directory:
            root, gpf, retro = write_fixture(directory)
            result = invoke_script(CHECK_TEXT, ["--root", str(root), "--git-push", str(gpf),
                                                "--retro", str(retro), "--json"], ROOT)
            self.assert_pass(result, "C4：--json 应退出 0")
            data = json.loads(result.stdout)
            for key in ("errors", "warnings"):
                self.assertIn(key, data, "C4：--json 缺 " + key)

    # C5 验证闸门
    def test_c5_gates(self) -> None:
        self.assert_pass(invoke_script(CHECK_DOCS, ["--root", "."], ROOT), "C5：check_docs 应 PASS")
        self.assert_pass(run_check(ROOT, GPF, RETRO), "C5：check_text 应 PASS")
        self.assert_pass(
            invoke_script(CHECK_SPEC, [str(REAL_SPEC.relative_to(ROOT)), "--stage", "spec"], ROOT),
            "C5：check_spec --stage spec 应 PASS",
        )


    # C11 验证闸门（v4.7.2）
    def test_c11_gates(self) -> None:
        self.assert_pass(run_check(ROOT, GPF, RETRO), "C11：check_text 应 PASS")
        self.assert_pass(invoke_script(CHECK_DOCS, ["--root", "."], ROOT), "C11：check_docs 应 PASS")
        self.assert_pass(
            invoke_script(CHECK_SPEC, [str(REAL_SPEC_472.relative_to(ROOT)), "--stage", "spec"], ROOT),
            "C11：check_spec --stage spec（v4.7.2）应 PASS",
        )

if __name__ == "__main__":
    unittest.main(verbosity=2)