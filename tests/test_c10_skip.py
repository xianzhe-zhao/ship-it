#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C10 SKIP 语义行为级测试。

契约：ship-it/docs/specs/2026-11-19-contract-gates-and-concision.md C10。
规则：测试脚本遇 SKIP 必须退出码 2；退出码 0 + SKIP = 假绿 FAIL。

两种用法：
1) 作为测试：python -m unittest tests.test_c10_skip -v
2) 作为最小 runner：python tests/test_c10_skip.py <sample_test_file>
   - 有 SKIP → 退出码 2
   - 有 FAIL/ERROR → 退出码 1
   - 全 PASS → 退出码 0
"""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def load_sample(path: Path):
    spec = importlib.util.spec_from_file_location("c10_sample_under_test", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_sample(path: Path):
    """返回 (exit_code, skipped, failed)；有 SKIP 即 2（C10 优先于失败码）。"""
    module = load_sample(path)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    skipped = len(result.skipped)
    failed = len(result.failures) + len(result.errors)
    if skipped:
        return 2, skipped, failed
    if failed:
        return 1, skipped, failed
    return 0, skipped, failed


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stderr.write("用法：python tests/test_c10_skip.py <sample_test_file>\n")
        return 2
    code, skipped, failed = run_sample(Path(args[0]))
    print("skipped=%d failed=%d exit=%d" % (skipped, failed, code))
    return code


SAMPLE_SKIP = (
    "import unittest\n"
    "\n"
    "class SampleSkipTest(unittest.TestCase):\n"
    "    @unittest.skip('C10 demo skip')\n"
    "    def test_skipped(self):\n"
    "        pass\n"
)

SAMPLE_PASS = (
    "import unittest\n"
    "\n"
    "class SamplePassTest(unittest.TestCase):\n"
    "    def test_pass(self):\n"
    "        self.assertTrue(True)\n"
)

SAMPLE_FAIL = (
    "import unittest\n"
    "\n"
    "class SampleFailTest(unittest.TestCase):\n"
    "    def test_fail(self):\n"
    "        self.assertEqual(1, 2)\n"
)


class C10SkipSemanticsTest(unittest.TestCase):
    def run_runner(self, sample_text: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory(prefix="c10-skip-") as directory:
            sample = Path(directory) / "sample_test.py"
            sample.write_text(sample_text, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), str(sample)],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=120,
            )

    def test_c10_skip_must_exit_2(self) -> None:
        result = self.run_runner(SAMPLE_SKIP)
        self.assertEqual(
            result.returncode,
            2,
            "C10：sample skip 时 runner 必须退出码 2（实际 %d）\nSTDOUT:\n%s\nSTDERR:\n%s"
            % (result.returncode, result.stdout or "", result.stderr or ""),
        )
        self.assertIn("skipped=1", result.stdout or "", "runner 必须报告 SKIP 计数")

    def test_c10_no_skip_exit_0(self) -> None:
        result = self.run_runner(SAMPLE_PASS)
        self.assertEqual(result.returncode, 0, "C10：无 SKIP 且全 PASS 时 runner 应退出码 0")

    def test_c10_failure_exit_1(self) -> None:
        result = self.run_runner(SAMPLE_FAIL)
        self.assertEqual(result.returncode, 1, "C10：有 FAIL 且无 SKIP 时 runner 应退出码 1")


if __name__ == "__main__":
    sys.exit(main())
