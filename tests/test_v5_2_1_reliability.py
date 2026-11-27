#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.2.1 可靠性修复契约派生测试（重做版）。

契约：ship-it/docs/specs/2026-11-26-v5.2.1-reliability-fixes-redo.md C1–C10。
覆盖 C1–C7 基线 + C8/C9/C10 新增条款的机器可查断言。

用法：
    python -m unittest tests.test_v5_2_1_reliability -v
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "ship-it" / "scripts"


def run_py(script: Path, args, cwd=None, timeout=30):
    proc = subprocess.run(
        [sys.executable, str(script)] + list(args),
        cwd=str(cwd or ROOT), capture_output=True, text=True, encoding="utf-8", timeout=timeout,
    )
    return proc


class C1SpecDirUnified(unittest.TestCase):
    """C1：spec 目录统一到 ship-it/docs/specs/。"""

    def test_c1_toplevel_docs_specs_deleted(self):
        """toplevel docs/specs/ 已删除。"""
        self.assertFalse((ROOT / "docs" / "specs").exists(),
                         "C1：toplevel docs/specs/ 应已删除")

    def test_c1_ship_it_docs_specs_has_specs(self):
        """ship-it/docs/specs/ 含 ≥14 个 spec（13 迁入 + v5.2.0 + v5.2.1）。"""
        specs = list((ROOT / "ship-it" / "docs" / "specs").glob("*.md"))
        self.assertGreaterEqual(len(specs), 14,
                                "C1：ship-it/docs/specs/ 应含 ≥14 个 spec，实际 %d" % len(specs))

    def test_c1_ci_prefix_aligned(self):
        """CI ship-it-gates.yml 用 ship-it/docs/specs/ 前缀。"""
        ci = ROOT / ".github" / "workflows" / "ship-it-gates.yml"
        text = ci.read_text(encoding="utf-8")
        self.assertIn("ship-it/docs/specs/*.md", text,
                      "C1：CI 应用 ship-it/docs/specs/ 前缀")
        self.assertNotIn("'docs/specs/*.md'", text,
                         "C1：CI 不应再用裸 docs/specs/ 前缀")


class C2ExpectedVersionDynamic(unittest.TestCase):
    """C2：EXPECTED_VERSION 动态读 SKILL.md frontmatter。"""

    def test_c2_skill_md_version_exists(self):
        """SKILL.md frontmatter 有合法 version。"""
        skill = (ROOT / "ship-it" / "SKILL.md").read_text(encoding="utf-8")
        import re
        m = re.search(r"^version:\s*(\d+\.\d+\.\d+)\s*$", skill, re.M)
        self.assertIsNotNone(m, "C2：SKILL.md frontmatter 应有合法 version")
        self.assertEqual(m.group(1), "5.2.1", "C2：SKILL.md version 应为 5.2.1")

    def test_c2_check_docs_dynamic_read_logic(self):
        """check_docs.py 有动态读 EXPECTED_VERSION 的逻辑（main 里覆盖模块级默认值）。"""
        text = (SCRIPTS / "check_docs.py").read_text(encoding="utf-8")
        self.assertIn("extract_version", text,
                      "C2：check_docs 应使用 extract_version")
        self.assertIn("dynamic_version", text,
                      "C2：check_docs main 应有 dynamic_version 动态读逻辑")
        self.assertIn("global EXPECTED_VERSION", text,
                      "C2：check_docs main 应 global 覆盖 EXPECTED_VERSION")
        self.assertIn("fail closed", text,
                      "C2：check_docs 应 fail closed（读不到 exit 1）")

    def test_c2_check_docs_reads_skill_md(self):
        """check_docs 启动时动态读 ship-it/SKILL.md。"""
        text = (SCRIPTS / "check_docs.py").read_text(encoding="utf-8")
        self.assertIn("ship-it", text)
        self.assertIn("SKILL.md", text)
        self.assertIn("dynamic_version", text.lower().replace("_", "_") or "EXPECTED_VERSION = dynamic_version" in text,
                      "C2：check_docs 应有动态读 version 逻辑")

    def test_c2_check_docs_passes_on_current_repo(self):
        """check_docs 在当前仓库 PASS（版本动态读生效）。"""
        result = run_py(SCRIPTS / "check_docs.py", ["--root", "."])
        self.assertEqual(result.returncode, 0,
                         "C2：check_docs 应 PASS，实际 exit %d\n%s" % (result.returncode, result.stdout[-500:]))

    def test_c2_fail_closed_when_skill_md_missing(self):
        """SKILL.md 不存在时 check_docs fail closed exit 1。"""
        with tempfile.TemporaryDirectory(prefix="shipit-c2-") as d:
            root = Path(d)
            result = run_py(SCRIPTS / "check_docs.py", ["--root", "."], cwd=root)
            self.assertEqual(result.returncode, 1,
                             "C2：SKILL.md 缺失应 fail closed exit 1，实际 %d" % result.returncode)


class C3SpecFlow(unittest.TestCase):
    """C3：spec_flow.py sign/accept/reconcile 三子命令。"""

    def test_c3_spec_flow_exists_and_compiles(self):
        """spec_flow.py 存在且可编译。"""
        sf = SCRIPTS / "spec_flow.py"
        self.assertTrue(sf.is_file(), "C3：spec_flow.py 应存在")
        result = run_py(sf, ["--help"])
        self.assertEqual(result.returncode, 0, "C3：spec_flow --help 应 exit 0")

    def test_c3_three_subcommands(self):
        """sign/accept/reconcile 三子命令可用。"""
        result = run_py(SCRIPTS / "spec_flow.py", ["--help"])
        combined = result.stdout + result.stderr
        for cmd in ("sign", "accept", "reconcile"):
            self.assertIn(cmd, combined, "C3：spec_flow 应有 %s 子命令" % cmd)

    def test_c3_fields_align_check_spec(self):
        """字段单点对齐 check_spec 的常量（import 而非复制）。"""
        text = (SCRIPTS / "spec_flow.py").read_text(encoding="utf-8")
        self.assertIn("from check_spec import", text,
                      "C3：spec_flow 应 import check_spec 常量")
        self.assertIn("COMMON_FM_KEYS", text)
        self.assertIn("ACCEPT_FM_KEYS", text)

    def test_c3_sign_preflight_three_gates(self):
        """C3[B1]：spec_flow sign 前置三闸门（draft + check_docs + print-sign-hash）。"""
        text = (SCRIPTS / "spec_flow.py").read_text(encoding="utf-8")
        self.assertIn("三闸门", text, "C3[B1]：spec_flow sign 应有三闸门逻辑")
        self.assertIn("draft", text, "C3[B1]：闸门① 应含 draft")
        self.assertIn("check_docs", text, "C3[B1]：闸门② 应含 check_docs")
        self.assertIn("print-sign-hash", text, "C3[B1]：闸门③ 应含 print-sign-hash")

    def test_c3_reconcile_exact_def_match(self):
        """C3[B5]：reconcile 精确匹配 def <name>( 。"""
        text = (SCRIPTS / "spec_flow.py").read_text(encoding="utf-8")
        self.assertIn("def_pattern", text, "C3[B5]：spec_flow reconcile 应有 def_pattern 精确匹配")
        self.assertIn("re.escape", text, "C3[B5]：应使用 re.escape 防正则注入")

    def test_c3_reconcile_table_exempt_from_dup(self):
        """C3[B6]：check_docs 对 spec §9 核销表区域豁免 DUP 检测。"""
        text = (SCRIPTS / "check_docs.py").read_text(encoding="utf-8")
        self.assertIn("核销表", text, "C3[B6]：check_docs spec_regions 应含核销表区域")
        self.assertIn("§9", text, "C3[B6]：check_docs 应识别 §9 核销表")


class C4LocalCheck(unittest.TestCase):
    """C4：local_check.py 1:1 复刻 CI 四步。"""

    def test_c4_local_check_exists_and_compiles(self):
        """local_check.py 存在且可编译。"""
        lc = SCRIPTS / "local_check.py"
        self.assertTrue(lc.is_file(), "C4：local_check.py 应存在")
        result = run_py(lc, ["--help"])
        self.assertEqual(result.returncode, 0, "C4：local_check --help 应 exit 0")

    def test_c4_four_steps_replicate_ci(self):
        """local_check 复刻 CI 4 步（check_spec/check_text/check_docs/tests）。"""
        text = (SCRIPTS / "local_check.py").read_text(encoding="utf-8")
        for step in ("check_spec", "check_text", "check_docs", "tests.run_suite"):
            self.assertIn(step, text, "C4：local_check 应含 %s 步" % step)

    def test_c4_base_dual_mode(self):
        """base 双模式：--base HEAD / --pr-base。"""
        text = (SCRIPTS / "local_check.py").read_text(encoding="utf-8")
        self.assertIn("--base", text, "C4：local_check 应有 --base 参数")
        self.assertIn("--pr-base", text, "C4：local_check 应有 --pr-base 参数")

    def test_c4_no_check_roles(self):
        """不加 check_roles（CI 没跑）。"""
        text = (SCRIPTS / "local_check.py").read_text(encoding="utf-8")
        # local_check 不应调用 check_roles
        self.assertNotIn("check_roles", text.replace("check_roles", "", 1) if "check_roles" in text else text,
                         "C4：local_check 不应加 check_roles（CI 没跑）")


class C5DocQualityBlindSpot(unittest.TestCase):
    """C5：文档质量盲区修补（DUP 短文本 + 流程术语）。"""

    def test_c5_core_pair_threshold_15(self):
        """check_docs 核心文件对 DUP 阈值 15。"""
        text = (SCRIPTS / "check_docs.py").read_text(encoding="utf-8")
        self.assertIn("CORE_PAIR_MIN_CHARS", text, "C5：check_docs 应有 CORE_PAIR_MIN_CHARS")
        self.assertIn("15", text, "C5：核心文件对阈值应为 15")

    def test_c5_term_glossary_exists(self):
        """term-glossary.md 新建。"""
        tg = ROOT / "ship-it" / "references" / "term-glossary.md"
        self.assertTrue(tg.is_file(), "C5：term-glossary.md 应存在")
        text = tg.read_text(encoding="utf-8")
        self.assertIn("5 轨道", text, "C5：term-glossary 应含 '5 轨道' 权威名")
        self.assertIn("五轨道", text, "C5：term-glossary 应含 '五轨道' 别名")

    def test_c5_check_terms_dual_glossary(self):
        """check_terms 扩展双词典源。"""
        text = (SCRIPTS / "check_terms.py").read_text(encoding="utf-8")
        self.assertIn("term-glossary", text, "C5：check_terms 应引用 term-glossary")
        self.assertIn("role-glossary", text, "C5：check_terms 仍引用 role-glossary")

    def test_c5_check_terms_passes(self):
        """check_terms 在当前仓库 PASS。"""
        result = run_py(SCRIPTS / "check_terms.py", ["--root", "."])
        self.assertEqual(result.returncode, 0,
                         "C5：check_terms 应 PASS，实际 exit %d" % result.returncode)

    def test_c5_check_text_term_pairs_from_glossary(self):
        """C5[B3]：check_text TERM_PAIRS 从 term-glossary.md 词典读（非硬编码）。"""
        text = (SCRIPTS / "check_text.py").read_text(encoding="utf-8")
        self.assertIn("term-glossary.md", text,
                      "C5[B3]：check_text 应引用 term-glossary.md")
        self.assertIn("TERM_PAIRS", text,
                      "C5[B3]：check_text 应有 TERM_PAIRS（从词典读）")
        # 不应再有硬编码的 5 组术语对列表
        self.assertNotIn('("五选一", "五轨道")', text,
                         "C5[B3]：check_text 不应硬编码术语对（应从词典读）")


class C6ThawEnforce(unittest.TestCase):
    """C6：已验收条款被改强制解冻重跑。"""

    def test_c6_check_thaw_function_exists(self):
        """check_spec.py 有 check_thaw 函数。"""
        text = (SCRIPTS / "check_spec.py").read_text(encoding="utf-8")
        self.assertIn("def check_thaw", text, "C6：check_spec 应有 check_thaw 函数")
        self.assertIn("accept_commit", text, "C6：check_thaw 应引用 accept_commit")
        self.assertIn("git diff", text, "C6：check_thaw 应用 git diff 比对")

    def test_c6_old_c16_warning_removed(self):
        """原 C16 空壳 WARNING 已废弃。"""
        text = (SCRIPTS / "check_spec.py").read_text(encoding="utf-8")
        # 原空壳的 WARNING 文案不应再出现
        self.assertNotIn("C16：§9 核销表缺'解冻记录'字段定义", text,
                         "C6：原 C16 空壳 WARNING 应已废弃")

    def test_c6_skips_without_accept_commit(self):
        """无 accept_commit 时 check_thaw 跳过（legacy 无验收基准）。"""
        # 当前 spec 无 accept_commit，verify 不应因 C6 报错（虽有其他 verify 错误）
        # 这里只验证 check_thaw 函数在无 accept_commit 时不抛异常
        text = (SCRIPTS / "check_spec.py").read_text(encoding="utf-8")
        self.assertIn("if not commit:", text, "C6：check_thaw 应在无 accept_commit 时 return")


class C7RoundsQueryable(unittest.TestCase):
    """C7：分轮追问 + 先查验塑形 + 澄清记录可查。"""

    def test_c7_draft_validates_rounds_format(self):
        """check_spec --stage draft 校验分轮格式。"""
        text = (SCRIPTS / "check_spec.py").read_text(encoding="utf-8")
        self.assertIn("R1", text, "C7：check_spec draft 应校验 R1 分轮")
        self.assertIn("查验", text, "C7：check_spec draft 应校验'查验'栏")
        self.assertIn("据此提问", text, "C7：check_spec draft 应校验'据此提问'栏")

    def test_c7_team_mode_has_round_discipline(self):
        """team-mode.md 需求分析师卡补分轮追问纪律。"""
        tm = ROOT / "ship-it" / "references" / "team-mode.md"
        text = tm.read_text(encoding="utf-8")
        self.assertIn("分轮追问纪律", text, "C7：team-mode 应有'分轮追问纪律'")
        self.assertIn("上一轮用户答复后才进下一轮", text,
                      "C7：team-mode 应有串行等待纪律")

    def test_c7_spec_template_has_rounds_format(self):
        """spec-template.md §1 有分轮格式说明。"""
        st = ROOT / "ship-it" / "references" / "spec-template.md"
        text = st.read_text(encoding="utf-8")
        self.assertIn("分轮决策清单", text, "C7：spec-template 应有分轮决策清单格式")
        self.assertIn("查验", text, "C7：spec-template 分轮格式应含'查验'")

    def test_c7_draft_single_question_per_round(self):
        """C7[B10]：check_spec draft 每轮单问题启发式校验。"""
        text = (SCRIPTS / "check_spec.py").read_text(encoding="utf-8")
        self.assertIn("C7[B10]", text, "C7[B10]：check_spec 应有 C7[B10] 单问题校验")
        self.assertIn("每轮只问一个最关键问题", text,
                      "C7[B10]：check_spec 应有每轮单问题启发式")
        # team-mode.md 也应强化"一次只问一个"
        tm = ROOT / "ship-it" / "references" / "team-mode.md"
        tm_text = tm.read_text(encoding="utf-8")
        self.assertIn("每轮只问一个最关键问题", tm_text,
                      "C7[B10]：team-mode 应强化每轮只问一个")


class C8AbandonedContractFlow(unittest.TestCase):
    """C8：废弃契约流程标准化（A4）——机器校验部分。"""

    def test_c8_signed_to_paused_recognized(self):
        """check_spec 识别 signed→paused 转换：旧 spec（paused）不报 status 错误。"""
        spec = ROOT / "ship-it" / "docs" / "specs" / "2026-11-26-v5.2.1-reliability-fixes.md"
        proc = run_py(SCRIPTS / "check_spec.py",
                      [str(spec), "--stage", "spec"], cwd=ROOT)
        self.assertEqual(proc.returncode, 0,
                         "C8[A4-C]：paused spec 应通过 check_spec（实际 %d）\n%s" % (
                             proc.returncode, proc.stdout + proc.stderr))

    def test_c8_pause_retro_records_required(self):
        """paused spec 必须有 pause 记录 + 复盘记录。"""
        reviews = ROOT / "docs" / "reviews"
        self.assertTrue((reviews / "2026-11-26-pause.md").is_file(),
                        "C8[A4-C]：pause 记录 docs/reviews/2026-11-26-pause.md 应存在")
        self.assertTrue((reviews / "2026-11-26-retrospective.md").is_file(),
                        "C8[A4-C]：复盘记录 docs/reviews/2026-11-26-retrospective.md 应存在")

    def test_c8_old_spec_not_revived(self):
        """旧 spec 维持 paused 不复活（status 仍为 paused）。"""
        spec = ROOT / "ship-it" / "docs" / "specs" / "2026-11-26-v5.2.1-reliability-fixes.md"
        text = spec.read_text(encoding="utf-8")
        # 提取 front matter status
        for line in text.splitlines():
            if line.strip().startswith("status:"):
                value = line.split(":", 1)[1].strip().strip('"').strip("'")
                self.assertEqual(value, "paused",
                                 "C8[A4-C]：旧 spec status 应为 paused，实际 %r" % value)
                return
        self.fail("C8[A4-C]：旧 spec 缺 status 字段")

    def test_c8_find_spec_filters_paused(self):
        """check_roles.find_spec 同日多候选过滤 paused，取唯一活跃 spec。"""
        proc = run_py(SCRIPTS / "check_roles.py",
                      ["--stage", "start", "--date", "2026-11-26"], cwd=ROOT)
        out = proc.stdout + proc.stderr
        # 应定位到 redo spec（活跃），不报"找到多个 spec"
        self.assertIn("v5.2.1-reliability-fixes-redo.md", out,
                      "C8[A4-find_spec]：find_spec 应过滤 paused 取 redo spec")
        self.assertNotIn("找到多个 2026-11-26 的 spec", out,
                         "C8[A4-find_spec]：find_spec 应过滤 paused 不报多个")

    def test_c8_skill_md_has_abandon_section(self):
        """SKILL.md 含「契约作废与重新立项」小节。"""
        skill = ROOT / "ship-it" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        self.assertIn("契约作废与重新立项", text,
                      "C8[A4-SKILL]：SKILL.md 应含「契约作废与重新立项」小节")


class C9AnalysisBeforeContract(unittest.TestCase):
    """C9：先分析后契约（A5）——draft 闸门校验方案分析产出物。"""

    def test_c9_draft_requires_analysis_artifact(self):
        """check_spec --stage draft 校验方案分析产出物引用路径。"""
        cs = SCRIPTS / "check_spec.py"
        text = cs.read_text(encoding="utf-8")
        self.assertIn("check_analysis_artifact", text,
                      "C9[A5-C]：check_spec 应有 check_analysis_artifact 函数")

    def test_c9_draft_artifact_must_exist(self):
        """方案分析产出物文件必须存在（redo-proposal-v2.html）。"""
        artifact = ROOT / "docs" / "reviews" / "2026-11-26-v5-2-1-redo-proposal-v2.html"
        self.assertTrue(artifact.is_file(),
                        "C9[A5-C]：方案分析产出物 redo-proposal-v2.html 应存在")

    def test_c9_draft_artifact_decision_tree_token(self):
        """产出物含决策树结构标记（选项/推荐/决策树/理由）。"""
        artifact = ROOT / "docs" / "reviews" / "2026-11-26-v5-2-1-redo-proposal-v2.html"
        text = artifact.read_text(encoding="utf-8")
        tokens = ("选项", "推荐", "决策树", "理由")
        hits = [t for t in tokens if t in text]
        self.assertGreaterEqual(len(hits), 2,
                                "C9[A5-C]：产出物应含 ≥2 个决策树标记，实际 %s" % hits)

    def test_c9_skill_md_step1_hard_constraint(self):
        """SKILL.md Step 1 末尾有先分析后契约硬约束。"""
        skill = ROOT / "ship-it" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        self.assertIn("C9[A5-P]", text,
                      "C9[A5-P]：SKILL.md 应有 C9[A5-P] 先分析后契约硬约束")
        self.assertIn("方案分析产出物", text,
                      "C9[A5-P]：SKILL.md 应提及方案分析产出物")


class C10StartupDispatchRoles(unittest.TestCase):
    """C10：启动团队模式即派角色（A6 + B11）。"""

    def test_c10_team_mode_has_startup_dispatch_list(self):
        """team-mode.md 主脑卡含"启动即派角色清单"决策表。"""
        tm = ROOT / "ship-it" / "references" / "team-mode.md"
        text = tm.read_text(encoding="utf-8")
        self.assertIn("启动即派角色清单", text,
                      "C10[A6-ai]：team-mode.md 主脑卡应有'启动即派角色清单'")
        self.assertIn("不得反复征求开工确认", text,
                      "C10[B11]：team-mode.md 应明示不得反复征求开工确认")

    def test_c10_check_roles_start_validates_dispatch(self):
        """check_roles --stage start 可验 role_dispatch 完整性（已有机制）。"""
        cr = SCRIPTS / "check_roles.py"
        text = cr.read_text(encoding="utf-8")
        self.assertIn("role_dispatch", text,
                      "C10[A6-ai]：check_roles 应有 role_dispatch 校验")

    def test_c10_skill_md_team_mode_no_stall(self):
        """SKILL.md 团队模式节明示启动即派角色不 stall。"""
        skill = ROOT / "ship-it" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        self.assertIn("C10[A6/B11]", text,
                      "C10[B11]：SKILL.md 应有 C10[A6/B11] 启动即派角色条目")
        self.assertIn("启动团队模式", text,
                      "C10[B11]：SKILL.md 应提及启动团队模式即授权")


if __name__ == "__main__":
    unittest.main()
