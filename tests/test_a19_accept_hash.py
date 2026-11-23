#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A19 行为测试：验收勾选采用代码层归一化，不改变 sign_hash。

契约：docs/specs/2026-11-19-contract-gates-and-concision.md（spec_revision 4）。
规则：sign_hash 只覆盖 §§1–8；`- [ ] A<n>` 与 `- [x] A<n>` 归一化后 hash 相同；
      填 A/acceptance 后 `--stage accept` PASS；§§1–8 改一行 FAIL。
"""

from __future__ import annotations

import re
import shutil
import unittest
from pathlib import Path

from tests.test_process_gates import (
    CHECK_SPEC,
    ROOT,
    SPEC_REL,
    accept_front,
    build_spec,
    git_commit,
    init_git,
    insert_before_section,
    parse_frontmatter,
    read_text,
    run_py,
    sign_spec,
    temp_repo,
    write_case_and_report,
    write_text,
)

GIT = shutil.which("git")
REAL_SPEC = ROOT / "docs" / "specs" / "2026-11-19-contract-gates-and-concision.md"
ACCEPTANCE_CHECK_RE = re.compile(r"(?m)^(\s*[-*]\s+\[) \)(\s+\*{0,2}A\d+\b)")
ACCEPTANCE_UNCHECK_RE = re.compile(r"(?m)^(\s*[-*]\s+\[)[xX](\]\s+\*{0,2}A\d+\b)")
ACCEPTANCE_LINE_RE = ACCEPTANCE_CHECK_RE


def signed_hash() -> str:
    value = parse_frontmatter(read_text(REAL_SPEC)).get("sign_hash", "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AssertionError("真实 spec 必须已签约并含 64 位 sign_hash")
    return value


def printed_hash(root: Path, rel: str = SPEC_REL) -> str:
    result = run_py(CHECK_SPEC, [rel, "--print-sign-hash"], cwd=root)
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    match = re.search(r"[0-9a-fA-F]{64}", output)
    if result.returncode != 0 or not match:
        raise AssertionError("--print-sign-hash 失败：exit=%d\n%s" % (result.returncode, output))
    return match.group(0).lower()


class A19AcceptHashTest(unittest.TestCase):
    maxDiff = None

    def assert_pass(self, result, label: str) -> None:
        self.assertEqual(
            result.returncode,
            0,
            label + "：期望退出码 0，实际 " + str(result.returncode)
            + "\nSTDOUT:\n" + (result.stdout or "")
            + "\nSTDERR:\n" + (result.stderr or ""),
        )

    def assert_fail(self, result, label: str) -> None:
        self.assertNotEqual(
            result.returncode,
            0,
            label + "：期望非零退出，实际 0"
            + "\nSTDOUT:\n" + (result.stdout or "")
            + "\nSTDERR:\n" + (result.stderr or ""),
        )

    def test_a19_acceptance_marks_hash_stable(self) -> None:
        expected = signed_hash()
        text = read_text(REAL_SPEC)
        unchecked_text = ACCEPTANCE_UNCHECK_RE.sub(r"\1 \2", text)
        checked_text = ACCEPTANCE_CHECK_RE.sub(r"\1x\2", text)
        self.assertNotEqual(unchecked_text, checked_text, "真实 spec 必须存在 A 行（[ ] 或 [x]）")
        with temp_repo() as root:
            write_text(root / SPEC_REL, unchecked_text)
            unchecked = printed_hash(root)
            write_text(root / SPEC_REL, checked_text)
            checked = printed_hash(root)
        self.assertEqual(unchecked, expected, "A [ ] 时 --print-sign-hash 必须等于签约值")
        self.assertEqual(checked, expected, "A [x] 与 A [ ] 归一化后 sign hash 必须相同（A19）")

    @unittest.skipUnless(GIT, "需要 git 命令")
    def test_a19_fill_acceptance_then_accept_pass(self) -> None:
        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            git_commit(root, "init", "2026-11-19T10:00:00+0800")
            sign_spec(root)
            hash_value = printed_hash(root)
            git_commit(root, "docs(spec): sign", "2026-11-19T10:01:00+0800")
            write_case_and_report(root)
            c0 = git_commit(root, "test: fixture", "2026-11-19T10:02:00+0800")
            filled = build_spec(
                acceptance_checked=True,
                front=accept_front(c0),
            ).replace("0" * 64, hash_value)
            write_text(root / SPEC_REL, filled)
            self.assertEqual(printed_hash(root), hash_value, "填 A [x] 后 sign_hash 不得变化（A19）")
            self.assert_pass(
                run_py(CHECK_SPEC, [SPEC_REL, "--stage", "spec"], cwd=root),
                "填 A [x] 后 --stage spec 应 PASS",
            )
            self.assert_pass(
                run_py(CHECK_SPEC, [SPEC_REL, "--stage", "accept"], cwd=root),
                "填 A/acceptance 后 --stage accept 应 PASS（A19）",
            )

    def test_a19_sections_1_8_change_fails(self) -> None:
        with temp_repo() as root:
            sign_spec(root)
            hash_value = printed_hash(root)
            changed = insert_before_section(read_text(root / SPEC_REL), 6, "- **修订**：§§1–8 改一行。")
            write_text(root / SPEC_REL, changed)
            self.assertNotEqual(printed_hash(root), hash_value, "§§1–8 改一行必须改变 sign hash")
            self.assert_fail(
                run_py(CHECK_SPEC, [SPEC_REL, "--stage", "spec"], cwd=root),
                "§§1–8 改一行后 --stage spec 应 FAIL（A19）",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
