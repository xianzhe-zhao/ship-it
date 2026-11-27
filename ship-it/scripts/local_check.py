#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""local_check.py — 本地严格复刻 CI（v5.2.1 / C4）：1:1 复刻 ship-it-gates.yml 四步。

让本地一键跑与 CI 完全相同的 4 步、相同参数，消除"本地绿 CI 红"的偏差。

用法：
    python ship-it/scripts/local_check.py                    # 默认 --base HEAD（模拟 push）
    python ship-it/scripts/local_check.py --pr-base origin/main  # 模拟 PR，取该 ref SHA
    python ship-it/scripts/local_check.py --json              # JSON 输出

CI 4 步（ship-it-gates.yml）：
    1. check_spec <changed specs> --stage spec --git-check --base <BASE>
    2. check_text --root . --allow-missing-git-push
    3. check_docs --root .
    4. python -m tests.run_suite

退出码：0=全过，2=有 SKIP 但无 failure/error，1=真失败。
不加 check_roles（CI 没跑，加了反而和 CI 不一致）。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DEFAULT = Path(__file__).resolve().parents[2]  # ship-it/scripts/../.. = repo root


def run_git(args, cwd):
    proc = subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8"
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def resolve_base(root, base_flag, pr_base_flag):
    """解析 base SHA：--base HEAD 取 HEAD；--pr-base <ref> 取该 ref 的 SHA。"""
    if pr_base_flag:
        code, out, err = run_git(["rev-parse", pr_base_flag], root)
        if code != 0:
            return None, "git rev-parse %s 失败：%s" % (pr_base_flag, err)
        return out, None
    # 默认 --base HEAD
    code, out, err = run_git(["rev-parse", base_flag or "HEAD"], root)
    if code != 0:
        return None, "git rev-parse %s 失败：%s" % (base_flag or "HEAD", err)
    return out, None


def changed_specs(root, base):
    """git diff --name-only base..HEAD -- ship-it/docs/specs/*.md，返回改动 spec 列表。"""
    code, out, _err = run_git(["diff", "--name-only", "%s..HEAD" % base, "--", "ship-it/docs/specs/*.md"], root)
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def run_step(name, cmd, root):
    """跑一步，返回 (exit_code, stdout+stderr)。"""
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(root))
    output = proc.stdout + proc.stderr
    return proc.returncode, output


def main(argv=None):
    parser = argparse.ArgumentParser(description="本地严格复刻 CI（v5.2.1 / C4）")
    parser.add_argument("--root", default=str(ROOT_DEFAULT), help="仓库根（默认脚本上级两级）")
    parser.add_argument("--base", default="HEAD", help="base 模式：HEAD（默认，模拟 push）")
    parser.add_argument("--pr-base", dest="pr_base", default=None, help="PR 模式：取该 ref SHA（模拟 PR）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    base, base_err = resolve_base(root, args.base, args.pr_base)
    if base_err:
        print("ERROR: %s" % base_err, file=sys.stderr)
        return 1

    steps = []
    overall_skip = False
    failed = False

    # Step 1: check_spec <changed specs> --stage spec --git-check --base <base>
    specs = changed_specs(root, base)
    step1_outputs = []
    if not specs:
        step1_outputs.append("no changed spec; skip check_spec")
        step1_exit = 0
    else:
        step1_exit = 0
        for spec in specs:
            cmd = [sys.executable, str(SCRIPT_DIR / "check_spec.py"), spec,
                   "--stage", "spec", "--git-check", "--base", base]
            code, out = run_step("check_spec/%s" % spec, cmd, root)
            step1_outputs.append("== %s (base=%s)\n%s" % (spec, base, out))
            if code != 0:
                step1_exit = code
                break
    steps.append({"name": "1. check_spec --git-check", "exit": step1_exit, "output": "\n".join(step1_outputs)})
    if step1_exit != 0:
        failed = True
        print("第 1 步失败（check_spec）", file=sys.stderr)
        for o in step1_outputs:
            print(o, file=sys.stderr)
        return emit(failed, overall_skip, steps, args.json)

    # Step 2: check_text --root . --allow-missing-git-push
    cmd2 = [sys.executable, str(SCRIPT_DIR / "check_text.py"), "--root", ".", "--allow-missing-git-push"]
    code2, out2 = run_step("check_text", cmd2, root)
    steps.append({"name": "2. check_text --allow-missing-git-push", "exit": code2, "output": out2})
    if code2 != 0 and code2 != 2:
        failed = True
        print("第 2 步失败（check_text）", file=sys.stderr)
        print(out2, file=sys.stderr)
        return emit(failed, overall_skip, steps, args.json)
    if code2 == 2:
        overall_skip = True

    # Step 3: check_docs --root .
    cmd3 = [sys.executable, str(SCRIPT_DIR / "check_docs.py"), "--root", "."]
    code3, out3 = run_step("check_docs", cmd3, root)
    steps.append({"name": "3. check_docs --root .", "exit": code3, "output": out3})
    if code3 != 0 and code3 != 2:
        failed = True
        print("第 3 步失败（check_docs）", file=sys.stderr)
        print(out3, file=sys.stderr)
        return emit(failed, overall_skip, steps, args.json)
    if code3 == 2:
        overall_skip = True

    # Step 4: python -m tests.run_suite
    cmd4 = [sys.executable, "-m", "tests.run_suite"]
    code4, out4 = run_step("tests.run_suite", cmd4, root)
    steps.append({"name": "4. tests.run_suite", "exit": code4, "output": out4})
    if code4 != 0 and code4 != 2:
        failed = True
        print("第 4 步失败（tests.run_suite）", file=sys.stderr)
        print(out4, file=sys.stderr)
        return emit(failed, overall_skip, steps, args.json)
    if code4 == 2:
        overall_skip = True

    return emit(failed, overall_skip, steps, args.json)


def emit(failed, overall_skip, steps, as_json):
    if as_json:
        print(json.dumps({"failed": failed, "skip": overall_skip, "steps": steps}, ensure_ascii=False, indent=2))
    else:
        for s in steps:
            status = "PASS" if s["exit"] == 0 else ("SKIP" if s["exit"] == 2 else "FAIL(%d)" % s["exit"])
            print("[%s] %s" % (status, s["name"]))
    if failed:
        return 1
    return 2 if overall_skip else 0


if __name__ == "__main__":
    sys.exit(main())
