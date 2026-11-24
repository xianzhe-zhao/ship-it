#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""流程闸门契约测试（v4.7.0 C1–C18 / A1–A18 + v4.7.1 C6–C10 / A6–A10）。

契约：
- docs/specs/2026-11-19-contract-gates-and-concision.md（v4.7.0，C1–C18）
- docs/specs/2026-11-20-skill-concision.md（v4.7.1，C6–C10：首写标记/暂停前 spec/历史 hash/测试速度/提交顺序）
测试从契约派生，不从实现派生；断言先按 spec 写，不因实现放宽。

运行（Step 4）：
    python tests/run_suite.py             # 全量，报告写 tmp/test-run.json
    python tests/run_suite.py --fast      # 排除 @slow
    python -m unittest tests.test_process_gates -v

约定：
- 临时 fixture 放 tempfile.TemporaryDirectory()，cwd 即仓库根；不写仓库内文件。
- 脚本走 tests/support/harness.py 进程内调用；git fixture 用批量 fast-import（C9）。
- 用例名与 spec 第 9 节核销表一致；v4.7.1 新增 test_c6_first_write_marker / test_c7_pause_pre_change /
  test_c8_git_check_revisions / test_c9_test_speed / test_c10_commit_order。
- 测试报告证据块：每个测试文件记 path/pre_sha256/post_sha256/run_started_at/run_finished_at。
- C14–C17 fixture：start artifact / patrol / pause / failure log 固定字段见 spec 第 3 节数据格式。
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from tests.support.harness import (
    build_history,
    cached_repo,
    commit_worktree,
    ensure_git,
    invoke_script,
    slow,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "ship-it" / "scripts"
CHECK_SPEC = SCRIPTS / "check_spec.py"
CHECK_ROLES = SCRIPTS / "check_roles.py"
GUARD = SCRIPTS / "guard_large_write.py"
CHECK_DOCS = SCRIPTS / "check_docs.py"
CHECK_TEXT = SCRIPTS / "check_text.py"
RUN_SUITE = ROOT / "tests" / "run_suite.py"
GIT = shutil.which("git")

DATE = "2026-11-19"
SPEC_REL = "docs/specs/2026-11-19-fixture.md"
SPEC_REL_472 = "docs/specs/2026-11-21-fixture.md"
CASE_REL = "tests/test_fixture_gate.py"
CASE_REL2 = "tests/test_fixture_gate2.py"
REPORT_REL = "docs/reviews/2026-11-19-test-report.md"
PATROL_REL = "docs/reviews/" + DATE + "-auditor-patrol.md"
PAUSE_REL = "docs/reviews/" + DATE + "-pause.md"
FAILURE_REL = "docs/reviews/" + DATE + "-failure-log.md"
START_ROLES = (("referee", "referee-j1"), ("security", "security-1"), ("auditor", "auditor-1"))
LEGACY_SPEC_REL = "docs/specs/2026-11-17-runtime-model-dispatch.md"
TICK = chr(96)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_py(script: Path, args, cwd: Path):
    """C9：进程内调用脚本（不再逐用例起 Python 子进程）。

    返回对象与 subprocess.CompletedProcess 兼容（returncode/stdout/stderr），
    断言代码无需改动；脚本 main(argv) 只依赖 cwd 与文件，语义等价。
    """
    return invoke_script(script, args, cwd)


def run_git(cwd: Path, *args: str, env_extra=None) -> subprocess.CompletedProcess:
    if not GIT:
        raise unittest.SkipTest("需要 git 命令")
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [GIT] + list(args),
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
        timeout=120,
    )


def require_git_ok(result: subprocess.CompletedProcess, label: str) -> None:
    if result.returncode != 0:
        raise AssertionError(label + " 失败：\n" + (result.stdout or "") + (result.stderr or ""))


def init_git(root: Path) -> None:
    """复制 .git 骨架（一次 git init 的模板），不再逐 fixture 起 git init。"""
    ensure_git(root)


def git_head(root: Path) -> str:
    """直接读 ref 文件；读不到再回退 git rev-parse。"""
    head = (root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        ref = head[5:].strip()
        ref_file = root / ".git" / ref
        if ref_file.is_file():
            return ref_file.read_text(encoding="utf-8").strip()
    result = run_git(root, "rev-parse", "HEAD")
    require_git_ok(result, "git rev-parse HEAD")
    return (result.stdout or "").strip()


def git_commit(root: Path, message: str, when: str) -> str:
    """一次 git fast-import 提交当前工作区（替代 add + commit 两次起进程）。"""
    return commit_worktree(root, message, when)


@contextmanager
def temp_repo():
    """fixture 的 cwd 即仓库根；默认不建 git（脚本 detect_repo_root 固定为 cwd）。

    需要真实历史的用例显式调用 init_git()（复制骨架，零 git init 进程）。
    """
    with tempfile.TemporaryDirectory(prefix="shipit-gates-") as directory:
        root = Path(directory)
        yield root


@contextmanager
def nested_repo():
    with tempfile.TemporaryDirectory(prefix="shipit-gates-") as directory:
        parent = Path(directory)
        root = parent / "repo"
        root.mkdir()
        yield parent, root


SIGN_PROMPT = (
    "刚才的说明可能造成误解：是否要签约？如果需要签约，请发送“签约”两个字才可以；"
    "不发送“签约”两个字，我不会开始编码。只发送这两个字，不要加标点、引号或其他内容。"
)
ACCEPT_PROMPT = (
    "刚才的说明可能造成误解：是否需要验收？如果需要验收，请发送“验收”两个字才可以；"
    "不发送“验收”两个字，我不会进入 PR。只发送这两个字，不要加标点、引号或其他内容。"
)

FRONT_KEYS = [
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
    "accept_prompt",
    "accept_requested_at",
    "accepted_by",
    "accepted_at",
    "accept_quote",
    "accept_commit",
    "accepted_items",
]

DEFAULT_FRONT = {
    "spec_version": "2",
    "spec_revision": "3",
    "status": "signed",
    "sign_prompt": SIGN_PROMPT,
    "sign_requested_at": "2026-11-19T09:00:00+08:00",
    "signed_by": "用户",
    "signed_at": "2026-11-19T09:10:00+08:00",
    "sign_quote": "签约",
    "sign_hash": "0" * 64,
    "confirmed_clauses": "C1-C2",
    "decisions": "D1=测试",
    "accept_prompt": "",
    "accept_requested_at": "",
    "accepted_by": "",
    "accepted_at": "",
    "accept_quote": "",
    "accept_commit": "",
    "accepted_items": "",
}

CLAUSE_C1 = (
    "### C1 测试条款一\n\n"
    "- **前置**：无。\n"
    "- **后置**：通过。\n"
    "- **失败**：失败。\n"
    "- **不变式**：不变。"
)
CLAUSE_C2 = (
    "### C2 测试条款二\n\n"
    "- **前置**：无。\n"
    "- **后置**：通过。\n"
    "- **失败**：失败。\n"
    "- **不变式**：不变。"
)
DEFAULT_CLAUSES = CLAUSE_C1 + "\n\n" + CLAUSE_C2

DEFAULT_RECONCILIATION = (
    "| 条款 | 用例名 | 用例文件 | 结果 | 路径真实性 |\n"
    "|---|---|---|---|---|\n"
    "| C1 | test_fixture_c1 | tests/test_fixture_gate.py | ✅ | 机器：check_spec |\n"
    "| C2 | test_fixture_c2 | tests/test_fixture_gate.py | ✅ | 机器：check_spec |"
)

RECON_PENDING = (
    "| 条款 | 用例名 | 用例文件 | 结果 | 路径真实性 |\n"
    "|---|---|---|---|---|\n"
    "| C1 | test_fixture_c1 | tests/test_fixture_gate.py | 待测 | 机器：check_spec |\n"
    "| C2 | test_fixture_c2 | tests/test_fixture_gate.py | 待测 | 机器：check_spec |"
)

FOUR_COL_RECONCILIATION = (
    "| 条款 | 用例名 | 结果 | 路径真实性 |\n"
    "|---|---|---|---|\n"
    "| C1 | test_fixture_c1 | ✅ | 机器 |\n"
    "| C2 | test_fixture_c2 | ✅ | 机器 |"
)


def recon_5(case1="test_fixture_c1", case2="test_fixture_c2", file1=CASE_REL, file2=CASE_REL,
            result1="✅", result2="✅", truth1="机器：check_spec", truth2="机器：check_spec") -> str:
    return "\n".join([
        "| 条款 | 用例名 | 用例文件 | 结果 | 路径真实性 |",
        "|---|---|---|---|---|",
        "| C1 | " + case1 + " | " + file1 + " | " + result1 + " | " + truth1 + " |",
        "| C2 | " + case2 + " | " + file2 + " | " + result2 + " | " + truth2 + " |",
    ])


def default_acceptance(checked: bool) -> str:
    mark = "[x]" if checked else "[ ]"
    return "- " + mark + " A1 测试验收一。\n- " + mark + " A2 测试验收二。"


def draft_front() -> dict:
    return {
        "status": "draft",
        "sign_prompt": "",
        "sign_requested_at": "",
        "signed_by": "",
        "signed_at": "",
        "sign_quote": "",
        "sign_hash": "",
        "confirmed_clauses": "",
        "decisions": "",
    }


def build_spec(
    *,
    front=None,
    clauses=None,
    acceptance=None,
    acceptance_checked=False,
    three_checked=True,
    section2_extra="",
    entry_inventory="无 UI 变更",
    frontend="无变更",
    reconciliation=None,
    footer=None,
    section9_extra="",
    body_suffix="",
    hash_scope=None,
) -> str:
    fm = dict(DEFAULT_FRONT)
    if front:
        fm.update(front)
    clause_text = clauses if clauses is not None else DEFAULT_CLAUSES
    acceptance_text = acceptance if acceptance is not None else default_acceptance(acceptance_checked)
    recon = reconciliation if reconciliation is not None else DEFAULT_RECONCILIATION
    foot = footer if footer is not None else "- 测试报告：" + REPORT_REL

    lines = ["---"]
    for key in FRONT_KEYS:
        value = str(fm.get(key, "")).replace('"', "'")
        if key in ("spec_version", "spec_revision", "status"):
            lines.append(key + ": " + value)
        else:
            lines.append(key + ': "' + value + '"')
        if key == "spec_revision" and hash_scope:
            lines.append("hash_scope: " + hash_scope)
    lines.append("---")
    lines.append("")
    lines.append("# 2026-11-19 闸门测试夹具 — spec 契约")
    lines.append("")
    lines.append("## 1. 背景与目标（what & why）")
    lines.append("")
    lines.append("夹具用于验证流程闸门，不实现真实功能。")
    lines.append("")
    lines.append("### 需求澄清记录（Step 1 产出，签约时展示给用户确认）")
    lines.append("")
    lines.append("- **原始需求**：验证闸门。")
    lines.append("- **优化后需求**：验证闸门。")
    lines.append("- **优化说明**：无。")
    lines.append("- **用户问答**：无疑问。")
    lines.append("- **用户约束（裁判员规则源）**：无。")
    lines.append("- **决策展示（D1）**：")
    lines.append("")
    lines.append("| # | 决策 | 选定 | 理由 |")
    lines.append("|---|---|---|---|")
    lines.append("| D1 | 范围 | 测试 | 测试 |")
    lines.append("")
    lines.append("## 2. 方案自审（怎么做）")
    lines.append("")
    lines.append("- **复用盘点**：无。")
    lines.append("- **决策**：B 扩展。")
    lines.append("- **影响面**：无。")
    lines.append("- **兼容性**：无。")
    lines.append("- **成本预算**：无。")
    lines.append("- **安全增量**：无。")
    lines.append("- **测试策略**：unittest。")
    lines.append("- **执行形态/角色矩阵**：形态 3。")
    if entry_inventory is not None:
        lines.append("- 入口清单：" + entry_inventory)
    if section2_extra:
        lines.extend(section2_extra.rstrip("\n").splitlines())
    lines.append("- **流程规则（P1–P2，一行一条）**：")
    lines.append("  - P1 测试规则一。")
    lines.append("  - P2 测试规则二。")
    lines.append("")
    lines.append("## 3. 技术蓝图（按涉及领域填，不涉及写“无变更”）")
    lines.append("")
    lines.append("- **前端**：" + frontend + "。")
    lines.append("- **后端**：无变更。")
    lines.append("- **数据库**：无变更。")
    lines.append("- **环境依赖**：无变更。")
    lines.append("- **Step 3 产出**：代码 diff + 自检结果（语法/测试/门禁）+ 条款追溯（C13 产出物 schema）。")
    lines.append("")
    lines.append("## 4. 非目标（out of scope）")
    lines.append("")
    lines.append("- 不做：不做真实功能。")
    lines.append("")
    lines.append("## 4.5 执行模式（用户裁定，AI 不得自选）")
    lines.append("")
    lines.append("**本次执行模式**：单干（用户裁定）。")
    lines.append("")
    lines.append("## 5. 契约条款（C1 / C2 / …）")
    lines.append("")
    lines.extend(clause_text.rstrip("\n").splitlines())
    lines.append("")
    lines.append("## 6. 验收标准（用户逐条打勾）")
    lines.append("")
    lines.extend(acceptance_text.rstrip("\n").splitlines())
    lines.append("")
    lines.append("## 7. 边界与异常")
    lines.append("")
    lines.append("| 场景 | 期望表现 |")
    lines.append("|---|---|")
    lines.append("| 越界 | 非零退出 |")
    lines.append("")
    lines.append("## 8. 三问完整性检查 + DoR（不过不得开工）")
    lines.append("")
    mark = "[x]" if three_checked else "[ ]"
    lines.append("- " + mark + " ① **取值范围**：枚举。")
    lines.append("- " + mark + " ② **状态流转**：draft → signed。")
    lines.append("- " + mark + " ③ **生成逻辑**：脚本退出码。")
    lines.append("")
    lines.append("**DoR 自检**：需求无歧义 ☑、技术可行 ☑、影响面已盘 ☑。")
    lines.append("")
    lines.append("## 9. 核销记录（Step 5 填写，PR 里引用）")
    lines.append("")
    lines.extend(recon.rstrip("\n").splitlines())
    lines.append("")
    lines.append(foot)
    if section9_extra:
        lines.extend(section9_extra.rstrip("\n").splitlines())
    if body_suffix:
        lines.extend(body_suffix.rstrip("\n").splitlines())
    return "\n".join(lines) + "\n"


def sign_spec(root: Path, *, rel: str = SPEC_REL, **kwargs) -> str:
    text = build_spec(**kwargs)
    path = root / rel
    write_text(path, text)
    result = run_py(CHECK_SPEC, [rel, "--print-sign-hash"], cwd=root)
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    match = re.search(r"[0-9a-fA-F]{64}", output)
    if not match:
        raise AssertionError("--print-sign-hash 未输出 64 位 SHA-256；exit=" + str(result.returncode) + "\n" + output)
    text = text.replace("0" * 64, match.group(0))
    write_text(path, text)
    return text


def accept_front(c0: str, **overrides) -> dict:
    front = {
        "status": "accepted",
        "accept_prompt": ACCEPT_PROMPT,
        "accept_requested_at": "2026-11-19T10:05:00+08:00",
        "accepted_by": "用户",
        "accepted_at": "2026-11-19T10:10:00+08:00",
        "accept_quote": "验收",
        "accept_commit": c0,
        "accepted_items": "A1-A2",
    }
    front.update(overrides)
    return front


def run_spec(root: Path, stage: str, *extra: str) -> subprocess.CompletedProcess:
    return run_py(CHECK_SPEC, [SPEC_REL, "--stage", stage] + list(extra), cwd=root)


def run_roles(root: Path, stage: str, *extra: str) -> subprocess.CompletedProcess:
    return run_py(CHECK_ROLES, ["--date", DATE, "--stage", stage, "--spec", SPEC_REL] + list(extra), cwd=root)


def run_roles_spec(root: Path, stage: str, spec_rel: str, *extra: str) -> subprocess.CompletedProcess:
    return run_py(CHECK_ROLES, ["--date", DATE, "--stage", stage, "--spec", spec_rel] + list(extra), cwd=root)


def guard(root: Path, action: str, rel: str, *extra: str) -> subprocess.CompletedProcess:
    return run_py(GUARD, [action, rel] + list(extra), cwd=root)


LARGE_REL = "tmp/large.txt"
LARGE_BACKUP = "tmp/large.bak"
LARGE_MANIFEST = "tmp/large.manifest.json"
LARGE_TAIL = "TAIL-END"


def make_large_file(root: Path, line_count: int = 1000) -> str:
    lines = []
    for index in range(1, line_count):
        lines.append(str(index).zfill(4) + " 中文内容中文内容 " + "x" * 40)
    lines.append(LARGE_TAIL)
    text = "\n".join(lines) + "\n"
    write_text(root / LARGE_REL, text)
    return text


def guard_prepare(root: Path) -> subprocess.CompletedProcess:
    return guard(
        root,
        "prepare",
        LARGE_REL,
        "--backup",
        LARGE_BACKUP,
        "--manifest",
        LARGE_MANIFEST,
        "--tail-marker",
        LARGE_TAIL,
    )


def guard_check(root: Path) -> subprocess.CompletedProcess:
    return guard(root, "check", LARGE_REL, "--backup", LARGE_BACKUP, "--manifest", LARGE_MANIFEST)


def guard_restore(root: Path) -> subprocess.CompletedProcess:
    return guard(root, "restore", LARGE_REL, "--backup", LARGE_BACKUP, "--manifest", LARGE_MANIFEST)


def evidence_block(root: Path, rel: str, *, pre=None, post=None,
                        started=None, finished=None, omit=()) -> str:
    """C6 测试报告每文件证据块：path/pre_sha256/post_sha256/run_started_at/run_finished_at。"""
    actual = sha256_file(root / rel)
    values = {
        "path": rel,
        "pre_sha256": actual if pre is None else pre,
        "post_sha256": actual if post is None else post,
        "run_started_at": started if started is not None else iso_at(10, 5),
        "run_finished_at": finished if finished is not None else iso_at(10, 6),
    }
    lines = ["### " + rel]
    for key in ("path", "pre_sha256", "post_sha256", "run_started_at", "run_finished_at"):
        if key in omit:
            continue
        lines.append("- " + key + ": " + values[key])
    return "\n".join(lines)


def write_case_and_report(root: Path, *, report_body=None, cases=None, evidence_blocks=None,
                          run_started=None, run_finished=None) -> None:
    if cases is None:
        cases = [(CASE_REL, ("test_fixture_c1", "test_fixture_c2"))]
    for rel, names in cases:
        case_lines = []
        for name in names:
            case_lines.append("# PASS")
            case_lines.append("def " + name + "():")
            case_lines.append("    assert True")
            case_lines.append("")
        write_text(root / rel, "\n".join(case_lines))
        set_mtime(root / rel, iso_at(10, 0))
    if callable(evidence_blocks):
        evidence_blocks = evidence_blocks()
    if evidence_blocks is None:
        evidence_blocks = "\n\n".join(
            evidence_block(root, rel, started=run_started, finished=run_finished)
            for rel, _names in cases
        )
    if report_body is None:
        body_lines = []
        for _rel, names in cases:
            for name in names:
                body_lines.append("- " + name + ": PASS")
        body_lines.extend(["- 核销率: 2/2", "- E2E: 13/13"])
        report_body = "\n".join(body_lines)
    write_text(
        root / REPORT_REL,
        "# 测试报告\n\n" + report_body + "\n\n## 测试文件证据\n\n" + evidence_blocks + "\n",
    )


def review_report(name, role, reviewer, session, verdict="PASS", evidence=None,
                  coding_decl=True, spec_decl=True, spec_revision="3",
                  spec_hash=None, summary="主脑转达；无子代理报告（叶子会话）", extra=""):
    lines = ["# " + name + " — 2026-11-19", ""]
    lines.append("角色：" + role)
    lines.append("审查者：" + reviewer)
    lines.append("会话标识：" + session)
    if coding_decl:
        lines.append("未参与编码声明：是（只读）")
    if spec_decl:
        lines.append("未参与 spec 编写声明：是")
    if spec_revision is not None:
        lines.append("spec_revision：" + spec_revision)
    if spec_hash is not None:
        lines.append("spec_hash：" + spec_hash)
    if summary is not None:
        lines.append("汇总来源：" + summary)
    lines.append("结论：" + verdict)
    lines.append("")
    lines.append("## 证据")
    if evidence is None:
        evidence = [
            SPEC_REL + ":10：证据一",
            SPEC_REL + ":20：证据二",
            SPEC_REL + ":30：证据三",
        ]
    for item in evidence:
        lines.append("- " + item)
    if extra:
        lines.append("")
        lines.append(extra)
    return "\n".join(lines) + "\n"


def j1_report(reviewer="referee-j1", verdict="PASS", evidence=None,
              coding_decl=True, spec_decl=True, spec_revision="3",
              spec_hash=None, summary="主脑转达；无子代理报告（叶子会话）", extra=""):
    return review_report(
        "referee-J1",
        "referee",
        reviewer,
        reviewer + " / " + DATE,
        verdict=verdict,
        evidence=evidence,
        coding_decl=coding_decl,
        spec_decl=spec_decl,
        spec_revision=spec_revision,
        spec_hash=spec_hash,
        summary=summary,
        extra=extra,
    )


def standard_reviews(*, coding_decl=True, spec_decl=True, referee="referee-j1",
                     security="security-1", auditor="auditor-1", verdict="PASS",
                     spec_revision="3"):
    summary = "；".join("docs/reviews/" + DATE + "-" + name + ".md" for name in (
        "referee-J1", "referee-J3", "referee-J4", "security", "auditor"))
    return {
        "referee-J1": review_report("referee-J1", "referee", referee, referee + " / " + DATE,
                                    verdict=verdict, coding_decl=coding_decl, spec_decl=spec_decl, summary=summary,
                                    spec_revision=spec_revision),
        "referee-J3": review_report("referee-J3", "referee", referee, referee + " / " + DATE,
                                    verdict=verdict, coding_decl=coding_decl, spec_decl=spec_decl, summary=summary,
                                    spec_revision=spec_revision),
        "referee-J4": review_report("referee-J4", "referee", referee, referee + " / " + DATE,
                                    verdict=verdict, coding_decl=coding_decl, spec_decl=spec_decl, summary=summary,
                                    spec_revision=spec_revision),
        "security": review_report("security", "security", security, security + " / " + DATE,
                                  verdict=verdict, coding_decl=coding_decl, spec_decl=spec_decl, summary=summary,
                                  spec_revision=spec_revision),
        "auditor": review_report("auditor", "auditor", auditor, auditor + " / " + DATE,
                                 verdict=verdict, coding_decl=coding_decl, spec_decl=spec_decl, summary=summary,
                                 spec_revision=spec_revision),
    }


def write_reviews(root: Path, reports, spec_rel: str = SPEC_REL) -> None:
    """写审查报告；缺 spec_hash 时按当前 spec 正文 SHA-256 自动补齐（C5）。

    C12：汇总来源只保留本次实际写出的报告路径，避免 fixture 列出未生成的报告。
    """
    hash_value = spec_body_hash(root, spec_rel)
    existing = {DATE + "-" + name + ".md" for name in reports}
    for name, text in reports.items():
        if "spec_hash：" not in text and "spec_hash:" not in text:
            text = re.sub(
                r"(?m)^(spec_revision[：:].*)$",
                lambda match: match.group(1) + "\nspec_hash：" + hash_value,
                text,
                count=1,
            )
        def clean_summary(match):
            tokens = re.split(r"([、,，;；\s]+)", match.group(1))
            kept = [token for token in tokens
                    if not token.endswith(".md") or token.split("/")[-1] in existing]
            return "汇总来源：" + "".join(kept)
        text = re.sub(r"(?m)^汇总来源：(.*)$", clean_summary, text)
        write_text(root / "docs" / "reviews" / (DATE + "-" + name + ".md"), text)


def signed_spec_text() -> str:
    with temp_repo() as root:
        return sign_spec(root)


def sign_spec_text_with_scope(scope: str) -> str:
    with temp_repo() as root:
        return sign_spec(root, hash_scope=scope)


def _build_accept_fixture(root: Path) -> dict:
    init_git(root)
    write_text(root / "README.md", "# fixture\n")
    base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
    sign_spec(root, acceptance_checked=True)
    git_commit(root, "docs(spec): sign", "2026-11-19T10:01:00+0800")
    write_case_and_report(root)
    c0 = git_commit(root, "test: fixture", "2026-11-19T10:02:00+0800")
    front = accept_front(c0)
    sign_spec(root, acceptance_checked=True, front=front)
    git_commit(root, "docs(spec): accept", "2026-11-19T10:03:00+0800")
    return {"base": base, "c0": c0}


def make_accept_fixture(root: Path, *, commit_accept=True, front_overrides=None):
    """C9 批量 fixture：整段历史只构建一次，之后复制（不再逐用例起 git）。"""
    meta = cached_repo("accept", _build_accept_fixture, root)
    if not commit_accept:
        sign_spec(root, acceptance_checked=True, front=accept_front(meta["c0"]))
    return meta["base"], meta["c0"]


def write_v472_patrol(root: Path, **overrides) -> None:
    """v4.7.2 C8/C12/C13 patrol：顶层 JSON 字段（reviewer_dispatch/role_dispatch/last_active_at/汇总来源）。"""
    role_dispatch = {
        "dev": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
        "tester": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
        "security": {"dispatch_at": iso_at(9, 20), "source": "new_missing", "reason": "无在岗 security"},
        "referee": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
        "auditor": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
    }
    summary_roles = {
        "dev": "docs/reviews/2026-11-19-dev.md",
        "tester": "docs/reviews/2026-11-19-tester.md",
        "security": "docs/reviews/2026-11-19-security.md",
        "referee": "docs/reviews/2026-11-19-referee-J1.md",
        "auditor": "docs/reviews/2026-11-19-auditor.md",
    }
    values = {
        "started_at": iso_at(9, 20),
        "first_round": iso_at(9, 21),
        "rounds": 3,
        "reviewer": "auditor-1",
        "reviewer_dispatch": "step1 派发；step2 返回；step3 检查点",
        "reviewer_dispatch_at": iso_at(9, 19),
        "heartbeat_effective_at": iso_at(9, 19),
        "role_dispatch": role_dispatch,
        "last_active_list": [iso_at(10, 0), iso_at(10, 1), iso_at(10, 2),
                              iso_at(10, 3), iso_at(10, 4), iso_at(10, 5)],
        "summary_roles": summary_roles,
    }
    values.update(overrides)
    first = values["first_round"]
    write_text(root / PATROL_REL, patrol_text(**values))
    set_mtime(root / PATROL_REL, first)


def set_round_times(root: Path, stamps) -> None:
    """按顺序改写 patrol 的 `## 第 N 轮 — <时间>` 标题时间（用于 C12 轮次间隔用例）。"""
    text = read_text(root / PATROL_REL)
    counter = [0]
    def replace(match):
        index = counter[0]
        counter[0] += 1
        if index >= len(stamps):
            return match.group(0)
        return "## 第 %s 轮 — %s" % (match.group(1), stamps[index])
    text = re.sub(r"(?m)^## 第 (\d+) 轮 — .*$", replace, text)
    write_text(root / PATROL_REL, text)

def _build_v472_fixture(root: Path) -> dict:
    init_git(root)
    write_text(root / "README.md", "# fixture\n")
    git_commit(root, "init", "2026-11-19T09:00:00+0800")
    sign_spec(root, rel=SPEC_REL_472, front={"spec_revision": "1"}, hash_scope="sections_1_8")
    git_commit(root, "docs(spec): sign", "2026-11-19T09:10:00+0800")
    write_case_and_report(root)
    write_start_artifacts(root, spec_rel=SPEC_REL_472, spec_revision="1")
    write_first_write(root, iso_at(9, 30))
    commit_file(root, "ship-it/scripts/impl.py", "VALUE = 1\n", "2026-11-19T10:00:00+08:00")
    write_failure_log(root, rows=None)
    write_text(root / "docs" / "reviews" / (DATE + "-dev.md"), "# dev report\n")
    write_text(root / "docs" / "reviews" / (DATE + "-tester.md"), "# tester report\n")
    write_reviews(root, standard_reviews(spec_revision="1"), spec_rel=SPEC_REL_472)
    write_v472_patrol(root)
    return {}


def make_v472_fixture(root: Path) -> None:
    cached_repo("v472", _build_v472_fixture, root)

def extract_section(text: str, number: int) -> str:
    pattern = re.compile(r"^##\s*" + str(number) + r"(?![0-9])\s*[.、]?\s*.*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    rest = text[match.end():]
    nxt = re.search(r"^##\s*\d+(?![0-9])\s*[.、]?\s*.*$", rest, re.MULTILINE)
    if nxt:
        return rest[:nxt.start()]
    return rest


def parse_frontmatter(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def parse_hard_words(rule_text: str):
    begin = re.search(r"<!--\s*BEGIN:hard-forbidden\s*-->", rule_text)
    end = re.search(r"<!--\s*END:hard-forbidden\s*-->", rule_text)
    if not begin or not end or end.start() <= begin.end():
        return []
    block = rule_text[begin.end():end.start()]
    words = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        for part in re.split(r"[\s,，、|/]+", stripped):
            word = part.strip().strip(TICK).strip()
            if not word or not re.search(r"[\u4e00-\u9fff]", word):
                continue
            if len(word) > 8 or re.search(r"[\s\\|<>=\"]", word):
                continue
            if word not in words:
                words.append(word)
    return words


# ---------------------------------------------------------------------------
# C14–C18 闸门 fixture（start artifact / patrol / pause / failure log / check_docs）
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sections_1_8_hash(text: str) -> str:
    """C1/A19：sign_hash = §§1–8 SHA-256（## 1. 行到 ## 9. 行前一行，\n 连接，无尾随换行）。"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    start = None
    end = None
    for index, line in enumerate(lines):
        if start is None and line.startswith("## 1."):
            start = index
        elif start is not None and line.startswith("## 9."):
            end = index
            break
    if start is None or end is None:
        raise AssertionError("spec 缺少 ## 1. 或 ## 9. 节，无法计算 §§1–8 hash")
    return hashlib.sha256("\n".join(lines[start:end]).encode("utf-8")).hexdigest()


def spec_body_hash(root: Path, rel: str = SPEC_REL) -> str:
    return sections_1_8_hash(read_text(root / rel))


def insert_before_section(text: str, number: int, extra: str) -> str:
    """在 ## <number>. 节前插入一行，用于修改 §§1–8（sign_hash 覆盖区）。"""
    marker = "\n## %d." % number
    index = text.find(marker)
    if index < 0:
        raise AssertionError("spec 缺少第 %d 节标题" % number)
    return text[:index] + "\n" + extra.rstrip("\n") + text[index:]


def iso_at(hour: int, minute: int = 0, second: int = 0) -> str:
    return "2026-11-19T%02d:%02d:%02d+08:00" % (hour, minute, second)


def set_mtime(path: Path, stamp: str) -> None:
    seconds = datetime.datetime.fromisoformat(stamp).timestamp()
    os.utime(str(path), (seconds, seconds))


def git_stamp(stamp: str) -> str:
    return stamp.replace("+08:00", "+0800")


def commit_file(root: Path, rel: str, text: str, stamp: str, message: str = "feat: impl") -> str:
    write_text(root / rel, text)
    commit = git_commit(root, message, git_stamp(stamp))
    set_mtime(root / rel, stamp)
    return commit


def write_first_write(root: Path, at: str, path: str = "ship-it/scripts/impl.py", extra=None) -> None:
    """C6：首个写任务前落 tmp/first-write.json（first_write_at/path）。"""
    data = {"first_write_at": at, "path": path}
    if extra:
        data.update(extra)
    write_text(root / "tmp" / "first-write.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def remove_first_write(root: Path) -> None:
    path = root / "tmp" / "first-write.json"
    if path.exists():
        path.unlink()


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def full_body_hash(text: str) -> str:
    """C8：front matter 结束后的全文（含 §9），CRLF→LF。"""
    normalized = normalize_newlines(text)
    lines = normalized.split("\n")
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return hashlib.sha256("\n".join(lines[index + 1:]).encode("utf-8")).hexdigest()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_a_marks(text: str) -> str:
    """C8：只归一化行首列表项 `- [x] A<n>` → `- [ ] A<n>`（不动正文/表格）。"""
    return re.sub(r"(?m)^(\s*[-*+]\s+\[)[xX](\]\s+\*{0,2}A\d+\b)", r"\1 \2", text)


def signing_hash_for_scope(text: str, scope: str) -> str:
    if scope == "full_body":
        return full_body_hash(text)
    if scope == "sections_1_8":
        return sections_1_8_hash(text)
    if scope == "sections_1_8_a_normalized":
        return sections_1_8_hash(normalize_a_marks(text))
    raise AssertionError("未知 hash_scope：" + scope)


def spec_scope(text: str) -> str:
    return parse_frontmatter(text).get("hash_scope", "").strip()


def spec_hash_with_scope(text: str) -> str:
    scope = spec_scope(text)
    if not scope:
        raise AssertionError("fixture spec 必须显式写 hash_scope")
    return signing_hash_for_scope(text, scope)


def write_snapshot(root: Path, rev: int, *, scope: str = "sections_1_8", source_rel: str = SPEC_REL) -> str:
    """C7：把当前 spec 快照到 tmp/spec-before-<rev>.md，并返回其签名 hash。"""
    text = read_text(root / source_rel)
    if spec_scope(text) != scope:
        text = set_hash_scope(text, scope)
    write_text(root / "tmp" / ("spec-before-%d.md" % rev), text)
    return signing_hash_for_scope(text, scope)


def set_hash_scope(text: str, scope: str) -> str:
    """在 front matter 的 spec_revision 后插入 hash_scope（不改变 §§1–8 正文）。"""
    if spec_scope(text) == scope:
        return text
    lines = normalize_newlines(text).split("\n")
    for index, line in enumerate(lines):
        if line.startswith("spec_revision:"):
            lines.insert(index + 1, "hash_scope: " + scope)
            return "\n".join(lines)
    raise AssertionError("spec 缺少 spec_revision 行")


def history_repo(root: Path, steps) -> list:
    """C9 批量 fixture：steps=[(message, when, {rel: text})]，一次 fast-import 建全史。"""
    files = {}
    commits = []
    for message, when, changes in steps:
        files.update(changes)
        commits.append({"message": message, "when": when, "files": dict(files)})
    return build_history(root, commits)


def start_rel(role: str) -> str:
    return "docs/reviews/" + DATE + "-" + role + "-start.md"


def start_artifact_text(role, reviewer, session, started_at, spec_revision, spec_hash) -> str:
    return "\n".join([
        "# 2026-11-19 " + role + " start artifact",
        "",
        "角色：" + role,
        "审查者：" + reviewer,
        "会话标识：" + session,
        "启动时间：" + started_at,
        "spec_revision：" + spec_revision,
        "spec_hash：" + spec_hash,
        "未参与编码声明：是（只读）",
        "未参与 spec 编写声明：是",
        "",
        "## 证据",
        "- " + SPEC_REL + ":3：spec_revision " + spec_revision,
        "- 命令 check_spec.py --print-sign-hash 退出码 0",
        "- " + SPEC_REL + ":10：sign_hash",
        "",
    ])


def write_start_artifacts(root: Path, *, started_at=None, spec_rel: str = SPEC_REL,
                          overrides=None, spec_revision: str = "3") -> None:
    started = started_at or iso_at(9, 20)
    hash_value = spec_body_hash(root, spec_rel)
    overrides = overrides or {}
    for role, reviewer in START_ROLES:
        text = start_artifact_text(role, reviewer, reviewer + " / " + DATE, started, spec_revision, hash_value)
        if role in overrides:
            text = overrides[role](text)
        rel = start_rel(role)
        write_text(root / rel, text)
        set_mtime(root / rel, started)


def patrol_text(*, started_at=None, first_round=None, rounds=3, round_gap_minutes=1,
                interval="60 秒（1 分钟，定时巡检）", triggers=True, evidence=True,
                conclusion="PASS", reviewer="auditor-1", session=None,
                last_active_at=None, reviewer_dispatch=None, reviewer_dispatch_at=None,
                role_dispatch=None, last_active_list=None, summary_roles=None,
                reviewer_pause=None, reviewer_resume=None, heartbeat_effective_at=None) -> str:
    started = started_at or iso_at(9, 20)
    first = first_round or iso_at(9, 21)
    base = datetime.datetime.fromisoformat(first)
    lines = [
        "# 2026-11-19 审查员巡检记录（C14）",
        "",
        "- 启动时间：" + started,
        "- 巡检间隔：" + interval,
        "- 轮次：" + str(rounds),
        "- 审查者：" + (reviewer or "auditor-1"),
        "- 会话标识：" + (session or ((reviewer or "auditor-1") + " / " + DATE)),
    ]
    if reviewer_dispatch is not None:
        lines.append("- reviewer_dispatch：" + reviewer_dispatch)
    if reviewer_dispatch_at is not None:
        lines.append("- reviewer_dispatch_at：" + reviewer_dispatch_at)
    if heartbeat_effective_at is not None:
        lines.append("- heartbeat_effective_at：" + heartbeat_effective_at)
    if role_dispatch is not None:
        lines.append("- role_dispatch：" + json.dumps(role_dispatch, ensure_ascii=False, sort_keys=True))
    if last_active_list is not None:
        lines.append("- last_active_at：" + json.dumps(last_active_list, ensure_ascii=False))
    if summary_roles is not None:
        lines.append("- 汇总来源：" + json.dumps(summary_roles, ensure_ascii=False, sort_keys=True))
    if reviewer_pause is not None:
        lines.append("- reviewer_pause：" + json.dumps(reviewer_pause, ensure_ascii=False))
    if reviewer_resume is not None:
        lines.append("- reviewer_resume：" + json.dumps(reviewer_resume, ensure_ascii=False))
    lines.append("")
    for index in range(rounds):
        stamp = (base + datetime.timedelta(minutes=index * round_gap_minutes)).isoformat()
        lines.append("## 第 %d 轮 — %s" % (index + 1, stamp))
        if triggers:
            lines.append("- trigger：" + ("派发" if index == 0 else "检查点"))
        lines.append("- 成员/状态：lead running；新派发 = 0")
        if evidence:
            lines.append("- 证据：git status --porcelain 退出码 0；" + SPEC_REL + ":3 spec_revision 3")
        lines.append("- 异常：无")
        lines.append("- 动作：继续检查")
        if index == rounds - 1:
            active = last_active_at or (base + datetime.timedelta(minutes=(rounds - 1) * round_gap_minutes)).isoformat()
            lines.append("- last_active_at：" + active)
        lines.append("")
    lines.append("## 结论")
    lines.append(conclusion)
    return "\n".join(lines) + "\n"


def set_last_active(root: Path, stamp: str) -> None:
    text = read_text(root / PATROL_REL)
    text = re.sub(r"(?m)^- last_active_at：.*$", "- last_active_at：" + stamp, text)
    write_text(root / PATROL_REL, text)


def remove_last_active(root: Path) -> None:
    path = root / PATROL_REL
    lines = [line for line in read_text(path).splitlines() if not line.startswith("- last_active_at：")]
    write_text(path, "\n".join(lines) + "\n")


def set_report_summary(root: Path, filename: str, value: str) -> None:
    path = root / "docs" / "reviews" / filename
    text = read_text(path)
    if re.search(r"(?m)^汇总来源：.*$", text):
        text = re.sub(r"(?m)^汇总来源：.*$", "汇总来源：" + value, text)
    else:
        text = text.replace("结论：", "汇总来源：" + value + "\n结论：", 1)
    write_text(path, text)

def write_patrol(root: Path, **kwargs) -> None:
    first = kwargs.get("first_round") or iso_at(9, 21)
    write_text(root / PATROL_REL, patrol_text(**kwargs))
    set_mtime(root / PATROL_REL, first)


def pause_text(*, paused_at=None, spec_before_revision=None, spec_before_hash=None,
               spec_before_snapshot=None) -> str:
    stamp = paused_at or iso_at(10, 0)
    lines = [
        "# 2026-11-19 暂停记录（C16/C7）",
        "",
        "- 暂停时间：" + stamp,
        "- 触发原话：用户要求修改已签约契约。",
    ]
    if spec_before_revision is not None:
        lines.append("- spec_before_revision：" + str(spec_before_revision))
    if spec_before_hash is not None:
        lines.append("- spec_before_hash：" + spec_before_hash)
    if spec_before_snapshot is not None:
        lines.append("- spec_before_snapshot：" + spec_before_snapshot)
    lines.extend([
        "- 活跃成员：dev-scripts inactive；tester inactive；auditor inactive。",
        "",
        "## 结束指令清单",
        "| 目标 | 时间 | 指令 | 确认 |",
        "|---|---|---|---|",
        "| dev-scripts | 10:00 | 停止读写 | 10:01 确认 |",
        "| tester | 10:00 | 停止测试 | 10:01 确认 |",
        "",
        "- 新派发=0：确认（暂停后无新 subagent）",
        "- 旧契约停止：是；HEAD 未变，无新代码/提交。",
        "- 产出保留：工作区文件与报告保留。",
        "- 未停住项：无。",
        "- 恢复条件：用户重新发送严格“签约”，check_spec --stage spec 退出码 0。",
        "",
        "## 结论",
        "已暂停，新派发=0。",
        "",
    ])
    return "\n".join(lines)


def write_pause(root: Path, *, paused_at=None, spec_at=None, spec_before_revision=None,
                spec_before_hash=None, spec_before_snapshot=None) -> None:
    stamp = paused_at or iso_at(10, 0)
    write_text(root / PAUSE_REL, pause_text(
        paused_at=stamp,
        spec_before_revision=spec_before_revision,
        spec_before_hash=spec_before_hash,
        spec_before_snapshot=spec_before_snapshot,
    ))
    set_mtime(root / PAUSE_REL, stamp)
    if spec_at:
        set_mtime(root / SPEC_REL, spec_at)


def pause_with_snapshot(root: Path, *, rev: int = 3, paused_at=None, spec_at=None,
                        scope: str = "sections_1_8") -> None:
    """C7 合规 pause：先快照当前 spec，再写 pause.md（含 spec_before_* 三字段）。"""
    hash_value = write_snapshot(root, rev, scope=scope)
    write_pause(
        root,
        paused_at=paused_at,
        spec_at=spec_at,
        spec_before_revision=rev,
        spec_before_hash=hash_value,
        spec_before_snapshot="tmp/spec-before-%d.md" % rev,
    )


def failure_row(task="测试", subagent="tester-a", failure_class="execution_failed", attempt=1,
                evidence="无收尾消息", action="重试", conclusion="继续") -> str:
    return "\n".join([
        "- task：" + task,
        "- subagent：" + subagent,
        "- failure_class：" + failure_class,
        "- attempt：" + str(attempt),
        "- 证据：" + evidence,
        "- 动作：" + action,
        "- 结论：" + conclusion,
    ])


def failure_log_text(rows=None) -> str:
    lines = ["# 2026-11-19 failure log（C17）", ""]
    if rows is None:
        lines.append("无失败。")
    else:
        lines.append("\n\n".join(rows))
    lines.append("")
    return "\n".join(lines) + "\n"


def write_failure_log(root: Path, rows=None) -> None:
    write_text(root / FAILURE_REL, failure_log_text(rows))


def write_gate_evidence(root: Path, *, started_at=None, first_round=None, rounds=3,
                        failure_rows=None, spec_rel: str = SPEC_REL,
                        last_active_at=None, spec_revision: str = "3") -> None:
    write_start_artifacts(root, started_at=started_at, spec_rel=spec_rel,
                          spec_revision=spec_revision)
    write_patrol(root, started_at=started_at, first_round=first_round, rounds=rounds,
                 last_active_at=last_active_at)
    write_failure_log(root, rows=failure_rows)


def run_docs(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return run_py(CHECK_DOCS, ["--root", "."] + list(extra), cwd=root)


def build_full_spec() -> str:
    clauses = "\n\n".join(
        "### C%d 测试条款%d\n\n- **前置**：无。\n- **后置**：通过。\n- **失败**：失败。\n- **不变式**：不变。" % (n, n)
        for n in range(1, 19)
    )
    acceptance = "\n".join("- [x] A%d 测试验收%d。" % (n, n) for n in range(1, 19))
    return build_spec(clauses=clauses, acceptance=acceptance, acceptance_checked=True)


def _build_start_history(root: Path, write_impl: bool, impl_at: str,
                         spec_revision: str, hash_scope) -> dict:
    init_git(root)
    write_text(root / "README.md", "# fixture\n")
    git_commit(root, "init", "2026-11-19T09:00:00+0800")
    sign_spec(root, front={"spec_revision": spec_revision}, hash_scope=hash_scope)
    git_commit(root, "docs(spec): sign", "2026-11-19T09:10:00+0800")
    if write_impl:
        commit_file(root, "ship-it/scripts/impl.py", "VALUE = 1\n", impl_at)
    return {}


def make_start_fixture(root: Path, *, impl_at=None, start_at=None, first_round=None,
                       patrol_kwargs=None, write_impl=True, first_write_at=None,
                       spec_revision: str = "3", hash_scope=None) -> None:
    """C14/C6 fixture：历史批量构建 + 每用例写 start/patrol/first-write 元数据。"""
    moment = impl_at or "2026-11-19T10:00:00+08:00"
    key = "start-%d-%s-%s-%s" % (1 if write_impl else 0, moment, spec_revision, hash_scope or "-")
    cached_repo(key, lambda path: _build_start_history(path, write_impl, moment, spec_revision, hash_scope), root)
    started = start_at or iso_at(9, 20)
    first = first_round or iso_at(9, 21)
    marker = first_write_at or iso_at(9, 30)
    active = (datetime.datetime.fromisoformat(marker) - datetime.timedelta(minutes=1)).isoformat()
    write_start_artifacts(root, started_at=started, spec_revision=spec_revision)
    patrol_args = dict(patrol_kwargs or {})
    patrol_args.setdefault("last_active_at", active)
    write_patrol(root, started_at=started, first_round=first, **patrol_args)
    write_first_write(root, marker)


def _build_verified_fixture(root: Path, spec_revision: str, hash_scope) -> dict:
    init_git(root)
    write_text(root / "README.md", "# fixture\n")
    git_commit(root, "init", "2026-11-19T09:00:00+0800")
    sign_spec(root, front={"spec_revision": spec_revision}, hash_scope=hash_scope)
    git_commit(root, "docs(spec): sign", "2026-11-19T09:10:00+0800")
    write_case_and_report(root)
    write_gate_evidence(root, started_at=iso_at(9, 20), first_round=iso_at(9, 21),
                        last_active_at=iso_at(10, 5), spec_revision=spec_revision)
    write_first_write(root, iso_at(9, 30))
    commit_file(root, "ship-it/scripts/impl.py", "VALUE = 1\n", "2026-11-19T10:00:00+08:00")
    write_reviews(root, standard_reviews(spec_revision=spec_revision))
    return {}


def make_verified_fixture(root: Path, *, spec_revision: str = "3", hash_scope=None) -> None:
    cached_repo("verified-%s-%s" % (spec_revision, hash_scope or "-"),
                lambda path: _build_verified_fixture(path, spec_revision, hash_scope), root)


class ProcessGatesContractTest(unittest.TestCase):
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

    def test_c1_sign_exact_word(self) -> None:
        with temp_repo() as root:
            sign_spec(root)
            self.assert_pass(run_spec(root, "spec"), "严格“签约”应 PASS")

        variants = ["签约，这次就用新的契约来做", "签约。", "“签约”", "继续", "签约，按这个做", "我签约"]
        with temp_repo() as root:
            for quote in variants:
                with self.subTest(sign_quote=quote):
                    sign_spec(root, front={"sign_quote": quote})
                    self.assert_fail(run_spec(root, "spec"), "sign_quote 非严格“签约”应 FAIL：" + quote)

        keywords = [
            "刚才的说明可能造成误解",
            "是否要签约",
            "发送",
            "签约",
            "两个字",
            "不会开始编码",
            "不要加标点、引号或其他内容",
        ]
        with temp_repo() as root:
            for keyword in keywords:
                with self.subTest(missing_keyword=keyword):
                    prompt = SIGN_PROMPT.replace(keyword, "")
                    sign_spec(root, front={"sign_prompt": prompt})
                    self.assert_fail(run_spec(root, "spec"), "sign_prompt 缺关键词应 FAIL：" + keyword)

        with temp_repo() as root:
            sign_spec(root)
            spec_path = root / SPEC_REL
            write_text(spec_path, insert_before_section(read_text(spec_path), 6, "- **修订**：新增一行。"))
            self.assert_fail(run_spec(root, "spec"), "§§1–8 正文变更后 sign_hash 不匹配应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec(front=draft_front()))
            self.assert_fail(run_spec(root, "spec"), "未签约（draft）应 FAIL")

    @unittest.skipUnless(GIT, "需要 git 命令")
    @slow
    def test_c2_accept_exact_word(self) -> None:
        with temp_repo() as root:
            base, c0 = make_accept_fixture(root)
            self.assert_pass(run_spec(root, "accept", "--git-check", "--base", base), "严格“验收”应 PASS")

        with temp_repo() as root:
            make_accept_fixture(root)
            self.assert_pass(
                run_spec(root, "accept", "--git-check"),
                "accept --git-check 不带 --base 应 PASS（C3 只校验 accept_commit..HEAD）",
            )

        variants = ["没问题", "验收，可以发", "验收。", "“验收”", "我验收", "继续"]
        with temp_repo() as root:
            base, c0 = make_accept_fixture(root)
            for quote in variants:
                with self.subTest(accept_quote=quote):
                    sign_spec(root, acceptance_checked=True, front=accept_front(c0, accept_quote=quote))
                    self.assert_fail(run_spec(root, "accept"), "accept_quote 非严格“验收”应 FAIL：" + quote)

        with temp_repo() as root:
            base, c0 = make_accept_fixture(root)
            sign_spec(root, acceptance_checked=True, front=accept_front(c0, accept_commit=""))
            self.assert_fail(run_spec(root, "accept"), "accept_commit 缺失应 FAIL")

        with temp_repo() as root:
            base, c0 = make_accept_fixture(root)
            self.assert_pass(run_spec(root, "accept", "--git-check", "--base", base), "验收后无代码变更应 PASS")
            write_text(root / "ship-it" / "scripts" / "impl.py", "VALUE = 1\n")
            git_commit(root, "feat: code after accept", "2026-11-19T10:04:00+0800")
            self.assert_fail(run_spec(root, "accept", "--git-check", "--base", base), "验收后代码变更应 FAIL")

    @unittest.skipUnless(GIT, "需要 git 命令")
    def test_c3_sign_accept_block(self) -> None:
        with temp_repo() as root:
            sign_spec(root)
            self.assert_pass(run_spec(root, "spec"), "完整签约块应 PASS")
            for key in ("sign_prompt", "sign_requested_at", "signed_by", "signed_at", "confirmed_clauses"):
                with self.subTest(empty_field=key):
                    sign_spec(root, front={key: ""})
                    self.assert_fail(run_spec(root, "spec"), "签约块字段为空应 FAIL：" + key)
            text = sign_spec(root)
            text = re.sub(r"^signed_by:.*\n", "", text, flags=re.MULTILINE)
            write_text(root / SPEC_REL, text)
            self.assert_fail(run_spec(root, "spec"), "签约块缺字段应 FAIL：signed_by")
            sign_spec(root, front={"confirmed_clauses": "C1"})
            self.assert_fail(run_spec(root, "spec"), "confirmed_clauses 未覆盖 C2 应 FAIL")
            sign_spec(root, front={"sign_hash": ""})
            self.assert_fail(run_spec(root, "spec"), "sign_hash 为空应 FAIL")
            sign_spec(root, front={"sign_quote": ""})
            self.assert_fail(run_spec(root, "spec"), "sign_quote 为空应 FAIL")

        with temp_repo() as root:
            write_case_and_report(root)
            sign_spec(root)
            self.assert_pass(run_spec(root, "verify"), "verify 基线应 PASS")
            sign_spec(root, front={"sign_quote": ""})
            self.assert_fail(run_spec(root, "verify"), "verify 阶段必须复校验签约块")

        with temp_repo() as root:
            base, c0 = make_accept_fixture(root)
            self.assert_pass(run_spec(root, "accept"), "完整验收块应 PASS")
            for key in ("accept_prompt", "accept_requested_at", "accepted_by", "accepted_at", "accepted_items"):
                with self.subTest(empty_field=key):
                    sign_spec(root, acceptance_checked=True, front=accept_front(c0, **{key: ""}))
                    self.assert_fail(run_spec(root, "accept"), "验收块字段为空应 FAIL：" + key)
            accept_keywords = [
                "刚才的说明可能造成误解",
                "是否需要验收",
                "发送",
                "验收",
                "两个字",
                "不会进入 PR",
                "不要加标点、引号或其他内容",
            ]
            for keyword in accept_keywords:
                with self.subTest(missing_keyword=keyword):
                    prompt = ACCEPT_PROMPT.replace(keyword, "")
                    sign_spec(root, acceptance_checked=True, front=accept_front(c0, accept_prompt=prompt))
                    self.assert_fail(run_spec(root, "accept"), "accept_prompt 缺关键词应 FAIL：" + keyword)
            sign_spec(root, acceptance_checked=True, front=accept_front(c0, accepted_items="A1"))
            self.assert_fail(run_spec(root, "accept"), "accepted_items 未覆盖 A2 应 FAIL")
            sign_spec(root, acceptance_checked=True, front=accept_front(c0, accept_commit=""))
            self.assert_fail(run_spec(root, "accept"), "accept_commit 为空应 FAIL")

    @unittest.skipUnless(GIT, "需要 git 命令")
    @slow
    def test_c4_git_check_spec_first(self) -> None:
        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            sign_spec(root)
            git_commit(root, "docs(spec): sign", "2026-11-19T10:01:00+0800")
            write_text(root / "ship-it" / "scripts" / "impl.py", "VALUE = 1\n")
            git_commit(root, "feat: impl", "2026-11-19T10:02:00+0800")
            self.assert_pass(run_spec(root, "spec", "--git-check", "--base", base), "spec 先于实现应 PASS")

        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            sign_spec(root)
            write_text(root / "ship-it" / "scripts" / "impl.py", "VALUE = 1\n")
            git_commit(root, "spec + impl", "2026-11-19T10:01:00+0800")
            self.assert_fail(run_spec(root, "spec", "--git-check", "--base", base), "spec 与实现同提交应 FAIL")

        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            write_text(root / "ship-it" / "scripts" / "impl.py", "VALUE = 1\n")
            git_commit(root, "feat: impl first", "2026-11-19T10:01:00+0800")
            sign_spec(root)
            git_commit(root, "docs(spec): sign", "2026-11-19T10:02:00+0800")
            self.assert_fail(run_spec(root, "spec", "--git-check", "--base", base), "实现先于 spec 应 FAIL")

        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            write_text(root / SPEC_REL, build_spec(front=draft_front()))
            git_commit(root, "docs(spec): draft", "2026-11-19T10:01:00+0800")
            sign_spec(root)
            git_commit(root, "docs(spec): sign", "2026-11-19T10:02:00+0800")
            self.assert_fail(run_spec(root, "spec", "--git-check", "--base", base), "spec 首次提交为 draft 应 FAIL")

        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            sign_spec(root)
            git_commit(root, "docs(spec): sign", "2026-11-19T10:01:00+0800")
            self.assert_fail(run_spec(root, "spec", "--git-check"), "--git-check 未提供 --base 应 FAIL")

        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            sign_spec(root)
            self.assert_fail(run_spec(root, "spec", "--git-check", "--base", base), "spec 未提交应 FAIL")

        # C4/A4：.md 不是天然非实现文件（SKILL/README/模板/team-mode 均为实现文件）
        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            sign_spec(root)
            write_text(root / "ship-it" / "SKILL.md", "# skill\n")
            git_commit(root, "spec + skill.md", "2026-11-19T10:01:00+0800")
            self.assert_fail(run_spec(root, "spec", "--git-check", "--base", base), "spec 与 .md 实现文件同提交应 FAIL")

        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            write_text(root / "ship-it" / "SKILL.md", "# skill\n")
            git_commit(root, "feat: skill.md first", "2026-11-19T10:01:00+0800")
            sign_spec(root)
            git_commit(root, "docs(spec): sign", "2026-11-19T10:02:00+0800")
            self.assert_fail(run_spec(root, "spec", "--git-check", "--base", base), ".md 实现文件早于 spec 应 FAIL")

        # C4/A4：spec 修订必须产生新的 docs-only signed 提交；实现不得早于最新 signed spec 提交
        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            sign_spec(root)
            git_commit(root, "docs(spec): sign rev1", "2026-11-19T10:01:00+0800")
            commit_file(root, "ship-it/scripts/impl.py", "VALUE = 1\n", "2026-11-19T10:02:00+08:00")
            sign_spec(root, section2_extra="- **修订 2**：新增一行。\n")
            git_commit(root, "docs(spec): sign rev2", "2026-11-19T10:03:00+0800")
            self.assert_fail(
                run_spec(root, "spec", "--git-check", "--base", base),
                "实现提交早于最新 signed spec 提交应 FAIL",
            )

        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            sign_spec(root)
            git_commit(root, "docs(spec): sign rev1", "2026-11-19T10:01:00+0800")
            sign_spec(root, section2_extra="- **修订 2**：新增一行。\n")
            git_commit(root, "docs(spec): sign rev2", "2026-11-19T10:02:00+0800")
            commit_file(root, "ship-it/scripts/impl.py", "VALUE = 1\n", "2026-11-19T10:03:00+08:00")
            self.assert_pass(
                run_spec(root, "spec", "--git-check", "--base", base),
                "实现晚于最新 signed spec 提交应 PASS",
            )

        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            sign_spec(root)
            git_commit(root, "docs(spec): sign rev1", "2026-11-19T10:01:00+0800")
            write_text(root / SPEC_REL, build_spec(front=draft_front()))
            git_commit(root, "docs(spec): revision draft", "2026-11-19T10:02:00+0800")
            self.assert_fail(
                run_spec(root, "spec", "--git-check", "--base", base),
                "最新 docs-only 提交未 signed 应 FAIL",
            )

        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            base = git_commit(root, "init", "2026-11-19T10:00:00+0800")
            sign_spec(root)
            git_commit(root, "docs(spec): sign rev1", "2026-11-19T10:01:00+0800")
            spec_path = root / SPEC_REL
            write_text(spec_path, insert_before_section(read_text(spec_path), 6, "- **修订**：追加正文但复用旧 sign_hash。"))
            git_commit(root, "docs(spec): revision old hash", "2026-11-19T10:02:00+0800")
            self.assert_fail(
                run_spec(root, "spec", "--git-check", "--base", base),
                "spec 修订后仍用旧 sign_hash 应 FAIL",
            )

    def test_c5_roles_gate(self) -> None:
        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report()})
            self.assert_pass(run_roles(root, "sign"), "sign 仅 J1 应 PASS")

        with temp_repo() as root:
            self.assert_fail(run_roles(root, "sign"), "sign 缺 J1 应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            reports = standard_reviews()
            del reports["referee-J3"]
            write_reviews(root, reports)
            self.assert_fail(run_roles(root, "verify"), "verify 缺 J3 应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            reports = standard_reviews()
            del reports["referee-J4"]
            write_reviews(root, reports)
            self.assert_fail(run_roles(root, "accept"), "accept 缺 J4 应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            reports = standard_reviews()
            del reports["referee-J4"]
            write_reviews(root, reports)
            write_gate_evidence(root)
            self.assert_pass(run_roles(root, "verify"), "verify 四份齐全 + patrol + failure log 应 PASS")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, standard_reviews())
            write_gate_evidence(root)
            self.assert_pass(run_roles(root, "accept"), "accept 五份齐全 + patrol + failure log 应 PASS")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report(verdict="BLOCK")})
            self.assert_fail(run_roles(root, "sign"), "结论 BLOCK 应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report(verdict="DEVIATION")})
            self.assert_fail(run_roles(root, "sign"), "结论 DEVIATION 应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            reports = standard_reviews()
            reports["security"] = review_report("security", "security", "referee-j1", "referee-j1 / " + DATE)
            write_reviews(root, reports)
            self.assert_fail(run_roles(root, "verify"), "三类角色身份重复应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            evidence = [SPEC_REL + ":10：证据一", SPEC_REL + ":20：证据二"]
            write_reviews(root, {"referee-J1": j1_report(evidence=evidence)})
            self.assert_fail(run_roles(root, "sign"), "证据少于 3 条应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report(coding_decl=False)})
            self.assert_fail(run_roles(root, "sign"), "缺未参与编码声明应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, standard_reviews(spec_decl=False))
            self.assert_fail(run_roles(root, "verify"), "全部报告未声明未参与 spec 编写应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report()})
            self.assert_fail(run_roles(root, "sign", "--reviews-dir", ".."), "reviews-dir 越界应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report(spec_hash="0" * 64)})
            self.assert_fail(run_roles(root, "sign"), "报告 spec_hash 与当前 spec 正文不一致应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report()})
            report_path = root / "docs" / "reviews" / (DATE + "-referee-J1.md")
            write_text(report_path, re.sub(r"(?m)^spec_hash[：:].*\n", "", read_text(report_path)))
            self.assert_fail(run_roles(root, "sign"), "报告缺 spec_hash 应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report(summary=None)})
            self.assert_fail(run_roles(root, "sign"), "报告缺 汇总来源 应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report(summary="")})
            self.assert_fail(run_roles(root, "sign"), "报告 汇总来源 为空应 FAIL")

    def test_c6_reconciliation_truth(self) -> None:
        with temp_repo() as root:
            write_case_and_report(root)
            sign_spec(root, section9_extra="- E2E：13/13\n")
            self.assert_pass(run_spec(root, "verify"), "真实用例/报告应 PASS")

        with temp_repo() as root:
            write_case_and_report(root)
            sign_spec(root, reconciliation=FOUR_COL_RECONCILIATION)
            self.assert_fail(run_spec(root, "verify"), "4 列核销应 FAIL")

        with temp_repo() as root:
            write_case_and_report(root)
            sign_spec(root, reconciliation=recon_5(case1="test_fabricated_zzz"))
            self.assert_fail(run_spec(root, "verify"), "虚构用例名应 FAIL")

        with temp_repo() as root:
            write_case_and_report(root)
            sign_spec(root, reconciliation=recon_5(file1="tests/missing_case_file.py"))
            self.assert_fail(run_spec(root, "verify"), "用例文件不存在应 FAIL")

        with temp_repo() as root:
            write_case_and_report(root)
            sign_spec(root, reconciliation=recon_5(result1="待测"))
            self.assert_fail(run_spec(root, "verify"), "结果非 ✅ 应 FAIL")

        with temp_repo() as root:
            write_case_and_report(root)
            sign_spec(root, reconciliation=recon_5(truth1=""))
            self.assert_fail(run_spec(root, "verify"), "路径真实性为空应 FAIL")

        with temp_repo() as root:
            write_case_and_report(root, report_body="- test_fixture_c1: 已运行\n- test_fixture_c2: 已运行\n- 核销率: 2/2\n- E2E: 13/13\n")
            sign_spec(root, section9_extra="- E2E：13/13\n")
            self.assert_fail(run_spec(root, "verify"), "报告缺 PASS 应 FAIL")

        with temp_repo() as root:
            write_case_and_report(root, report_body="- test_fixture_c1: PASS\n- 核销率: 2/2\n- E2E: 13/13\n")
            sign_spec(root, section9_extra="- E2E：13/13\n")
            self.assert_fail(run_spec(root, "verify"), "报告缺用例名应 FAIL")

        with temp_repo() as root:
            write_case_and_report(root)
            sign_spec(root, footer="- 测试报告：docs/reviews/2026-11-19-missing-report.md", section9_extra="- E2E：13/13\n")
            self.assert_fail(run_spec(root, "verify"), "报告文件不存在应 FAIL")

        with temp_repo() as root:
            write_case_and_report(root, report_body="- test_fixture_c1: PASS\n- test_fixture_c2: PASS\n- 核销率: 2/2\n- E2E: 12/12\n")
            sign_spec(root, section9_extra="- E2E：13/13\n")
            self.assert_fail(run_spec(root, "verify"), "13/13 对 12/12 应 FAIL")

        # C6/A6：报告必须绑定每个测试文件的 hash 与运行窗口
        with temp_repo() as root:
            write_case_and_report(root)
            sign_spec(root)
            report_path = root / REPORT_REL
            write_text(report_path, read_text(report_path).split("## 测试文件证据")[0])
            self.assert_fail(run_spec(root, "verify"), "报告缺测试文件 hash/run window 应 FAIL")

        with temp_repo() as root:
            write_case_and_report(root, evidence_blocks=lambda: evidence_block(root, CASE_REL, pre="0" * 64))
            sign_spec(root)
            self.assert_fail(run_spec(root, "verify"), "pre_sha256 与当前文件不一致应 FAIL")

        with temp_repo() as root:
            write_case_and_report(root, evidence_blocks=lambda: evidence_block(root, CASE_REL, post="0" * 64))
            sign_spec(root)
            self.assert_fail(run_spec(root, "verify"), "post_sha256 与当前文件不一致应 FAIL")

        with temp_repo() as root:
            write_case_and_report(
                root,
                evidence_blocks=lambda: evidence_block(root, CASE_REL, omit=("run_started_at", "run_finished_at")),
            )
            sign_spec(root)
            self.assert_fail(run_spec(root, "verify"), "报告缺运行窗口应 FAIL")

        with temp_repo() as root:
            write_case_and_report(
                root,
                evidence_blocks=lambda: evidence_block(root, CASE_REL, started=iso_at(9, 0)),
            )
            sign_spec(root)
            self.assert_fail(run_spec(root, "verify"), "run_started_at 早于测试文件 mtime 应 FAIL")

        with temp_repo() as root:
            write_case_and_report(
                root,
                evidence_blocks=lambda: evidence_block(root, CASE_REL, started=iso_at(10, 5), finished=iso_at(10, 4)),
            )
            sign_spec(root)
            self.assert_fail(run_spec(root, "verify"), "run_finished_at 早于 run_started_at 应 FAIL")

        with temp_repo() as root:
            write_case_and_report(
                root,
                cases=[(CASE_REL, ("test_fixture_c1",)), (CASE_REL2, ("test_fixture_c2",))],
                evidence_blocks=lambda: evidence_block(root, CASE_REL),
            )
            sign_spec(root, reconciliation=recon_5(file1=CASE_REL, file2=CASE_REL2))
            self.assert_fail(run_spec(root, "verify"), "多文件只记录一个文件 hash 应 FAIL")

        with temp_repo() as root:
            write_case_and_report(
                root,
                cases=[(CASE_REL, ("test_fixture_c1",)), (CASE_REL2, ("test_fixture_c2",))],
            )
            sign_spec(root, reconciliation=recon_5(file1=CASE_REL, file2=CASE_REL2))
            self.assert_pass(run_spec(root, "verify"), "多文件逐个记录 hash/run window 应 PASS")

        with temp_repo() as root:
            write_case_and_report(root)
            sign_spec(root)
            case_path = root / CASE_REL
            write_text(case_path, read_text(case_path) + "\n# changed during run\n")
            self.assert_fail(run_spec(root, "verify"), "测试文件运行中被修改（hash 不匹配）应 FAIL")
            set_mtime(case_path, iso_at(10, 0))
            write_text(
                root / REPORT_REL,
                "# 测试报告\n\n- test_fixture_c1: PASS\n- test_fixture_c2: PASS\n"
                "- 核销率: 2/2\n- E2E: 13/13\n\n## 测试文件证据\n\n"
                + evidence_block(root, CASE_REL)
                + "\n",
            )
            self.assert_pass(run_spec(root, "verify"), "冻结后重跑（新 hash/窗口）应 PASS")

    def test_c7_guard_large_write(self) -> None:
        with temp_repo() as root:
            original = make_large_file(root)
            self.assert_pass(guard_prepare(root), "prepare 应 PASS")
            self.assert_pass(guard_check(root), "未改写时 check 应 PASS")
            truncated = "\n".join(original.splitlines()[:400]) + "\n"
            write_text(root / LARGE_REL, truncated)
            self.assert_fail(guard_check(root), "缩水到 400 行 check 应 FAIL")
            self.assert_pass(guard_restore(root), "restore 应 PASS")
            self.assertEqual(read_text(root / LARGE_REL), original, "restore 后内容应与基线一致")
            self.assert_pass(guard_check(root), "restore 后 check 应 PASS")

        with temp_repo() as root:
            original = make_large_file(root)
            self.assert_pass(guard_prepare(root), "prepare 基线")
            lines = original.splitlines()
            lines[-1] = "TAIL-GONE"
            write_text(root / LARGE_REL, "\n".join(lines) + "\n")
            self.assert_fail(guard_check(root), "尾部标记丢失应 FAIL")

        with temp_repo() as root:
            make_large_file(root)
            self.assert_fail(guard_check(root), "未 prepare（manifest 缺失）check 应 FAIL")

        with temp_repo() as root:
            original = make_large_file(root)
            self.assert_pass(guard_prepare(root), "prepare 基线")
            lines = original.splitlines()
            lines[0] = "乱码 \ufffd"
            write_text(root / LARGE_REL, "\n".join(lines) + "\n")
            self.assert_fail(guard_check(root), "出现 U+FFFD 应 FAIL")

        with nested_repo() as (parent, root):
            write_text(parent / "outside.txt", "x\n")
            result = guard(root, "prepare", "../outside.txt", "--backup", "tmp/outside.bak", "--manifest", "tmp/outside.manifest.json")
            self.assert_fail(result, "prepare .. 越界应 FAIL")

    def test_c8_entry_inventory(self) -> None:
        spec_text = read_text(ROOT / "docs" / "specs" / "2026-11-19-contract-gates-and-concision.md")
        self.assertIn("入口清单：无 UI 变更", spec_text, "本 spec 第 2 节必须写 入口清单：无 UI 变更")
        template = read_text(ROOT / "ship-it" / "references" / "spec-template.md")
        self.assertIn("入口清单", template, "模板必须包含入口清单")
        self.assertIn("无 UI 变更", template, "模板必须给出无 UI 变更写法")
        skill = read_text(ROOT / "ship-it" / "SKILL.md")
        self.assertIn("入口清单", skill, "SKILL 必须包含入口清单闸门")

        with temp_repo() as root:
            sign_spec(root)
            self.assert_pass(run_spec(root, "spec"), "入口清单：无 UI 变更 应 PASS")

        with temp_repo() as root:
            sign_spec(root, entry_inventory=None, frontend="新增 /settings 页面")
            self.assert_fail(run_spec(root, "spec"), "UI 变更无入口清单应 FAIL")

    def test_c9_p_c_number_isolation(self) -> None:
        spec_text = read_text(ROOT / "docs" / "specs" / "2026-11-19-contract-gates-and-concision.md")
        section2 = extract_section(spec_text, 2)
        self.assertNotRegex(section2, r"^- \*\*C\d+", "本 spec 第 2 节不得出现 C 编号标签")

        with temp_repo() as root:
            sign_spec(root)
            self.assert_pass(run_spec(root, "spec"), "第 2 节用 P 编号应 PASS")

        with temp_repo() as root:
            sign_spec(root, section2_extra="- **C14 流程规则**：占用产品条款编号。\n")
            self.assert_fail(run_spec(root, "spec"), "第 2 节出现 **C14 应 FAIL")

    def test_c10_skip_semantics(self) -> None:
        for rel in ("ship-it/SKILL.md", "ship-it/references/spec-template.md", "ship-it/references/team-mode.md"):
            with self.subTest(file=rel):
                self.assertIn("SKIP 必须退出码 2", read_text(ROOT / rel), rel + " 必须写明 SKIP 退出码 2")

    def test_c11_concise_style(self) -> None:
        rule_path = ROOT / "ship-it" / "references" / "rule-style.md"
        self.assertTrue(rule_path.is_file(), "缺少 references/rule-style.md")
        rule_text = read_text(rule_path)
        words = parse_hard_words(rule_text)
        self.assertTrue(words, "rule-style.md 的硬禁用词节没有可解析的词")
        for rel in ("ship-it/SKILL.md", "README.md", "ship-it/references/spec-template.md",
                    "docs/specs/2026-11-19-contract-gates-and-concision.md"):
            text = read_text(ROOT / rel)
            for word in words:
                with self.subTest(file=rel, word=word):
                    self.assertNotIn(word, text, rel + " 含硬禁用词：" + word)
        self.assertIn("建议使用", rule_text, "rule-style.md 必须写裁判规则：建议使用 X = FAIL")
        self.assertIn("FAIL", rule_text, "rule-style.md 必须写明判 FAIL")
        self.assertIn("才可以", rule_text, "rule-style.md 必须写“才可以”例外")

        with temp_repo() as root:
            sign_spec(root)
            self.assert_pass(run_spec(root, "spec"), "check_spec 不得误杀含“才可以”的强制提醒语")

        long_clause = (
            "### C1 测试条款一\n\n"
            "- **前置**：无。\n"
            "- **后置**：" + ("很长的后置条件。" * 120) + "\n"
            "- **失败**：失败。\n"
            "- **不变式**：不变。\n\n" + CLAUSE_C2
        )
        with temp_repo() as root:
            sign_spec(root, clauses=long_clause)
            self.assert_fail(run_spec(root, "spec"), "单条条款超过 800 字符应 FAIL")

    def test_c12_version_compat(self) -> None:
        skill_text = read_text(ROOT / "ship-it" / "SKILL.md")
        self.assertEqual(parse_frontmatter(skill_text).get("version"), "5.1.0", "SKILL.md frontmatter 版本应为 5.1.0")
        self.assertIn("4.7.2", read_text(ROOT / "CHANGELOG.md"), "根 CHANGELOG 必须含 4.7.2")
        skill_changelog = read_text(ROOT / "ship-it" / "CHANGELOG.md")
        self.assertIn("4.7.2", skill_changelog, "skill CHANGELOG 必须含 4.7.2")
        self.assertNotIn("含糊同意判定表", skill_changelog, "skill CHANGELOG 不得保留旧口径：含糊同意判定表")
        self.assertNotIn("入口三处", skill_changelog, "skill CHANGELOG 不得保留旧口径：入口三处")

        template = read_text(ROOT / "ship-it" / "references" / "spec-template.md")
        section2 = extract_section(template, 2)
        self.assertNotRegex(section2, r"^- \*\*C\d+", "模板第 2 节不得再用 C 编号流程规则")
        self.assertIn("P1", section2, "模板第 2 节必须用 P1..Pn")
        section9 = extract_section(template, 9)
        header = ""
        for line in section9.splitlines():
            if line.strip().startswith("| 条款"):
                header = line.strip()
                break
        cells = [cell.strip() for cell in header.strip().strip("|").split("|")]
        self.assertEqual(cells, ["条款", "用例名", "用例文件", "结果", "路径真实性"], "模板第 9 节必须为 5 列核销表")
        self.assertIn("- 测试报告：", section9, "模板第 9 节必须有测试报告 footer")

        team = read_text(ROOT / "ship-it" / "references" / "team-mode.md")
        for field in ("角色", "审查者", "会话标识", "未参与编码声明", "未参与 spec 编写声明", "结论", "证据"):
            self.assertIn(field, team, "team-mode 裁判单字段缺：" + field)

        legacy = run_py(CHECK_SPEC, [LEGACY_SPEC_REL, "--stage", "verify"], cwd=ROOT)
        self.assert_pass(legacy, "旧 spec 按日期 legacy 应 PASS")
        strict = run_py(CHECK_SPEC, [LEGACY_SPEC_REL, "--stage", "spec", "--strict"], cwd=ROOT)
        self.assert_fail(strict, "旧 spec --strict 应强制新规则并 FAIL")

        with temp_repo() as root:
            write_case_and_report(root)
            sign_spec(root, reconciliation=FOUR_COL_RECONCILIATION)
            self.assert_fail(run_spec(root, "verify"), "新 spec 用 4 列核销应 FAIL")

        with temp_repo() as root:
            sign_spec(root)
            spec_path = root / SPEC_REL
            write_text(spec_path, insert_before_section(read_text(spec_path), 6, "- **修订**：追加正文。"))
            self.assert_fail(run_spec(root, "spec"), "§§1–8 改动后旧签约块应 FAIL")

    def test_c13_path_and_secret_safety(self) -> None:
        signed = signed_spec_text()
        with tempfile.TemporaryDirectory(prefix="shipit-gates-") as directory:
            parent = Path(directory)
            root = parent / "repo"
            root.mkdir()
            if GIT:
                init_git(root)
            write_text(parent / "outside-spec.md", signed)
            result = run_py(CHECK_SPEC, ["../outside-spec.md", "--stage", "spec"], cwd=root)
            self.assert_fail(result, "check_spec .. 越界应 FAIL")

        with nested_repo() as (parent, root):
            write_text(root / SPEC_REL, build_spec())
            write_text(parent / "reviews" / (DATE + "-referee-J1.md"), j1_report())
            self.assert_fail(run_roles(root, "sign", "--reviews-dir", "../reviews"), "check_roles --reviews-dir .. 越界应 FAIL")

        with nested_repo() as (parent, root):
            make_large_file(root)
            self.assert_pass(guard_prepare(root), "prepare 基线")
            write_text(parent / "outside.txt", "x\n")
            self.assert_fail(
                guard(root, "restore", "../outside.txt", "--backup", LARGE_BACKUP, "--manifest", LARGE_MANIFEST),
                "restore 文件 .. 越界应 FAIL",
            )
            write_text(parent / "outside.manifest.json", read_text(root / LARGE_MANIFEST))
            self.assert_fail(
                guard(root, "restore", LARGE_REL, "--backup", LARGE_BACKUP, "--manifest", "../outside.manifest.json"),
                "restore manifest .. 越界应 FAIL",
            )

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report(extra="API_KEY=abc")})
            self.assert_fail(run_roles(root, "sign"), "报告含 API_KEY= 应 FAIL")
            write_reviews(root, {"referee-J1": j1_report(extra="TOKEN=")})
            self.assert_fail(run_roles(root, "sign"), "报告含 TOKEN= 空值也应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report()})
            self.assert_pass(run_roles(root, "sign"), "正常报告路径应 PASS")


    @unittest.skipUnless(GIT, "需要 git 命令")
    @slow
    def test_c14_auditor_start_gate(self) -> None:
        with temp_repo() as root:
            make_start_fixture(root)
            self.assert_pass(run_roles(root, "start"), "patrol 3 轮 + 三份 start + 早于实现应 PASS")

        with temp_repo() as root:
            make_start_fixture(root, write_impl=False)
            self.assert_pass(run_roles(root, "start"), "无实现提交时 start 应 PASS（+warning）")

        with temp_repo() as root:
            make_start_fixture(root)
            (root / PATROL_REL).unlink()
            self.assert_fail(run_roles(root, "start"), "缺 auditor-patrol.md 应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root, patrol_kwargs={"rounds": 2})
            self.assert_fail(run_roles(root, "start"), "patrol 轮次少于 3 应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root, patrol_kwargs={"interval": "600 秒（10 分钟，定时巡检）", "round_gap_minutes": 10})
            self.assert_fail(run_roles(root, "start"), "定时巡检间隔超过 5 分钟应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root, patrol_kwargs={"interval": "事件触发（无定时；事前声明；每轮记录 trigger）"})
            self.assert_pass(run_roles(root, "start"), "事件触发 + 每轮 trigger 应 PASS")

        with temp_repo() as root:
            make_start_fixture(root, patrol_kwargs={"interval": "事件触发（无定时；事前声明）", "triggers": False})
            self.assert_fail(run_roles(root, "start"), "事件触发但每轮缺 trigger 应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root, patrol_kwargs={"evidence": False})
            self.assert_fail(run_roles(root, "start"), "patrol 每轮缺证据应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root, patrol_kwargs={"conclusion": "BLOCK"})
            self.assert_fail(run_roles(root, "start"), "patrol 结论非 PASS 应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root, start_at=iso_at(11, 0), first_round=iso_at(11, 1))
            self.assert_fail(run_roles(root, "start"), "patrol 首轮晚于第一个实现提交应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root)
            (root / start_rel("auditor")).unlink()
            self.assert_fail(run_roles(root, "start"), "缺 auditor-start.md 应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root)
            (root / start_rel("referee")).unlink()
            self.assert_fail(run_roles(root, "start"), "缺 referee-start.md 应 FAIL（三份 start 强制）")

        with temp_repo() as root:
            make_start_fixture(root)
            (root / start_rel("security")).unlink()
            self.assert_fail(run_roles(root, "start"), "缺 security-start.md 应 FAIL（三份 start 强制）")

        with temp_repo() as root:
            make_start_fixture(root)
            path = root / start_rel("auditor")
            write_text(path, read_text(path).replace(spec_body_hash(root), "0" * 64))
            set_mtime(path, iso_at(9, 20))
            self.assert_fail(run_roles(root, "start"), "auditor-start 的 spec_hash 与 spec 正文不一致应 FAIL")

    @unittest.skipUnless(GIT, "需要 git 命令")
    @slow
    def test_c15_role_start_report(self) -> None:
        with temp_repo() as root:
            make_verified_fixture(root)
            self.assert_pass(run_roles(root, "verify"), "三份 start + patrol + 报告应 PASS")

        with temp_repo() as root:
            make_verified_fixture(root)
            (root / start_rel("referee")).unlink()
            self.assert_fail(run_roles(root, "verify"), "verify 缺 referee-start.md 应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            (root / start_rel("security")).unlink()
            self.assert_fail(run_roles(root, "verify"), "verify 缺 security-start.md 应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            (root / start_rel("auditor")).unlink()
            self.assert_fail(run_roles(root, "verify"), "verify 缺 auditor-start.md 应 FAIL")

        for role, field in (("auditor", "启动时间"), ("referee", "spec_hash"), ("security", "会话标识")):
            with self.subTest(role=role, missing_field=field), temp_repo() as root:
                make_verified_fixture(root)
                path = root / start_rel(role)
                lines = [line for line in read_text(path).splitlines() if field not in line]
                write_text(path, "\n".join(lines) + "\n")
                self.assert_fail(run_roles(root, "verify"), role + "-start 缺字段应 FAIL：" + field)

        with temp_repo() as root:
            make_verified_fixture(root)
            for role, _reviewer in START_ROLES:
                path = root / start_rel(role)
                write_text(path, read_text(path).replace("启动时间：2026-11-19T09:20:00+08:00",
                                                         "启动时间：2026-11-19T11:00:00+08:00"))
                set_mtime(path, iso_at(11, 0))
            self.assert_fail(run_roles(root, "verify"), "started_at 晚于第一个实现提交应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            path = root / start_rel("security")
            write_text(path, read_text(path).replace(spec_body_hash(root), "0" * 64))
            self.assert_fail(run_roles(root, "verify"), "security-start 的 spec_hash 不一致应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            path = root / start_rel("referee")
            write_text(path, read_text(path).replace("spec_revision：3", "spec_revision：2"))
            self.assert_fail(run_roles(root, "verify"), "start artifact 的 spec_revision 与 spec 不一致应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            write_patrol(root, started_at=iso_at(9, 20), first_round=iso_at(9, 21), reviewer="auditor-9")
            self.assert_fail(run_roles(root, "verify"), "start artifact 与 patrol log 审查者矛盾应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            self.assert_pass(run_roles(root, "accept"), "accept 五份报告 + 三份 start + patrol 应 PASS")

        with temp_repo() as root:
            make_verified_fixture(root)
            (root / start_rel("security")).unlink()
            self.assert_fail(run_roles(root, "accept"), "accept 缺 security-start.md 应 FAIL")

    def test_c16_contract_change_pause(self) -> None:
        with temp_repo() as root:
            sign_spec(root, front={"status": "paused"}, hash_scope="sections_1_8")
            pause_with_snapshot(root, paused_at=iso_at(10, 0), spec_at=iso_at(10, 5))
            self.assert_pass(run_roles(root, "pause"), "status paused + C7 快照 + pause.md 早于 spec 应 PASS")

        with temp_repo() as root:
            sign_spec(root, hash_scope="sections_1_8")
            pause_with_snapshot(root, paused_at=iso_at(10, 0), spec_at=iso_at(10, 5))
            self.assert_fail(run_roles(root, "pause"), "spec status 非 paused 应 FAIL")

        with temp_repo() as root:
            sign_spec(root, front={"status": "paused"}, hash_scope="sections_1_8")
            self.assert_fail(run_roles(root, "pause"), "缺 pause.md 应 FAIL")

        with temp_repo() as root:
            sign_spec(root, front={"status": "paused"}, hash_scope="sections_1_8")
            hash_value = write_snapshot(root, 3)
            write_pause(root, paused_at=iso_at(10, 5), spec_before_revision=3,
                        spec_before_hash=hash_value, spec_before_snapshot="tmp/spec-before-3.md")
            set_mtime(root / SPEC_REL, iso_at(10, 0))
            self.assert_fail(run_roles(root, "pause"), "pause.md mtime 晚于 spec（先改 spec 后落 pause）应 FAIL")

        for label in ("暂停时间", "触发原话", "活跃成员", "结束指令清单", "旧契约停止", "产出保留", "未停住项", "恢复条件"):
            with self.subTest(missing_field=label), temp_repo() as root:
                sign_spec(root, front={"status": "paused"}, hash_scope="sections_1_8")
                pause_with_snapshot(root, paused_at=iso_at(10, 0), spec_at=iso_at(10, 5))
                path = root / PAUSE_REL
                lines = [line for line in read_text(path).splitlines() if label not in line]
                write_text(path, "\n".join(lines) + "\n")
                set_mtime(path, iso_at(10, 0))
                self.assert_fail(run_roles(root, "pause"), "pause.md 缺字段应 FAIL：" + label)

        with temp_repo() as root:
            sign_spec(root, front={"status": "paused"}, hash_scope="sections_1_8")
            pause_with_snapshot(root, paused_at=iso_at(10, 0), spec_at=iso_at(10, 5))
            path = root / PAUSE_REL
            write_text(path, read_text(path).replace("新派发=0", "新派发=1"))
            set_mtime(path, iso_at(10, 0))
            self.assert_fail(run_roles(root, "pause"), "新派发不等于 0 应 FAIL")

    @unittest.skipUnless(GIT, "需要 git 命令")
    @slow
    def test_c17_failure_attempts(self) -> None:
        with temp_repo() as root:
            make_verified_fixture(root)
            self.assert_pass(run_roles(root, "verify"), "无失败 failure log 应 PASS")

        with temp_repo() as root:
            make_verified_fixture(root)
            (root / FAILURE_REL).unlink()
            self.assert_fail(run_roles(root, "verify"), "verify 缺 failure log 应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            write_failure_log(root, rows=["- task：测试\n- subagent：tester-a\n- failure_class：execution_failed"])
            self.assert_fail(run_roles(root, "verify"), "failure log 缺字段应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            write_failure_log(root, rows=[failure_row(attempt=1, action="主脑自做", conclusion="违规")])
            self.assert_fail(run_roles(root, "verify"), "执行失败 1 次就主脑自做应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            write_failure_log(root, rows=[
                failure_row(failure_class="dispatch_failed", attempt=n, action="重试", conclusion="继续")
                for n in (1, 2, 3)
            ])
            self.assert_fail(run_roles(root, "verify"), "派发失败 3 次空转应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            write_failure_log(root, rows=[
                failure_row(attempt=n, action="换新子智能体（第 4 个）", conclusion="PASS")
                for n in (1, 2, 3)
            ])
            self.assert_pass(run_roles(root, "verify"), "执行失败 3 次后换新子智能体应 PASS")

        with temp_repo() as root:
            make_verified_fixture(root)
            write_failure_log(root, rows=[
                failure_row(attempt=n, action="主脑自做", conclusion="违规")
                for n in (1, 2, 3)
            ])
            self.assert_fail(run_roles(root, "verify"), "执行失败 3 次后主脑自做（未获授权）应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            write_failure_log(root, rows=[
                failure_row(failure_class="dispatch_failed", attempt=1, action="换新子智能体", conclusion="PASS")
            ])
            self.assert_pass(run_roles(root, "verify"), "派发失败 1 次后换新子智能体应 PASS")

    def test_c18_docs_consistency(self) -> None:
        self.assertTrue(CHECK_DOCS.is_file(), "缺少 ship-it/scripts/check_docs.py（C18 机器闸门）")
        real = run_py(CHECK_DOCS, ["--root", "."], cwd=ROOT)
        self.assert_pass(real, "仓库文档体检应 PASS（C18/A18）")

        json_result = run_py(CHECK_DOCS, ["--root", ".", "--json"], cwd=ROOT)
        try:
            data = json.loads(json_result.stdout)
        except ValueError:
            self.fail("check_docs --json 输出不是合法 JSON：\n" + (json_result.stdout or "") + (json_result.stderr or ""))
        for key in ("ok", "errors", "warnings", "files", "stale", "duplicate", "long", "contradiction", "allowlist", "stats"):
            self.assertIn(key, data, "check_docs --json 缺少顶层键：" + key)

        with temp_repo() as root:
            write_text(root / "README.md", "# fixture\n\n用户确认 = 签约\n")
            self.assert_fail(run_docs(root), "旧口径（用户确认 = 签约）应 FAIL")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_full_spec())
            write_text(root / "README.md", "# fixture\n\n全量范围 C1–C13 / A1–A13。\n")
            self.assert_fail(run_docs(root), "过期全量计数 C1–C13/A1–A13 应 FAIL")

        with temp_repo() as root:
            paragraph = "本段用于验证跨文件重复检测的唯一测试句子，长度明显超过三十个字符，确保触发重复闸门。"
            write_text(root / "README.md", "# fixture\n\n" + paragraph + "\n")
            write_text(root / "ship-it" / "SKILL.md", "# skill\n\n" + paragraph + "\n")
            self.assert_fail(run_docs(root), "跨文件重复段落（≥30 字符）应 FAIL")

        with temp_repo() as root:
            write_text(root / "README.md", "# fixture\n\n" + "长" * 600 + "\n")
            self.assert_fail(run_docs(root), "单行超过 500 字符应 FAIL")

        with temp_repo() as root:
            url = "https://example.com/ship-it/docs"
            write_text(root / "README.md", "# fixture\n\n[docs](" + url + ")\n\n[again](" + url + ")\n")
            self.assert_fail(run_docs(root), "README 重复 URL 应 FAIL")

        with temp_repo() as root:
            write_text(root / "ship-it" / "references" / "spec-template.md",
                       "# 模板\n\n## 2. 方案自审（怎么做）\n\n- **C14 流程规则**：占用产品条款编号。\n")
            self.assert_fail(run_docs(root), "模板 §2 出现 C 编号应 FAIL")

        with temp_repo() as root:
            write_text(root / "ship-it" / "SKILL.md",
                       "---\nname: ship-it\nversion: 4.7.2\n---\n\n# skill\n\ncheck_roles.py --stage sign|verify|accept\n")
            self.assert_fail(run_docs(root), "check_roles 阶段列表缺 start/pause 应 FAIL")

        with temp_repo() as root:
            write_text(root / "CHANGELOG.md",
                       "# 更新记录\n\n## 版本索引\n\n| 版本 | 日期 | 变更 |\n|---|---|---|\n| v5.1.0 | 2026-11-24 | 短变更。 |\n")
            write_text(root / "ship-it" / "CHANGELOG.md",
                       "# Changelog — ship-it\n\n## 5.1.0（2026-11-24）\n\n短变更。\n")
            write_text(root / "ship-it" / "SKILL.md", "---\nname: ship-it\nversion: 5.1.0\n---\n\n# skill\n")
            self.assert_pass(run_docs(root), "5.1.0 CHANGELOG ≤600 字符 + 三处版本一致应 PASS")

        with temp_repo() as root:
            write_text(root / "CHANGELOG.md",
                       "# 更新记录\n\n## 版本索引\n\n| 版本 | 日期 | 变更 |\n|---|---|---|\n| v5.1.0 | 2026-11-24 | "
                       + "长" * 700 + " |\n")
            write_text(root / "ship-it" / "CHANGELOG.md",
                       "# Changelog — ship-it\n\n## 5.1.0（2026-11-24）\n\n短变更。\n")
            write_text(root / "ship-it" / "SKILL.md", "---\nname: ship-it\nversion: 5.1.0\n---\n\n# skill\n")
            self.assert_fail(run_docs(root), "5.1.0 CHANGELOG 超过 600 字符应 FAIL")

        with temp_repo() as root:
            write_text(root / "CHANGELOG.md",
                       "# 更新记录\n\n## v4.6.0（2026-11-18）\n\n- 旧口径：用户确认 = 签约。\n")
            write_text(root / "README.md", "# fixture\n\n> " + SIGN_PROMPT + "\n")
            self.assert_pass(run_docs(root), "allowlist（历史 CHANGELOG + canonical 提醒语）应 PASS")

        with temp_repo() as root:
            self.assert_fail(run_py(CHECK_DOCS, ["--root", ".."], cwd=root), "check_docs --root .. 越界应 FAIL")


    @unittest.skipUnless(GIT, "需要 git 命令")
    def test_c6_first_write_marker(self) -> None:
        """C6：首个写任务前 tmp/first-write.json；start/patrol 早于首写；仅 commit 校验 FAIL。"""
        with temp_repo() as root:
            make_start_fixture(root)
            self.assert_pass(run_roles(root, "start"), "C6：marker + start/patrol 早于首写应 PASS")

        with temp_repo() as root:
            make_start_fixture(root)
            remove_first_write(root)
            self.assert_fail(run_roles(root, "start"), "C6：缺 first-write marker 应 FAIL")

        invalid_payloads = [
            ("not-json", "JSON 非法"),
            ('{"path": "ship-it/scripts/impl.py"}', "缺 first_write_at"),
            ('{"first_write_at": "2026-11-19T09:30:00+08:00"}', "缺 path"),
            ('{"first_write_at": "2026-11-19T09:30:00+08:00", "path": "/abs/x.py"}', "path 绝对路径"),
            ('{"first_write_at": "2026-11-19T09:30:00+08:00", "path": "../x.py"}', "path 含 .."),
            ('{"first_write_at": "not-a-time", "path": "ship-it/scripts/impl.py"}', "时间非法"),
        ]
        for payload, label in invalid_payloads:
            with self.subTest(marker=label), temp_repo() as root:
                make_start_fixture(root)
                write_text(root / "tmp" / "first-write.json", payload)
                self.assert_fail(run_roles(root, "start"), "C6：marker " + label + " 应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root, first_write_at=iso_at(9, 15))
            self.assert_fail(run_roles(root, "start"), "C6：start artifact 启动时间晚于首写应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root)
            write_patrol(root, started_at=iso_at(9, 35), first_round=iso_at(9, 36))
            self.assert_fail(run_roles(root, "start"), "C6：patrol 启动时间晚于首写应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root)
            write_patrol(root, started_at=iso_at(9, 20), first_round=iso_at(9, 35))
            self.assert_fail(run_roles(root, "start"), "C6：patrol 首轮晚于首写应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root, first_write_at=iso_at(9, 10))
            self.assert_fail(run_roles(root, "start"), "C6：仅 commit 校验不足（start 晚于首写、早于 impl commit）应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root)
            write_first_write(root, iso_at(9, 30), extra={"note": "允许额外键"})
            self.assert_pass(run_roles(root, "start"), "C6：marker 允许额外键应 PASS")

        with temp_repo() as root:
            make_start_fixture(root)
            remove_first_write(root)
            write_text(root / "tmp" / "custom-first-write.json",
                       json.dumps({"first_write_at": iso_at(9, 30), "path": "ship-it/scripts/impl.py"}))
            self.assert_fail(run_roles(root, "start"), "C6：默认 marker 缺失应 FAIL（自定义路径需显式传参）")
            self.assert_pass(
                run_roles(root, "start", "--first-write", "tmp/custom-first-write.json"),
                "C6：--first-write 指向自定义 marker 应 PASS",
            )

    def test_c7_pause_pre_change(self) -> None:
        """C7：暂停前快照 tmp/spec-before-<rev>.md；pause.md 绑定快照签名 hash；先 pause 后改正文。"""
        with temp_repo() as root:
            sign_spec(root, hash_scope="sections_1_8")
            hash_value = write_snapshot(root, 3)
            write_pause(
                root,
                paused_at=iso_at(10, 0),
                spec_before_revision=3,
                spec_before_hash=hash_value,
                spec_before_snapshot="tmp/spec-before-3.md",
            )
            text = read_text(root / SPEC_REL)
            text = text.replace("status: signed", "status: paused", 1)
            text = insert_before_section(text, 6, "- **修订**：暂停后编辑正文。")
            write_text(root / SPEC_REL, text)
            set_mtime(root / SPEC_REL, iso_at(10, 5))
            self.assert_pass(run_roles(root, "pause"), "C7：快照 hash 绑定 + pause 早于 spec 编辑应 PASS")

        with temp_repo() as root:
            sign_spec(root, hash_scope="sections_1_8")
            hash_value = write_snapshot(root, 3)
            write_pause(
                root,
                paused_at=iso_at(10, 0),
                spec_before_revision=3,
                spec_before_hash=hash_value,
                spec_before_snapshot="",
            )
            text = read_text(root / SPEC_REL).replace("status: signed", "status: paused", 1)
            write_text(root / SPEC_REL, text)
            set_mtime(root / SPEC_REL, iso_at(10, 5))
            self.assert_fail(run_roles(root, "pause"), "C7：spec_before_snapshot 为空（缺字段）应 FAIL")

        with temp_repo() as root:
            sign_spec(root, hash_scope="sections_1_8")
            hash_value = write_snapshot(root, 3)
            write_pause(root, paused_at=iso_at(10, 0), spec_before_revision=3,
                        spec_before_hash=hash_value, spec_before_snapshot="tmp/spec-before-3.md")
            text = read_text(root / SPEC_REL).replace("status: signed", "status: paused", 1)
            write_text(root / SPEC_REL, text)
            set_mtime(root / SPEC_REL, iso_at(10, 5))
            (root / "tmp" / "spec-before-3.md").unlink()
            self.assert_fail(run_roles(root, "pause"), "C7：快照文件缺失应 FAIL")

        with temp_repo() as root:
            sign_spec(root, hash_scope="sections_1_8")
            write_snapshot(root, 3)
            write_pause(root, paused_at=iso_at(10, 0), spec_before_revision=3,
                        spec_before_hash="0" * 64, spec_before_snapshot="tmp/spec-before-3.md")
            text = read_text(root / SPEC_REL).replace("status: signed", "status: paused", 1)
            write_text(root / SPEC_REL, text)
            set_mtime(root / SPEC_REL, iso_at(10, 5))
            self.assert_fail(run_roles(root, "pause"), "C7：spec_before_hash 与快照签名 hash 不一致应 FAIL")

        with temp_repo() as root:
            sign_spec(root, hash_scope="sections_1_8")
            hash_value = write_snapshot(root, 3)
            write_pause(root, paused_at=iso_at(10, 0), spec_before_revision=2,
                        spec_before_hash=hash_value, spec_before_snapshot="tmp/spec-before-3.md")
            text = read_text(root / SPEC_REL).replace("status: signed", "status: paused", 1)
            write_text(root / SPEC_REL, text)
            set_mtime(root / SPEC_REL, iso_at(10, 5))
            self.assert_fail(run_roles(root, "pause"), "C7：spec_before_revision 与快照 front matter 不一致应 FAIL")

        for label in ("spec_before_revision", "spec_before_hash", "spec_before_snapshot"):
            with self.subTest(missing_field=label), temp_repo() as root:
                sign_spec(root, hash_scope="sections_1_8")
                hash_value = write_snapshot(root, 3)
                fields = {"spec_before_revision": 3, "spec_before_hash": hash_value,
                          "spec_before_snapshot": "tmp/spec-before-3.md"}
                fields[label] = None
                write_pause(root, paused_at=iso_at(10, 0), **fields)
                text = read_text(root / SPEC_REL).replace("status: signed", "status: paused", 1)
                write_text(root / SPEC_REL, text)
                set_mtime(root / SPEC_REL, iso_at(10, 5))
                self.assert_fail(run_roles(root, "pause"), "C7：pause.md 缺 " + label + " 应 FAIL")

        with temp_repo() as root:
            sign_spec(root, hash_scope="sections_1_8")
            hash_value = write_snapshot(root, 3)
            write_pause(root, paused_at=iso_at(10, 0), spec_before_revision=3,
                        spec_before_hash=hash_value, spec_before_snapshot="tmp/spec-before-3.md")
            text = read_text(root / SPEC_REL).replace("status: signed", "status: paused", 1)
            write_text(root / SPEC_REL, text)
            set_mtime(root / SPEC_REL, iso_at(9, 50))
            self.assert_fail(run_roles(root, "pause"), "C7：pause.md mtime 晚于 spec mtime 应 FAIL")

        with temp_repo() as root:
            sign_spec(root, hash_scope="sections_1_8")
            hash_value = write_snapshot(root, 3)
            write_pause(root, paused_at=iso_at(10, 0), spec_before_revision=3,
                        spec_before_hash=hash_value, spec_before_snapshot="tmp/spec-before-3.md")
            text = read_text(root / SPEC_REL)
            text = insert_before_section(text, 6, "- **修订**：暂停后编辑正文。")
            write_text(root / SPEC_REL, text)
            set_mtime(root / SPEC_REL, iso_at(10, 5))
            self.assert_fail(run_roles(root, "pause"), "C7：spec status 非 paused 应 FAIL")

        with temp_repo() as root:
            sign_spec(root, hash_scope="sections_1_8")
            write_snapshot(root, 3)
            text = read_text(root / SPEC_REL).replace("status: signed", "status: paused", 1)
            text = insert_before_section(text, 6, "- **修订**：暂停后编辑正文。")
            write_text(root / SPEC_REL, text)
            set_mtime(root / SPEC_REL, iso_at(10, 5))
            current_hash = sections_1_8_hash(text)
            write_pause(root, paused_at=iso_at(10, 0), spec_before_revision=3,
                        spec_before_hash=current_hash, spec_before_snapshot="tmp/spec-before-3.md")
            self.assert_fail(run_roles(root, "pause"), "C7：pause 记录当前 spec 而非变更前快照应 FAIL")

    @unittest.skipUnless(GIT, "需要 git 命令")
    @slow
    def test_c8_git_check_revisions(self) -> None:
        """C8：--git-check 按每个 spec 文件自己的 hash_scope 计算；历史 base 全 PASS。"""
        with temp_repo() as root:
            text = sign_spec(root, hash_scope="sections_1_8")
            self.assertEqual(parse_frontmatter(text).get("sign_hash"), sections_1_8_hash(text))
            self.assert_pass(run_spec(root, "spec"), "C8：sections_1_8 显式 scope 应 PASS")
            write_text(root / SPEC_REL, text + "\n§9 追加核销说明。\n")
            self.assert_pass(run_spec(root, "spec"), "C8：sections_1_8 下 §9 改动不影响 sign_hash")
            write_text(root / SPEC_REL, insert_before_section(text, 6, "- **修订**：§§1–8 改一行。"))
            self.assert_fail(run_spec(root, "spec"), "C8：sections_1_8 下 §§1–8 改动应 FAIL")

        with temp_repo() as root:
            text = sign_spec(root, hash_scope="full_body")
            self.assertEqual(parse_frontmatter(text).get("sign_hash"), full_body_hash(text))
            self.assert_pass(run_spec(root, "spec"), "C8：full_body 显式 scope 应 PASS")
            write_text(root / SPEC_REL, text + "\n§9 追加核销说明。\n")
            self.assert_fail(run_spec(root, "spec"), "C8：full_body 下 §9 改动应 FAIL")

        with temp_repo() as root:
            text = sign_spec(root, hash_scope="sections_1_8_a_normalized")
            self.assertEqual(parse_frontmatter(text).get("sign_hash"),
                             sections_1_8_hash(normalize_a_marks(text)))
            toggled = text.replace("- [ ] A1 ", "- [x] A1 ", 1)
            self.assertNotEqual(toggled, text)
            write_text(root / SPEC_REL, toggled)
            self.assert_pass(run_spec(root, "spec"), "C8：a_normalized 下 A 复选框切换不影响 hash")
            write_text(root / SPEC_REL, insert_before_section(text, 6, "- **修订**：§§1–8 改一行。"))
            self.assert_fail(run_spec(root, "spec"), "C8：a_normalized 下 §§1–8 改动应 FAIL")

        with temp_repo() as root:
            text = sign_spec(root)
            self.assertEqual(parse_frontmatter(text).get("sign_hash"),
                             sections_1_8_hash(normalize_a_marks(text)),
                             "C8：2026-11-19 非真实 v4.7.0 spec 缺 hash_scope 应推断 a_normalized")
            self.assert_pass(run_spec(root, "spec"), "C8：缺 hash_scope 按 2026-11-19 推断 a_normalized 应 PASS")

        with temp_repo() as root:
            text = sign_spec(root, front={"spec_revision": "4"})
            self.assertEqual(parse_frontmatter(text).get("sign_hash"),
                             sections_1_8_hash(normalize_a_marks(text)),
                             "C8：2026-11-19 rev4 缺 hash_scope 应推断 a_normalized")

        with temp_repo() as root:
            rel = "docs/specs/2026-11-20-fixture.md"
            text = sign_spec(root, rel=rel, front={"spec_revision": "2"})
            self.assertEqual(parse_frontmatter(text).get("sign_hash"), sections_1_8_hash(text),
                             "C8：2026-11-20 rev2 缺 hash_scope 应推断 sections_1_8")
            self.assert_pass(run_py(CHECK_SPEC, [rel, "--stage", "spec"], cwd=root),
                             "C8：2026-11-20 缺 hash_scope 应 PASS")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec(hash_scope="bogus"))
            self.assert_fail(run_spec(root, "spec"), "C8：非法 hash_scope 应 FAIL")

        with temp_repo() as root:
            rev3 = sign_spec(root, hash_scope="full_body")
            rev4 = sign_spec(root, front={"spec_revision": "4"}, hash_scope="sections_1_8")
            rev4 = rev4.replace("| 待测 |", "| ✅ |")
            shas = history_repo(root, [
                ("init", "2026-11-19T10:00:00+0800", {"README.md": "# fixture\n"}),
                ("docs(spec): rev3 full_body", "2026-11-19T10:01:00+0800", {SPEC_REL: rev3}),
                ("docs(spec): rev4 sections_1_8", "2026-11-19T10:02:00+0800", {SPEC_REL: rev4}),
                ("feat: impl", "2026-11-19T10:03:00+0800", {"ship-it/scripts/impl.py": "VALUE = 1\n"}),
            ])
            self.assert_pass(run_spec(root, "spec", "--git-check", "--base", shas[0]),
                             "C8：--git-check 按各提交自己的 hash_scope（rev4 sections_1_8）应 PASS")
            self.assert_pass(run_spec(root, "spec", "--git-check", "--base", shas[0], "--head", "HEAD"),
                             "C8：--head HEAD 与默认一致应 PASS")

        spec_rel = "docs/specs/2026-11-19-contract-gates-and-concision.md"
        if os.environ.get("CI"):
            self.skipTest("CI 环境历史 base commit 不可达（重建分支历史与 origin/main 不同），跳过历史 base 校验")
        for base in ("df96d34", "830d35f", "03faf7d", "54b1c61", "660a6be"):
            with self.subTest(base=base):
                result = run_py(CHECK_SPEC, [spec_rel, "--stage", "spec", "--git-check", "--base", base], cwd=ROOT)
                self.assert_pass(result, "C8/A8：历史 base " + base + " 应 PASS")
        legacy = run_py(CHECK_SPEC, [
            "docs/specs/2026-11-18-process-violation-retrospective-and-gates.md",
            "--stage", "spec", "--git-check", "--base", "d94613d", "--json",
        ], cwd=ROOT)
        legacy_data = json.loads(legacy.stdout)
        self.assertEqual(legacy_data.get("mode"), "legacy", "C8：2026-11-18 提案必须走 legacy")
        self.assertTrue(any("跳过 --git-check" in item for item in legacy_data.get("warnings", [])),
                        "C8：legacy 必须跳过 --git-check")

    def test_c9_test_speed(self) -> None:
        """C9：四套 <5 分钟；@slow + --fast；报告有 run window/hash；不写死调用次数。"""
        import io as _io
        import tests.run_suite as runner
        self.assertGreaterEqual(len(runner.SUITES), 4, "C9：至少四套测试")
        self.assertEqual(runner.DEFAULT_MAX_SECONDS, 300, "C9：全量预算 300 秒")
        source = read_text(Path(__file__))
        self.assertIn("invoke_script", source, "C9：测试必须进程内调用脚本，不逐用例起子进程")
        legacy_spawn = "sys.executable" + ", str(script)"
        self.assertNotIn(legacy_spawn, source, "C9：run_py 不得再起 Python 子进程")
        self.assertIn("@slow", source, "C9：慢测试必须标记 @slow")
        listed = invoke_script(ROOT / "tests" / "run_suite.py", ["--list"], ROOT)
        self.assert_pass(listed, "C9：--list 应退出 0")
        data = json.loads(listed.stdout)
        self.assertGreater(data["count"], 0)
        fast = invoke_script(ROOT / "tests" / "run_suite.py", ["--fast", "--list"], ROOT)
        self.assert_pass(fast, "C9：--fast --list 应退出 0")
        fast_data = json.loads(fast.stdout)
        self.assertLess(fast_data["count"], data["count"], "C9：--fast 必须排除 @slow 用例")

        class _SpeedProbe(unittest.TestCase):
            def test_probe_pass(self) -> None:
                self.assertTrue(True)

        probe = unittest.TestSuite([_SpeedProbe("test_probe_pass")])
        meta = [{"module": "tests.test_process_gates",
                 "file": "tests/test_process_gates.py",
                 "path": Path(__file__), "tests": 1}]
        report = runner.execute(probe, meta, fast=True, max_seconds=300, stream=_io.StringIO())
        for key in ("run_started_at", "run_finished_at", "elapsed_seconds", "files",
                    "tests_run", "max_seconds", "ok"):
            self.assertIn(key, report, "C9：报告缺字段 " + key)
        self.assertEqual(report["tests_run"], probe.countTestCases(), "C9：tests_run 必须动态计数")
        self.assertEqual(report["files"][0]["pre_sha256"], sha256_file(Path(__file__)))
        self.assertEqual(report["files"][0]["post_sha256"], sha256_file(Path(__file__)))
        probe_again = unittest.TestSuite([_SpeedProbe("test_probe_pass")])
        over = runner.execute(probe_again, meta, fast=True, max_seconds=0, stream=_io.StringIO())
        self.assertTrue(over["over_budget"], "C9：超预算必须可判定")
        self.assertFalse(over["ok"], "C9：超预算必须 FAIL")

    @unittest.skipUnless(GIT, "需要 git 命令")
    @slow
    def test_c10_commit_order(self) -> None:
        """C10：仓库内 pre_commit_check + install-hooks；pre-commit 跑 check_spec --git-check。"""
        pre = SCRIPTS / "pre_commit_check.py"
        wrapper = SCRIPTS / "install-hooks.py"
        workflow = ROOT / ".github" / "workflows" / "ship-it-gates.yml"
        self.assertTrue(pre.is_file(), "C10：缺少 ship-it/scripts/pre_commit_check.py")
        self.assertTrue(wrapper.is_file(), "C10：缺少 ship-it/scripts/install-hooks.py")
        self.assertTrue(workflow.is_file(), "C10：缺少 .github/workflows/ship-it-gates.yml")
        pre_text = read_text(pre)
        self.assertIn("--git-check", pre_text, "C10：pre-commit 必须跑 check_spec --git-check")
        workflow_text = read_text(workflow)
        for token in ("check_text.py", "check_docs.py", "check_spec.py", "--git-check", "upload-artifact"):
            self.assertIn(token, workflow_text, "C10：CI 缺 " + token)
        for rel in ("ship-it/SKILL.md", "README.md", "ship-it/references/spec-template.md"):
            self.assertNotIn("尽早", read_text(ROOT / rel), "C10：" + rel + " 不得写“尽早”")

        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            git_commit(root, "init", "2026-11-19T10:00:00+0800")
            installed = run_py(pre, ["install-hooks", "--root", "."], cwd=root)
            self.assert_pass(installed, "C10：install-hooks 应 PASS")
            hook = root / ".git" / "hooks" / "pre-commit"
            self.assertTrue(hook.is_file(), "C10：install-hooks 必须写 .git/hooks/pre-commit")
            hook_text = hook.read_text(encoding="utf-8")
            self.assertIn("pre_commit_check.py", hook_text)
            self.assertIn("check", hook_text)
            self.assertNotIn("\r", hook_text, "C10：hook 必须 LF")
            self.assert_pass(run_py(pre, ["install-hooks", "--root", "."], cwd=root),
                             "C10：已有本工具 hook 时重复安装应 PASS")
            hook.write_text("#!/bin/sh\necho custom\n", encoding="utf-8")
            self.assert_fail(run_py(pre, ["install-hooks", "--root", "."], cwd=root),
                             "C10：已有非本工具 hook 且无 --force 应 FAIL")
            self.assert_pass(run_py(pre, ["install-hooks", "--root", ".", "--force"], cwd=root),
                             "C10：--force 应覆盖非本工具 hook")
            self.assert_pass(run_py(wrapper, ["--root", ".", "--force"], cwd=root),
                             "C10：install-hooks.py 包装脚本应等价可用")

        spec_text = sign_spec_text_with_scope("sections_1_8")
        with temp_repo() as root:
            shas = history_repo(root, [
                ("init", "2026-11-19T10:00:00+0800", {"README.md": "# fixture\n"}),
                ("docs(spec): sign", "2026-11-19T10:01:00+0800", {SPEC_REL: spec_text}),
                ("feat: impl", "2026-11-19T10:02:00+0800", {"ship-it/scripts/impl.py": "VALUE = 1\n"}),
            ])
            write_text(root / "docs" / "reviews" / "note.md", "# note\n")
            require_git_ok(run_git(root, "add", "-A"), "git add")
            self.assert_pass(run_py(pre, ["check", "--root", ".", "--base", shas[0]], cwd=root),
                             "C10：spec 先于实现应 PASS")

        with temp_repo() as root:
            shas = history_repo(root, [
                ("init", "2026-11-19T10:00:00+0800", {"README.md": "# fixture\n"}),
            ])
            write_text(root / SPEC_REL, spec_text)
            write_text(root / "ship-it" / "scripts" / "impl.py", "VALUE = 1\n")
            require_git_ok(run_git(root, "add", "-A"), "git add")
            self.assert_fail(run_py(pre, ["check", "--root", ".", "--base", shas[0]], cwd=root),
                             "C10：spec 与实现同提交应 FAIL")

        with temp_repo() as root:
            shas = history_repo(root, [
                ("init", "2026-11-19T10:00:00+0800", {"README.md": "# fixture\n"}),
                ("feat: impl first", "2026-11-19T10:01:00+0800", {"ship-it/scripts/impl.py": "VALUE = 1\n"}),
                ("docs(spec): sign", "2026-11-19T10:02:00+0800", {SPEC_REL: spec_text}),
            ])
            write_text(root / "docs" / "reviews" / "note.md", "# note\n")
            require_git_ok(run_git(root, "add", "-A"), "git add")
            self.assert_fail(run_py(pre, ["check", "--root", ".", "--base", shas[0]], cwd=root),
                             "C10：实现先于 spec 应 FAIL")

    @slow
    @unittest.skipUnless(GIT, "需要 git 命令")
    def test_c11_reviewer_liveness(self) -> None:
        """C11：patrol 末轮 last_active_at >= max(first_write_at, test_run_finished) - 5min。"""
        scope = "sections_1_8"
        rev4 = {"spec_revision": "4"}

        with temp_repo() as root:
            make_start_fixture(root, spec_revision="4", hash_scope=scope)
            self.assert_pass(run_roles(root, "start"), "C11：start 末轮 last_active_at 9:29 >= 9:25 应 PASS")

        with temp_repo() as root:
            make_start_fixture(root, spec_revision="4", hash_scope=scope)
            remove_last_active(root)
            self.assert_fail(run_roles(root, "start"), "C11：缺末轮 last_active_at 应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root, spec_revision="4", hash_scope=scope)
            set_last_active(root, iso_at(9, 24))
            self.assert_fail(run_roles(root, "start"), "C11：last_active_at 早于 first_write_at-5min 应 FAIL")

        with temp_repo() as root:
            make_start_fixture(root, spec_revision="4", hash_scope=scope)
            write_case_and_report(root)
            self.assert_pass(run_roles(root, "start"),
                             "C11：start 阶段忽略 test report（run_finished 10:06 也不抬高阈值）应 PASS")

        with temp_repo() as root:
            make_start_fixture(root, spec_revision="3")
            remove_last_active(root)
            self.assert_pass(run_roles(root, "start"), "C11：rev<=3 旧 fixture 跳过 C11 应 PASS（兼容）")

        with temp_repo() as root:
            make_verified_fixture(root, spec_revision="4", hash_scope=scope)
            set_last_active(root, iso_at(10, 1))
            self.assert_pass(run_roles(root, "verify"),
                             "C11：verify 末轮 10:01 = max(9:30, 10:06)-5min 边界应 PASS")

        with temp_repo() as root:
            make_verified_fixture(root, spec_revision="4", hash_scope=scope)
            set_last_active(root, iso_at(10, 0))
            self.assert_fail(run_roles(root, "verify"), "C11：verify 末轮早于阈值应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root, spec_revision="4", hash_scope=scope)
            (root / REPORT_REL).unlink()
            self.assert_fail(run_roles(root, "verify"), "C11：verify 缺 test report/run_finished 应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root, spec_revision="4", hash_scope=scope)
            set_last_active(root, iso_at(10, 1))
            self.assert_pass(run_roles(root, "accept"), "C11：accept 末轮满足阈值应 PASS")

    @slow
    @unittest.skipUnless(GIT, "需要 git 命令")
    def test_c12_reviewer_sole_aggregation(self) -> None:
        """C12：汇总来源必须列仓库内存在的报告路径；叶子会话写法放行。"""
        with temp_repo() as root:
            make_verified_fixture(root)
            self.assert_pass(run_roles(root, "verify"), "C12：汇总来源列全存在路径应 PASS")

        with temp_repo() as root:
            write_text(root / SPEC_REL, build_spec())
            write_reviews(root, {"referee-J1": j1_report()})
            self.assert_pass(run_roles(root, "sign"), "C12：叶子会话（无子代理报告）应 PASS")

        with temp_repo() as root:
            make_verified_fixture(root)
            set_report_summary(root, DATE + "-referee-J3.md", "docs/reviews/2026-11-19-missing-report.md")
            self.assert_fail(run_roles(root, "verify"), "C12：汇总来源路径不存在应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            set_report_summary(root, DATE + "-referee-J3.md", "主脑汇总")
            self.assert_fail(run_roles(root, "verify"), "C12：非叶子会话但无路径应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            set_report_summary(root, DATE + "-referee-J3.md", "../outside-report.md")
            self.assert_fail(run_roles(root, "verify"), "C12：汇总来源路径越界应 FAIL")

        with temp_repo() as root:
            make_verified_fixture(root)
            set_report_summary(root, DATE + "-referee-J3.md", "referee-J3")
            self.assert_fail(run_roles(root, "verify"), "C12：只写 ID 不写路径应 FAIL")

    def test_c1_out_root(self) -> None:
        """C1：run_suite --out realpath 必须在仓库根内；../ 立即 FAIL。"""
        escaped = ROOT.parent / "escaped.json"
        if escaped.exists():
            escaped.unlink()
        result = invoke_script(RUN_SUITE, ["--out", "../escaped.json", "--list"], ROOT)
        self.assert_fail(result, "C1：--out ../escaped.json 应 FAIL")
        self.assertFalse(escaped.exists(), "C1：越界文件不得写出仓库根")
        absolute = str(ROOT.parent / "escaped-abs.json")
        result_abs = invoke_script(RUN_SUITE, ["--out", absolute, "--list"], ROOT)
        self.assert_fail(result_abs, "C1：--out 绝对路径越界应 FAIL")
        self.assert_pass(invoke_script(RUN_SUITE, ["--out", "tmp/test-out.json", "--list"], ROOT),
                         "C1：--out tmp/... 应 PASS")

    @slow
    @unittest.skipUnless(GIT, "需要 git 命令")
    def test_c2_failure_log_secret(self) -> None:
        """C2：failure log 必须过密钥扫描；注入 API_KEY/TOKEN/PASSWORD/SECRET → FAIL。"""
        with temp_repo() as root:
            make_verified_fixture(root)
            self.assert_pass(run_roles(root, "verify"), "C2：无失败记录应 PASS")
        for label, secret in (("API_KEY", "API_KEY=abc123"), ("TOKEN", "TOKEN=xyz"),
                              ("PASSWORD", "PASSWORD=p@ss"), ("SECRET", "SECRET=s3cr3t")):
            with self.subTest(field=label), temp_repo() as root:
                make_verified_fixture(root)
                write_failure_log(root, rows=[failure_row(evidence=secret)])
                self.assert_fail(run_roles(root, "verify"), "C2：failure log 含 " + label + " 应 FAIL")

    @unittest.skipUnless(GIT, "需要 git 命令")
    def test_c3_hook_root(self) -> None:
        """C3：install-hooks 的 hook 目录 realpath 必须在仓库根内；core.hooksPath 越界 → FAIL。"""
        pre = SCRIPTS / "pre_commit_check.py"
        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            git_commit(root, "init", "2026-11-19T10:00:00+0800")
            outside = root.parent / "outside-hooks"
            outside.mkdir(exist_ok=True)
            require_git_ok(run_git(root, "config", "core.hooksPath", str(outside)), "git config core.hooksPath")
            self.assert_fail(run_py(pre, ["install-hooks", "--root", "."], cwd=root),
                             "C3：core.hooksPath 绝对路径越界应 FAIL")
            self.assertFalse((outside / "pre-commit").exists(), "C3：不得写出仓库外 hook")
        with temp_repo() as root:
            init_git(root)
            write_text(root / "README.md", "# fixture\n")
            git_commit(root, "init", "2026-11-19T10:00:00+0800")
            self.assert_pass(run_py(pre, ["install-hooks", "--root", "."], cwd=root),
                             "C3：正常 hook 目录应 PASS")

    def test_c4_check_text_root(self) -> None:
        """C4：check_text --root/--retro/--git-push realpath 必须在仓库根内；../ → FAIL。"""
        with temp_repo() as root:
            write_text(root / "ship-it" / "SKILL.md",
                       "# ship-it\n\n- 远端写前读上传工具。\n- PR 仅在验收后创建。\n- 合并仅用户。\n")
            write_text(root / "docs" / "reviews" / "retro.md", "# 复盘\n\n- 一句能说清不写两句。\n")
            write_text(root / "gpf" / "SKILL.md",
                       "# git-push-firewall\n\n不由此 skill 决定目的地/PR/合并。\n")
            write_text(root.parent / "outside.md", "# outside\n")
            self.assert_pass(invoke_script(CHECK_TEXT, ["--root", ".", "--git-push", "gpf/SKILL.md",
                                                       "--retro", "docs/reviews/retro.md"], root),
                             "C4：仓库内三路径应 PASS")
            self.assert_fail(invoke_script(CHECK_TEXT, ["--root", ".", "--git-push", "gpf/SKILL.md",
                                                       "--retro", "../outside.md"], root),
                             "C4：--retro ../ 越界应 FAIL")
            self.assert_fail(invoke_script(CHECK_TEXT, ["--root", ".", "--git-push", "../outside.md",
                                                       "--retro", "docs/reviews/retro.md"], root),
                             "C4：--git-push ../ 越界应 FAIL")
            self.assert_fail(invoke_script(CHECK_TEXT, ["--root", "..", "--git-push", "gpf/SKILL.md",
                                                       "--retro", "docs/reviews/retro.md"], root),
                             "C4：--root .. 越界应 FAIL")

    def test_c5_ci_pin(self) -> None:
        """C5：CI action 用完整 SHA；for 循环变量必须引号/数组安全展开。"""
        workflow = read_text(ROOT / ".github" / "workflows" / "ship-it-gates.yml")
        uses = re.findall(r"(?m)^\s*uses:\s*(\S+)", workflow)
        self.assertTrue(uses, "C5：workflow 必须有 uses:")
        for action in uses:
            if action.startswith("./"):
                continue
            with self.subTest(action=action):
                self.assertRegex(action, r"@[0-9a-f]{40}$", "C5：action 必须 pin 完整 SHA：" + action)
        quoted = ('for spec in "$CHANGED"' in workflow
                  or 'for spec in "${CHANGED[@]}"' in workflow
                  or "while IFS= read -r spec" in workflow)
        self.assertTrue(quoted, "C5：for spec 必须用引号或数组/read 安全展开")

    def test_c6_default_base(self) -> None:
        """C6：删除 default_base 死代码；base=HEAD 与文档一致。"""
        pre = read_text(SCRIPTS / "pre_commit_check.py")
        self.assertNotIn("def default_base", pre, "C6：不得保留 default_base 死代码")
        self.assertRegex(pre, r"base\s*=\s*base_override\s+or\s+\"HEAD\"",
                         "C6：无 --base 时必须 base = base_override or \"HEAD\"")
        docs = pre + read_text(ROOT / "ship-it" / "SKILL.md") + read_text(ROOT / "ship-it" / "references" / "team-mode.md")
        self.assertRegex(docs, r"(?:--base\s+HEAD|base\s*=\s*HEAD)", "C6：文档必须写明 base=HEAD")

    def test_c10_version(self) -> None:
        """C10：三处 5.1.0 + check_docs EXPECTED_VERSION=5.1.0。"""
        skill = read_text(ROOT / "ship-it" / "SKILL.md")
        self.assertEqual(parse_frontmatter(skill).get("version"), "5.1.0", "C10：SKILL.md 版本应为 5.1.0")
        self.assertIn("5.1.0", read_text(ROOT / "CHANGELOG.md"), "C10：根 CHANGELOG 必须含 5.1.0")
        self.assertIn("5.1.0", read_text(ROOT / "ship-it" / "CHANGELOG.md"), "C10：skill CHANGELOG 必须含 5.1.0")
        self.assertIn("EXPECTED_VERSION = \"5.1.0\"", read_text(SCRIPTS / "check_docs.py"),
                      "C10：check_docs EXPECTED_VERSION 应为 5.1.0")

    @unittest.skipUnless(GIT, "需要 git 命令")
    def test_c7_guard_restore(self) -> None:
        """C7：manifest 含工具 hmac；restore 校验；手写/篡改 hmac → FAIL。"""
        key = "shipit-test-guard-key"
        old_key = os.environ.get("GUARD_KEY")
        os.environ["GUARD_KEY"] = key
        try:
            with temp_repo() as root:
                make_large_file(root)
                self.assert_pass(guard_prepare(root), "C7：prepare（GUARD_KEY）应 PASS")
                manifest = json.loads(read_text(root / LARGE_MANIFEST))
                self.assertIn("hmac", manifest, "C7：manifest 必须含 hmac")
                self.assertRegex(str(manifest["hmac"]), r"^[0-9a-f]{64}$", "C7：hmac 必须是 64 位十六进制")
                self.assert_pass(guard_check(root), "C7：未改写 check 应 PASS")
                self.assert_pass(guard_restore(root), "C7：restore 应 PASS")

            with temp_repo() as root:
                make_large_file(root)
                self.assert_pass(guard_prepare(root), "C7：prepare 基线")
                manifest = json.loads(read_text(root / LARGE_MANIFEST))
                manifest["hmac"] = "0" * 64
                write_text(root / LARGE_MANIFEST, json.dumps(manifest, ensure_ascii=False))
                self.assert_fail(guard_restore(root), "C7：hmac 错误 restore 应 FAIL")

            with temp_repo() as root:
                make_large_file(root)
                self.assert_pass(guard_prepare(root), "C7：prepare 基线")
                manifest = json.loads(read_text(root / LARGE_MANIFEST))
                manifest.pop("hmac", None)
                write_text(root / LARGE_MANIFEST, json.dumps(manifest, ensure_ascii=False))
                self.assert_fail(guard_restore(root), "C7：手写 manifest 缺 hmac 应 FAIL")
        finally:
            if old_key is None:
                os.environ.pop("GUARD_KEY", None)
            else:
                os.environ["GUARD_KEY"] = old_key

    @unittest.skipUnless(GIT, "需要 git 命令")
    def test_c8_reviewer_dispatch(self) -> None:
        """C8：patrol 必须有非空 reviewer_dispatch；start/verify 校验；文档写明派发/返回/检查点唤醒。"""
        with temp_repo() as root:
            make_v472_fixture(root)
            self.assert_pass(run_roles_spec(root, "start", SPEC_REL_472), "C8：start 有 reviewer_dispatch 应 PASS")
        with temp_repo() as root:
            make_v472_fixture(root)
            text = read_text(root / PATROL_REL)
            write_text(root / PATROL_REL, "\n".join(line for line in text.splitlines()
                                                    if not line.startswith("- reviewer_dispatch：")) + "\n")
            self.assert_fail(run_roles_spec(root, "start", SPEC_REL_472), "C8：缺 reviewer_dispatch start 应 FAIL")
        with temp_repo() as root:
            make_v472_fixture(root)
            text = read_text(root / PATROL_REL)
            write_text(root / PATROL_REL, "\n".join(line for line in text.splitlines()
                                                    if not line.startswith("- reviewer_dispatch：")) + "\n")
            self.assert_fail(run_roles_spec(root, "verify", SPEC_REL_472), "C8：缺 reviewer_dispatch verify 应 FAIL")
        docs = read_text(ROOT / "ship-it" / "SKILL.md") + read_text(ROOT / "ship-it" / "references" / "team-mode.md")
        self.assertRegex(docs, r"唤醒.*(?:reviewer|审查员)|(?:reviewer|审查员).*唤醒",
                         "C8：文档必须写唤醒 reviewer/审查员")
        self.assertRegex(docs, r"派发.*返回.*检查点", "C8：文档必须写派发/返回/检查点")

    def test_c9_cleanup(self) -> None:
        """C9：Step 9 清理清单 + git status clean + pre-commit hook 说明（文档断言）。"""
        docs = (read_text(ROOT / "ship-it" / "SKILL.md")
                + read_text(ROOT / "ship-it" / "references" / "team-mode.md")
                + read_text(ROOT / "README.md"))
        for token in ("tmp/", ".tmp/", ".dsh-project-memory/", "tests/__pycache__/",
                      "test/**/*.tmp", "*.gz"):
            with self.subTest(token=token):
                self.assertIn(token, docs, "C9：清理清单缺 " + token)
        self.assertIn("git status", docs, "C9：必须写 git status clean")
        self.assertRegex(docs, r"pre-commit", "C9：必须说明 pre-commit hook")
        self.assertRegex(docs, r"install-hooks", "C9：必须说明 hook 安装方式")

    @unittest.skipUnless(GIT, "需要 git 命令")
    def test_c12_reviewer_mandatory(self) -> None:
        """C12：reviewer_dispatch_at < min(role_dispatch)；轮次 Δ<=60s；末轮新鲜；汇总覆盖五角色。"""
        with temp_repo() as root:
            make_v472_fixture(root)
            self.assert_pass(run_roles_spec(root, "verify", SPEC_REL_472), "C12：默认合规 patrol verify 应 PASS")
            self.assert_pass(run_roles_spec(root, "accept", SPEC_REL_472), "C12：默认合规 patrol accept 应 PASS")

        with temp_repo() as root:
            make_v472_fixture(root)
            write_v472_patrol(root, reviewer_dispatch_at=iso_at(9, 20, 30))
            self.assert_fail(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C12：reviewer 晚于角色派发应 FAIL")

        with temp_repo() as root:
            make_v472_fixture(root)
            write_v472_patrol(root, round_gap_minutes=2)
            self.assert_fail(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C12：相邻轮次 Δ>60s 应 FAIL")

        with temp_repo() as root:
            make_v472_fixture(root)
            write_v472_patrol(root, last_active_list=[iso_at(10, 3)])
            self.assert_fail(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C12：末轮 last_active_at 不新鲜应 FAIL")

        with temp_repo() as root:
            make_v472_fixture(root)
            patrol = read_text(root / PATROL_REL)
            text = patrol.splitlines()
            for index, line in enumerate(text):
                if line.startswith("- 汇总来源："):
                    summary = json.loads(line.split("：", 1)[1])
                    summary.pop("tester", None)
                    text[index] = "- 汇总来源：" + json.dumps(summary, ensure_ascii=False, sort_keys=True)
            write_text(root / PATROL_REL, "\n".join(text) + "\n")
            self.assert_fail(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C12：汇总来源缺角色应 FAIL")

        with temp_repo() as root:
            make_v472_fixture(root)
            patrol = read_text(root / PATROL_REL)
            text = patrol.splitlines()
            for index, line in enumerate(text):
                if line.startswith("- 汇总来源："):
                    summary = json.loads(line.split("：", 1)[1])
                    summary["tester"] = "docs/reviews/2026-11-19-missing.md"
                    text[index] = "- 汇总来源：" + json.dumps(summary, ensure_ascii=False, sort_keys=True)
            write_text(root / PATROL_REL, "\n".join(text) + "\n")
            self.assert_fail(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C12：汇总来源路径不存在应 FAIL")

        with temp_repo() as root:
            make_v472_fixture(root)
            dispatch = {
                "dev": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "tester": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "security": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "referee": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "auditor": {"dispatch_at": iso_at(9, 15), "source": "reuse"},
            }
            write_v472_patrol(root, role_dispatch=dispatch, reviewer_dispatch_at=iso_at(9, 19))
            self.assert_pass(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C12：auditor(reviewer) 派发早于 reviewer_dispatch_at 应豁免 PASS")

        with temp_repo() as root:
            make_v472_fixture(root)
            write_v472_patrol(root, rounds=4, started_at=iso_at(8, 59), heartbeat_effective_at=iso_at(9, 3))
            set_round_times(root, [iso_at(9, 0), iso_at(9, 2), iso_at(9, 4), iso_at(9, 5)])
            self.assert_pass(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C12：heartbeat_effective_at 之前的 Δ>60s 轮次应忽略 PASS")

        with temp_repo() as root:
            make_v472_fixture(root)
            write_v472_patrol(root, rounds=4, started_at=iso_at(8, 59), heartbeat_effective_at=iso_at(9, 3))
            set_round_times(root, [iso_at(9, 0), iso_at(9, 2), iso_at(9, 4), iso_at(9, 6)])
            self.assert_fail(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C12：heartbeat_effective_at 之后 Δ>60s 应 FAIL")

        with temp_repo() as root:
            make_v472_fixture(root)
            write_v472_patrol(root, rounds=4, started_at=iso_at(8, 59), heartbeat_effective_at=iso_at(9, 3),
                              reviewer_pause=[iso_at(9, 5, 30)],
                              reviewer_resume=[iso_at(9, 6, 30)])
            set_round_times(root, [iso_at(9, 4), iso_at(9, 5), iso_at(9, 6), iso_at(9, 7)])
            self.assert_pass(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C12：暂停段轮次剔除 + 跨暂停跳过 Δ 应 PASS")

        with temp_repo() as root:
            make_v472_fixture(root)
            write_v472_patrol(root, rounds=4, started_at=iso_at(8, 59), heartbeat_effective_at=iso_at(9, 3),
                              reviewer_pause=[iso_at(9, 5, 30), iso_at(9, 6, 30)],
                              reviewer_resume=[iso_at(9, 6, 30)])
            set_round_times(root, [iso_at(9, 4), iso_at(9, 5), iso_at(9, 6), iso_at(9, 7)])
            self.assert_fail(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C12：pause/resume 数量不匹配应 FAIL")

        with temp_repo() as root:
            make_v472_fixture(root)
            patrol = read_text(root / PATROL_REL)
            write_text(root / PATROL_REL, "\n".join(line for line in patrol.splitlines()
                                                    if not line.startswith("- heartbeat_effective_at：")) + "\n")
            self.assert_fail(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C12：缺 heartbeat_effective_at 应 FAIL")

    @unittest.skipUnless(GIT, "需要 git 命令")
    def test_c13_role_reuse(self) -> None:
        """C13：role_dispatch source 枚举合法；new_* 必须附理由；reuse 放行。"""
        with temp_repo() as root:
            make_v472_fixture(root)
            self.assert_pass(run_roles_spec(root, "verify", SPEC_REL_472), "C13：合法 source/new_missing+理由 应 PASS")

        with temp_repo() as root:
            make_v472_fixture(root)
            dispatch = {
                "dev": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "tester": {"dispatch_at": iso_at(9, 20), "source": "new_whatever"},
                "security": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "referee": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "auditor": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
            }
            write_v472_patrol(root, role_dispatch=dispatch)
            self.assert_fail(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C13：非法 source 应 FAIL")

        with temp_repo() as root:
            make_v472_fixture(root)
            dispatch = {
                "dev": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "tester": {"dispatch_at": iso_at(9, 20), "source": "new_overflow"},
                "security": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "referee": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "auditor": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
            }
            write_v472_patrol(root, role_dispatch=dispatch)
            self.assert_fail(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C13：new_* 无理由应 FAIL")

        with temp_repo() as root:
            make_v472_fixture(root)
            dispatch = {
                "dev": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "tester": {"dispatch_at": iso_at(9, 20), "source": "new_overflow", "reason": "上下文溢出"},
                "security": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "referee": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
                "auditor": {"dispatch_at": iso_at(9, 20), "source": "reuse"},
            }
            write_v472_patrol(root, role_dispatch=dispatch)
            self.assert_pass(run_roles_spec(root, "verify", SPEC_REL_472),
                             "C13：new_* 附理由应 PASS")

    def test_c14_lead_quiet(self) -> None:
        """C14：文档写明提醒各一次、心跳内部静默、被动响应、不重复进度。"""
        docs = (read_text(ROOT / "ship-it" / "SKILL.md")
                + read_text(ROOT / "ship-it" / "references" / "team-mode.md"))
        self.assertRegex(docs, r"各(?:发送)?一次|只发一次|仅一次", "C14：必须写提醒各一次")
        self.assertRegex(docs, r"不重复催促|不重复提醒|不再催促", "C14：必须写不重复催促")
        self.assertIn("心跳", docs, "C14：必须写心跳")
        self.assertRegex(docs, r"用户可见|对用户可见|可能.*可见", "C14：心跳提醒可能对用户可见")
        self.assertRegex(docs, r"活跃期|dev/tester 活跃|开发/测试.*活跃", "C14：心跳仅活跃期启用")
        self.assertRegex(docs, r"间隙.*暂停|暂停.*间隙|间隙暂停", "C14：心跳间隙暂停")
        self.assertRegex(docs, r"被动响应|被动", "C14：其余场景被动响应")
        self.assertRegex(docs, r"不重复发送相同状态|不重复.*进度", "C14：不得重复发送相同状态")

    def test_a19_sign_hash_scope(self) -> None:
        real_spec = ROOT / "docs" / "specs" / "2026-11-19-contract-gates-and-concision.md"
        real_text = read_text(real_spec)
        expected = parse_frontmatter(real_text).get("sign_hash", "").strip().lower()
        self.assertRegex(expected, r"^[0-9a-f]{64}$", "A19：真实 spec 必须已签约并含 64 位 sign_hash")
        self.assertEqual(sections_1_8_hash(normalize_a_marks(real_text)), expected, "A19：真实 spec 的 A 归一化 §§1–8 SHA-256 应等于签约值")
        result = run_py(CHECK_SPEC, [str(real_spec), "--print-sign-hash"], cwd=ROOT)
        self.assert_pass(result, "真实 spec --print-sign-hash 应退出 0")
        match = re.search(r"[0-9a-fA-F]{64}", (result.stdout or "") + (result.stderr or ""))
        self.assertIsNotNone(match, "--print-sign-hash 未输出 64 位 SHA-256")
        self.assertEqual(match.group(0).lower(), expected, "--print-sign-hash 必须与 A 归一化 §§1–8 一致（A19）")

        with temp_repo() as root:
            signed = sign_spec(root, reconciliation=RECON_PENDING, hash_scope="sections_1_8")
            hash_before = sections_1_8_hash(read_text(root / SPEC_REL))
            self.assertEqual(hash_before, sections_1_8_hash(signed), "签约 hash 必须为 §§1–8")
            write_case_and_report(root)
            filled = build_spec(
                reconciliation=DEFAULT_RECONCILIATION,
                section9_extra="- E2E：13/13\n",
                hash_scope="sections_1_8",
            ).replace("0" * 64, hash_before)
            write_text(root / SPEC_REL, filled)
            self.assertEqual(
                sections_1_8_hash(read_text(root / SPEC_REL)),
                hash_before,
                "§9 填 ✅ 后 §§1–8 hash 不得变化（A19）",
            )
            printed = run_py(CHECK_SPEC, [SPEC_REL, "--print-sign-hash"], cwd=root)
            match = re.search(r"[0-9a-fA-F]{64}", (printed.stdout or "") + (printed.stderr or ""))
            self.assertIsNotNone(match, "§9 填 ✅ 后 --print-sign-hash 未输出")
            self.assertEqual(match.group(0).lower(), hash_before, "§9 填 ✅ 后 sign_hash 必须不变（A19）")
            self.assert_pass(run_spec(root, "spec"), "§9 填 ✅ 后 --stage spec 应 PASS")
            self.assert_pass(run_spec(root, "verify"), "§9 填 ✅ 后 --stage verify 应 PASS（A19）")

        with temp_repo() as root:
            sign_spec(root, hash_scope="sections_1_8")
            hash_before = sections_1_8_hash(read_text(root / SPEC_REL))
            write_text(
                root / SPEC_REL,
                insert_before_section(read_text(root / SPEC_REL), 6, "- **修订**：§§1–8 改动。"),
            )
            self.assertNotEqual(
                sections_1_8_hash(read_text(root / SPEC_REL)),
                hash_before,
                "§§1–8 改动必须改变 hash",
            )
            self.assert_fail(run_spec(root, "spec"), "§§1–8 改动后 sign_hash 不匹配应 FAIL（A19）")

        with temp_repo() as root:
            sign_spec(root, hash_scope="sections_1_8")
            hash_before = sections_1_8_hash(read_text(root / SPEC_REL))
            write_text(root / SPEC_REL, read_text(root / SPEC_REL) + "\n§9 追加一行核销说明。\n")
            self.assertEqual(
                sections_1_8_hash(read_text(root / SPEC_REL)),
                hash_before,
                "§9 改动不得改变 §§1–8 hash（A19）",
            )
            self.assert_pass(run_spec(root, "spec"), "仅 §9 改动时 sign_hash 仍有效（A19）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
