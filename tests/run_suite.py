#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.7.1 C9 测试入口：四套全量 <5 分钟，报告记录 run window + 文件 hash。

用法：
  python tests/run_suite.py                 # 全量（默认五套）
  python tests/run_suite.py --fast          # 排除 @slow 用例
  python tests/run_suite.py --list          # 只列出将运行的用例（JSON）
  python tests/run_suite.py --out tmp/test-run.json

退出码：0 = 全 PASS 且在预算内；1 = FAIL/超预算；2 = 有 SKIP（C10 语义）。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import json
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SUITES = [
    "tests.test_process_gates",
    "tests.test_text_quality",
    "tests.test_reviewer_judge_contract",
    "tests.test_c10_skip",
    "tests.test_a19_accept_hash",
    "tests.test_v5_2_1_reliability",
]
DEFAULT_MAX_SECONDS = 300
DEFAULT_OUT = "tmp/test-run.json"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iter_tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item


def is_slow(test) -> bool:
    from tests.support.harness import is_slow as harness_is_slow
    return harness_is_slow(test)


def collect(names, fast=False) -> tuple:
    """返回 (suite, metadata)；fast=True 排除 @slow 用例。"""
    suite = unittest.TestSuite()
    metadata = []
    for name in names:
        module = importlib.import_module(name)
        path = Path(module.__file__)
        module_suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        selected = []
        for test in iter_tests(module_suite):
            if fast and is_slow(test):
                continue
            selected.append(test)
        suite.addTests(selected)
        metadata.append({"module": name, "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                         "path": path, "tests": len(selected)})
    return suite, metadata


def execute(suite, metadata, *, fast=False, max_seconds=DEFAULT_MAX_SECONDS, stream=None) -> dict:
    """运行 suite，返回报告（run window / 每文件 hash / 计数 / 耗时）。"""
    started = _now()
    started_clock = time.perf_counter()
    pre = {item["file"]: _sha256(item["path"]) for item in metadata}
    result = unittest.TextTestRunner(stream=stream or io.StringIO(), verbosity=1).run(suite)
    elapsed = time.perf_counter() - started_clock
    finished = _now()
    post = {item["file"]: _sha256(item["path"]) for item in metadata}
    files = []
    for item in metadata:
        files.append({
            "module": item["module"],
            "path": item["file"],
            "pre_sha256": pre[item["file"]],
            "post_sha256": post[item["file"]],
            "tests": item["tests"],
        })
    report = {
        "run_started_at": started,
        "run_finished_at": finished,
        "elapsed_seconds": round(elapsed, 3),
        "max_seconds": max_seconds,
        "fast": fast,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "files": files,
        "ok": result.wasSuccessful() and elapsed <= max_seconds,
        "over_budget": elapsed > max_seconds,
    }
    return report


def write_report(report: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _round_robin(items, chunks):
    chunks = max(1, min(chunks, len(items)))
    return [items[index::chunks] for index in range(chunks)]


def run_parallel(names, *, fast, max_seconds, jobs):
    """按用例分块并行（test_process_gates 拆 2–4 块，小套各 1 块）。"""
    import subprocess
    started = _now()
    started_clock = time.perf_counter()
    plan = []
    for name in names:
        suite, _meta = collect([name], fast=fast)
        ids = [test.id() for test in iter_tests(suite)]
        if not ids:
            continue
        chunks = max(2, min(4, jobs)) if name == "tests.test_process_gates" else 1
        plan.extend(_round_robin(ids, chunks))
    processes = []
    outs = []
    for index, group in enumerate(plan):
        out = ROOT / "tmp" / (".chunk-%d.json" % index)
        out.parent.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, "-m", "tests.run_suite", "--jobs", "1",
                   "--out", str(out.relative_to(ROOT)), "--quiet",
                   "--max-seconds", str(max_seconds), "--only"] + group
        processes.append(subprocess.Popen(command, cwd=str(ROOT),
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          text=True, encoding="utf-8", errors="replace"))
        outs.append(out)
    reports = []
    for process, out in zip(processes, outs):
        stdout, stderr = process.communicate()
        if out.is_file():
            reports.append(json.loads(out.read_text(encoding="utf-8")))
        else:
            reports.append({"tests_run": 0, "failures": 1, "errors": 0, "skipped": 0,
                            "files": [], "ok": False, "output": stdout + stderr})
    elapsed = time.perf_counter() - started_clock
    finished = _now()
    files = []
    files_by_path = {}
    for report in reports:
        for item in report.get("files", []):
            path = item.get("path")
            if path not in files_by_path:
                entry = dict(item)
                files_by_path[path] = entry
                files.append(entry)
            else:
                files_by_path[path]["tests"] = files_by_path[path].get("tests", 0) + item.get("tests", 0)
    for index, name in enumerate(names):
        path = Path(importlib.import_module(name).__file__)
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if not any(item.get("path") == rel for item in files):
            files.append({"module": name, "path": rel,
                          "pre_sha256": _sha256(path), "post_sha256": _sha256(path),
                          "tests": 0})
    return {
        "run_started_at": started,
        "run_finished_at": finished,
        "elapsed_seconds": round(elapsed, 3),
        "max_seconds": max_seconds,
        "fast": fast,
        "jobs": jobs,
        "tests_run": sum(item.get("tests_run", 0) for item in reports),
        "failures": sum(item.get("failures", 0) for item in reports),
        "errors": sum(item.get("errors", 0) for item in reports),
        "skipped": sum(item.get("skipped", 0) for item in reports),
        "files": files,
        "ok": all(item.get("ok") for item in reports) and elapsed <= max_seconds,
        "over_budget": elapsed > max_seconds,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="v4.7.1 测试 runner（C9）")
    parser.add_argument("--fast", action="store_true", help="排除 @slow 用例")
    parser.add_argument("--list", action="store_true", help="只列出将运行的用例（JSON）")
    parser.add_argument("--suites", nargs="*", default=SUITES, help="模块名列表")
    parser.add_argument("--out", default=DEFAULT_OUT, help="报告 JSON 路径")
    parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS)
    parser.add_argument("--jobs", type=int, default=4, help="并行块数（1=串行）")
    parser.add_argument("--only", nargs="+", default=None, help="只跑指定用例 id（内部并行分块用）")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path = out_path.resolve()
    if not out_path.is_relative_to(ROOT):
        print("ERROR: --out 越出仓库根：%s（C1：测试产物不得写出仓库根）" % args.out)
        return 1
    if args.only:
        suite = unittest.TestLoader().loadTestsFromNames(args.only)
        modules = {}
        for test_id in args.only:
            name = ".".join(test_id.split(".")[:-2])
            modules[name] = modules.get(name, 0) + 1
        metadata = []
        for name, count in modules.items():
            path = Path(importlib.import_module(name).__file__)
            metadata.append({"module": name,
                             "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                             "path": path, "tests": count})
    else:
        suite, metadata = collect(args.suites, fast=args.fast)
    if args.list:
        ids = [test.id() for test in iter_tests(suite)]
        print(json.dumps({"fast": args.fast, "count": len(ids), "tests": ids},
                         ensure_ascii=False, indent=2))
        return 0
    if args.only:
        stream = io.StringIO() if args.quiet else sys.stdout
        report = execute(suite, metadata, fast=args.fast, max_seconds=args.max_seconds, stream=stream)
    elif args.jobs > 1 and len(args.suites) > 1:
        report = run_parallel(args.suites, fast=args.fast,
                              max_seconds=args.max_seconds, jobs=args.jobs)
    else:
        stream = io.StringIO() if args.quiet else sys.stdout
        report = execute(suite, metadata, fast=args.fast, max_seconds=args.max_seconds, stream=stream)
    write_report(report, out_path)
    if not args.quiet:
        print("run window: %s .. %s（%.1f 秒）" % (
            report["run_started_at"], report["run_finished_at"], report["elapsed_seconds"]))
        print("tests=%d failures=%d errors=%d skipped=%d budget=%s" % (
            report["tests_run"], report["failures"], report["errors"],
            report["skipped"], "PASS" if not report["over_budget"] else "OVER"))
    if report["skipped"]:
        return 2
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())