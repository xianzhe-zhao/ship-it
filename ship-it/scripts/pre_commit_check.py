#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pre_commit_check.py — v4.7.1 C10 spec-first pre-commit gate.

用法：
    python ship-it/scripts/pre_commit_check.py check [--root .] [--base REF] [--json]
    python ship-it/scripts/pre_commit_check.py install-hooks [--root .] [--force]

check：
    1. git write-tree 取暂存区；git commit-tree -p HEAD 造临时提交（不移动 HEAD、不建 ref）。
    2. 对 base..临时提交 中变更的 spec 逐个跑 check_spec --stage spec --git-check --base <base> --head <temp>。
    3. 无 spec 变更时，对当前所有新规则 signed/accepted spec 跑同一检查（保证实现晚于最新 signed spec）。
    spec 与实现同提交、spec 未签、实现先于 spec 均由 check_spec 判 FAIL。

install-hooks：
    写 $(git rev-parse --git-path hooks)/pre-commit；已有非本工具 hook 时需 --force。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

SCRIPT_DIR = Path(__file__).resolve().parent
CHECK_SPEC = SCRIPT_DIR / "check_spec.py"
HOOK_MARKER = "ship-it v4.7.1 pre-commit"
HOOK_BODY = """#!/bin/sh
# ship-it v4.7.1 pre-commit gate (spec-first + hash_scope)
# runs check_spec.py --stage spec --git-check --base <base> --head <simulated commit>
set -e
ROOT="$(git rev-parse --show-toplevel)"
exec python "$ROOT/ship-it/scripts/pre_commit_check.py" check
"""
NEW_RULES_FROM = date(2026, 11, 19)


def run_git(root: Path, args, env=None):
    proc = subprocess.run(
        ["git", "-C", str(root)] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def detect_root(start: Path) -> Path:
    code, out, err = run_git(start, ["rev-parse", "--show-toplevel"])
    if code != 0:
        raise SystemExit("不是 git 仓库：%s" % (err or start))
    return Path(out).resolve()


def default_base(root: Path):
    code, _out, _err = run_git(root, ["rev-parse", "--verify", "--quiet", "origin/main^{commit}"])
    if code == 0:
        code, out, _err = run_git(root, ["merge-base", "HEAD", "origin/main"])
        if code == 0 and out:
            return out
    code, out, _err = run_git(root, ["rev-list", "--max-parents=0", "HEAD"])
    if code == 0 and out:
        return out.splitlines()[-1].strip()
    return None


def staged_tree(root: Path):
    code, out, err = run_git(root, ["write-tree"])
    if code != 0:
        raise SystemExit("git write-tree 失败：%s" % err)
    return out


def temp_commit(root: Path, tree: str, parent: str):
    args = ["commit-tree", tree]
    if parent:
        args += ["-p", parent]
    args += ["-m", "ship-it pre-commit check"]
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "ship-it pre-commit")
    env.setdefault("GIT_AUTHOR_EMAIL", "ship-it-pre-commit@localhost")
    env.setdefault("GIT_COMMITTER_NAME", "ship-it pre-commit")
    env.setdefault("GIT_COMMITTER_EMAIL", "ship-it-pre-commit@localhost")
    code, out, err = run_git(root, args, env=env)
    if code != 0:
        raise SystemExit("git commit-tree 失败：%s" % err)
    return out


def spec_date(name: str):
    import re
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-", Path(name).name)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def active_specs(root: Path):
    code, out, _err = run_git(root, ["ls-files", "docs/specs/*.md"])
    if code != 0:
        return []
    result = []
    for rel in out.splitlines():
        rel = rel.strip().replace("\\", "/")
        if not rel:
            continue
        parsed_date = spec_date(rel)
        if parsed_date is None or parsed_date < NEW_RULES_FROM:
            continue
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        head = text.split("---", 2)
        front = head[1] if len(head) >= 3 else ""
        status = ""
        for line in front.splitlines():
            if line.strip().startswith("status:"):
                status = line.split(":", 1)[1].strip().strip('"').strip("'")
                break
        if status in ("signed", "accepted"):
            result.append(rel)
    return result


def run_check(root: Path, base: str, head: str, specs):
    failures = []
    outputs = []
    for spec in specs:
        proc = subprocess.run(
            [sys.executable, str(CHECK_SPEC), spec, "--stage", "spec", "--git-check", "--base", base, "--head", head],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        outputs.append({"spec": spec, "exit": proc.returncode, "output": output})
        if proc.returncode != 0:
            failures.append(spec)
    return failures, outputs


def check(root: Path, base_override=None, as_json=False):
    code, _out, _err = run_git(root, ["diff", "--cached", "--name-only"])
    if code != 0:
        print("FAIL: git diff --cached 失败")
        return 1
    staged = [line.strip().replace("\\", "/") for line in _out.splitlines() if line.strip()]
    if not staged:
        print("PASS: 无暂存变更，跳过 pre-commit 闸门")
        return 0

    base = base_override or "HEAD"
    if not base:
        print("FAIL: 找不到 --base（无 origin/main 且无 root commit）；请显式传 --base")
        return 1
    code, parent, _err = run_git(root, ["rev-parse", "--verify", "--quiet", "HEAD"])
    parent = parent if code == 0 else ""
    tree = staged_tree(root)
    head = temp_commit(root, tree, parent)

    changed_specs = []
    code, out, _err = run_git(root, ["diff", "--name-only", base, head])
    if code == 0:
        changed_specs = [item.strip() for item in out.splitlines()
                         if item.strip().startswith("docs/specs/") and item.strip().endswith(".md")
                         and spec_date(item.strip()) is not None
                         and spec_date(item.strip()) >= NEW_RULES_FROM]
    active = sorted(active_specs(root))
    specs = sorted(set(changed_specs) | (set() if changed_specs else set(active[-1:])))
    if not specs:
        print("PASS: 无新规则 spec，跳过 pre-commit 闸门（staged=%d）" % len(staged))
        return 0

    failures, outputs = run_check(root, base, head, specs)
    if as_json:
        print(json.dumps({"ok": not failures, "base": base, "head": head, "staged": staged,
                          "specs": outputs}, ensure_ascii=False, indent=2))
    else:
        for item in outputs:
            print("--- %s (exit %d)" % (item["spec"], item["exit"]))
            print(item["output"].rstrip())
        print("PASS: pre-commit spec-first 闸门（%s）" % "、".join(specs) if not failures
              else "FAIL: pre-commit spec-first 闸门失败：%s" % "、".join(failures))
    return 0 if not failures else 1


def install_hooks(root: Path, force=False):
    code, hooks_dir, err = run_git(root, ["rev-parse", "--git-path", "hooks"])
    if code != 0:
        print("FAIL: 无法定位 hooks 目录：%s" % err)
        return 1
    hooks = Path(hooks_dir)
    if not hooks.is_absolute():
        hooks = (root / hooks).resolve()
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    if hook.exists():
        try:
            existing = hook.read_text(encoding="utf-8", errors="replace")
        except OSError:
            existing = ""
        if HOOK_MARKER not in existing and not force:
            print("FAIL: 已存在非 ship-it pre-commit hook：%s；确认后用 --force 覆盖" % hook)
            return 1
    with open(str(hook), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(HOOK_BODY)
    try:
        os.chmod(str(hook), 0o755)
    except OSError:
        pass
    print("PASS: 已安装 pre-commit hook：%s" % hook)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="v4.7.1 C10 spec-first pre-commit gate")
    parser.add_argument("command", nargs="?", choices=["check", "install-hooks"], default="check",
                        help="check（默认）或 install-hooks")
    parser.add_argument("--root", default=".", help="仓库根（默认当前目录）")
    parser.add_argument("--base", help="git 基准 ref（默认 origin/main 的 merge-base，否则 root commit）")
    parser.add_argument("--force", action="store_true", help="install-hooks 覆盖已有 hook")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = detect_root(Path(args.root).resolve())
    if args.command == "install-hooks":
        return install_hooks(root, force=args.force)
    return check(root, base_override=args.base, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
