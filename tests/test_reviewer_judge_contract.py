#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.6.0 契约测试：代码安全员 / 审查员 / 裁判员 / 角色按需启用矩阵 / 主动巡视。

测试从 spec 派生，不从实现派生：
  docs/specs/2026-11-18-reviewer-judge-roles.md（C1–C23 / A1–A22）
运行：
  Step 4：python -m unittest tests.test_reviewer_judge_contract -v
  Step 5（回填 §9 后）：SHIP_IT_VERIFY=1 python -m unittest tests.test_reviewer_judge_contract -v
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "specs" / "2026-11-18-reviewer-judge-roles.md"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"')
    return data


def run_check_spec(spec: Path, stage: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "ship-it" / "scripts" / "check_spec.py"), str(spec), "--stage", stage],
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


class ReviewerJudgeContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.team = read("ship-it/references/team-mode.md")
        cls.skill = read("ship-it/SKILL.md")
        cls.readme = read("README.md")
        cls.runbook = read("docs/deploy-runbook.md")
        cls.template = read("ship-it/references/spec-template.md")
        cls.security_kb = read("ship-it/references/security-kb.md")
        cls.changelog_root = read("CHANGELOG.md")
        cls.changelog_skill = read("ship-it/CHANGELOG.md")
        cls.spec = SPEC.read_text(encoding="utf-8")

    # C1 角色分工、改名与删除改动说明员
    def test_c1_role_division(self) -> None:
        for role in ("代码安全员", "审查员（异常与偷懒审查）", "裁判员", "测试员"):
            self.assertIn(role, self.team)
        self.assertIn("代码安全员", self.skill)
        self.assertIn("审查员（异常与偷懒审查）", self.skill)
        self.assertIn("改动说明员已删除", self.skill + self.readme)
        self.assertNotIn("### 改动说明员", self.team)
        self.assertNotIn("| 改动说明员 |", self.team)
        self.assertNotIn("### 代码审查员", self.team)
        cards = re.findall(
            r"^### (主脑（会话本身）|需求澄清员|后端开发|前端开发|代码安全员|审查员（异常与偷懒审查）|裁判员|测试员)$",
            self.team,
            re.MULTILINE,
        )
        self.assertEqual(len(cards), 8, f"角色卡应为 8 张，实际 {cards}")
        self.assertIn("安全相关重复接口", self.team)
        self.assertIn("团队模式必执行", self.team)

    # C2 审查员触发条件与失败分类
    def test_c2_reviewer_trigger_classes(self) -> None:
        for cls in (
            "dispatch_failed",
            "timeout",
            "empty_output",
            "meta_only",
            "unreachable_clause",
            "tool_denied",
            "context_overflow",
            "laziness",
            "suspected_drift",
        ):
            self.assertIn(f"`{cls}`", self.team)
        self.assertIn("明显偷懒", self.team)
        self.assertIn("`failure_class` 为 9 个固定枚举", self.spec)

    # C3 审查员输出、只读与指令边界
    def test_c3_reviewer_direct_order_boundary(self) -> None:
        self.assertIn("直接向子代理发 `continue` / `retry_same`", self.team)
        self.assertIn("`continue` → 审查员直发", self.team)
        self.assertIn("`continue` → 审查员直发", self.spec)
        self.assertIn("换模型 / 换 prompt / 缩范围 / 新派发 / 续派剩余部分交主脑", self.team)
        self.assertIn("只审不裁", self.team)
        self.assertIn("只读", self.team)

    # C4 审查员升级阈值与尝试计数
    def test_c4_escalation_threshold(self) -> None:
        self.assertIn("初次 + 最多 2 次重试 = 共 3 次尝试", self.team)
        self.assertIn("第 3 次失败", self.team)
        self.assertIn("尝试次数", self.team)
        self.assertIn("总尝试 ≤3", self.team)

    # C5 主脑决策集与重派/续派规则
    def test_c5_main_decision_set(self) -> None:
        for kw in ("换模型重派", "换 prompt / 缩范围重派", "基于已有产出续派剩余部分", "主脑不得自做", "报用户"):
            self.assertIn(kw, self.team)
        self.assertIn("派发失败", self.team)
        self.assertIn("执行失败", self.team)
        self.assertIn("审计角色例外", self.team)

    # C6 裁判员规则源与检查点
    def test_c6_judge_rules_and_checkpoints(self) -> None:
        for kw in ("J1 签约前", "J2 编码后", "J3 核销前", "J4 验收前"):
            self.assertIn(kw, self.team)
        for kw in ("用户约束", "AGENTS.md", "agent 目录", "任务树", "未找到"):
            self.assertIn(kw, self.team)
        self.assertIn("本仓库根**无** `AGENTS.md`", self.team)

    # C7 裁判员输出与效力
    def test_c7_judge_verdict_power(self) -> None:
        for kw in ("BLOCK", "PASS", "不替代", "check_spec.py", "≤2 轮", "非最终裁定"):
            self.assertIn(kw, self.team)
        self.assertIn("裁判员不是最终裁定者", self.team)

    # C8 证据口径与后台可见性声明
    def test_c8_evidence_visibility(self) -> None:
        for kw in ("后台可见性", "完整 / 降级 / 不可见", "evidence_missing", "禁止声称"):
            self.assertIn(kw, self.team)
        self.assertIn("path:line", self.team)

    # C9 反偷懒/反越权检查表 + 主脑时序/子代理越权检查
    def test_c9_redline_and_timing_checklist(self) -> None:
        for kw in ("19 条", "反偷懒 4", "反越权 7", "主脑时序 3", "子代理越权/偷懒 5", "明显偷懒"):
            self.assertIn(kw, self.team)
        self.assertIn("B1", self.team)
        self.assertIn("B2", self.team)
        self.assertIn("B3", self.team)

    # C10 与 9 步流程、既有闸门和角色的关系
    def test_c10_nine_steps_unchanged(self) -> None:
        headings = re.findall(r"^## Step (\d+)", self.skill, re.MULTILINE)
        self.assertEqual(sorted({int(h) for h in headings}), list(range(1, 10)))
        self.assertNotIn("## Step 10", self.skill)
        self.assertIn("用户验收", self.skill)
        self.assertIn("check_spec.py", self.skill)
        self.assertIn("主脑汇总团队产出", self.team + self.skill)

    # C11 文档同步、版本 4.7.0 与 skill 正文零模型名
    # C12/A12：v4.7.0 三处版本同步（4.6.0 → 4.7.0）
    def test_c11_version_and_sync(self) -> None:
        meta = frontmatter(self.skill)
        self.assertEqual(meta.get("version"), "4.7.1")
        for rel in ("CHANGELOG.md", "ship-it/CHANGELOG.md"):
            self.assertIn("4.7.1", read(rel))
        for kw in ("代码安全员", "审查员（异常与偷懒审查）", "裁判员"):
            self.assertIn(kw, self.readme)
        self.assertIn("监督规则源", self.runbook)
        self.assertIn("用户约束（裁判员规则源）", self.template)
        self.assertIn("裁判员", self.template)
        model_re = re.compile(
            r"(?i)(deepseek[-_ ]?v?\d|glm[-_ ]?\d|qwen\d|bailian-tpp|aipro/|kimi[-_ ]?k?\d|gpt-\d|gemini[-_ ]?\d)"
        )
        for rel in ("ship-it/SKILL.md", "ship-it/references/team-mode.md"):
            self.assertIsNone(model_re.search(read(rel)), f"{rel} 出现具体模型名")
        # 反越权红线 #6 与派发预检同口径（防回归）
        self.assertIn("派发失败", self.skill)
        self.assertIn("审计角色例外", self.skill)

    # C12 降级与关闭开关
    def test_c12_degrade_switch(self) -> None:
        self.assertIn("审查员（异常与偷懒审查）派发失败/超时", self.team)
        self.assertIn("不得自判 PASS", self.team)
        self.assertIn("单干 / mini-spec", self.team)
        self.assertIn("4.5.0", self.team)

    # C13 角色按需启用矩阵与可选专项能力
    def test_c13_role_activation_matrix(self) -> None:
        for form in ("0 单干", "1 小改", "2 中改", "3 大改/高风险"):
            self.assertIn(form, self.team)
        self.assertIn("全部 8 角色", self.team)
        self.assertIn("代码安全员、审查员、裁判员", self.team)
        self.assertIn("**需求澄清员**：按需", self.team)
        self.assertIn("**测试员**：团队模式形态 1–3 必执行", self.team)
        self.assertIn("**前后端开发**：只派相关侧", self.team)
        self.assertIn("深度安全审计", self.team)
        # 形态 1 的「必派」列必须含裁判员（J2-06 回归）
        form1 = next(line for line in self.team.splitlines() if line.startswith("| **1 小改**"))
        cells = [c.strip() for c in form1.strip().strip("|").split("|")]
        self.assertIn("裁判员", cells[2], f"形态 1 必派列缺裁判员：{cells}")
        # Step 1 澄清员必须写「按需」
        self.assertIn("**按需**派**需求澄清员**", self.skill)

    # C14 审查员主动巡视协议
    def test_c14_reviewer_patrol(self) -> None:
        self.assertIn("间隔 1 分钟", self.team)
        self.assertIn("主动巡视", self.team)
        self.assertIn("主脑不持续轮询", self.team)
        self.assertIn("事件触发巡视", self.team)
        self.assertIn("无主动定时巡视", self.team + self.skill + self.readme)
        self.assertIn("裁判员", self.team)
        self.assertIn("running / inactive / corrupt / unsupported / unavailable", self.team)
        self.assertIn("主脑证据包/看板快照", self.team)
        self.assertIn("5 分钟无审查员消息", self.team)
        self.assertIn("再次上报/唤醒主脑", self.team)
        self.assertIn("等待前先激活审查员", self.team)
        self.assertIn("每 5 分钟向用户发状态", self.team)
        self.assertIn("等待工具单次 ≤5 分钟", self.team)
        self.assertIn("超时先发状态", self.team)
        self.assertIn("`question`", self.team)
        self.assertIn("C14", self.spec)
        self.assertIn("A13", self.spec)
        self.assertIn("主脑不持续轮询", self.skill)

    # C15 裁判员不执行测试、不审代码，只审契约
    def test_c15_judge_no_test_execution(self) -> None:
        self.assertIn("不执行测试、不审代码", self.team)
        self.assertIn("代码审查+安全检查归代码安全员", self.team)
        self.assertIn("J2 只审流程/文档/自检", self.team)
        self.assertIn("安全检查归代码安全员", self.team)
        self.assertIn("J3/J4 在测试员验收测试、代码安全员代码审查+安全检查", self.team)
        self.assertIn("不执行测试", self.skill)
        self.assertIn("不执行测试", self.readme)
        self.assertIn("C15", self.spec)
        self.assertIn("A14", self.spec)

    # C16 信息流与循环升级顺序
    def test_c16_information_flow(self) -> None:
        for kw in (
            "用户 ↔ 主脑 ↔ 审查员",
            "主脑不直接等裁判员",
            "主脑唯一汇总接口",
            "测试员做验收测试",
            "代码安全员做代码审查",
            "安全检查",
            "裁判员审契约",
            "用户提问",
        ):
            self.assertIn(kw, self.team)
        self.assertIn("C16", self.spec)
        self.assertIn("A15", self.spec)

    # C17 代码安全员安全审查库与工具适配
    def test_c17_security_kb(self) -> None:
        kb = read("ship-it/references/security-kb.md")
        for kw in (
            "OSV",
            "GitHub Advisory",
            "NVD",
            "CISA KEV",
            "EPSS",
            "endoflife.date",
            "SonarQube",
            "Semgrep",
            "CodeQL",
            "Trivy",
            "gitleaks",
            "OWASP",
            "CWE",
            "来源 URL",
            "查询日期",
            "未联网核验",
            "token",
            "SonarQube 未接入",
        ):
            self.assertIn(kw, kb)
        self.assertIn("security-kb.md", self.team)
        self.assertIn("security-kb.md", self.skill)
        self.assertIn("security-kb.md", self.readme)
        self.assertIn("C17", self.spec)
        self.assertIn("A16", self.spec)

    # C18 执行中需求变更 / 重签约协议
    def test_c18_midflight_resign(self) -> None:
        for kw in (
            "执行中需求变更",
            "重新签约",
            "暂停所有子智能体",
            "盘点进度",
            "不跑旧契约",
            "继续/重派",
            "受影响闸门重跑",
        ):
            self.assertIn(kw, self.team)
        self.assertIn("C18", self.spec)
        self.assertIn("A17", self.spec)
        self.assertIn("执行中需求变更", self.skill + self.readme)

    # C19 角色边界与设计/测试标准
    def test_c19_role_boundary_design_standards(self) -> None:
        for kw in (
            "代码审查**（正确性 / 质量 / 注释 / 重复功能）+ **安全检查",
            "**只做验收测试**",
            "`design.md`",
            "后端标准 + 数据库标准",
            "团队模式形态 1–3 **必须执行**",
            "主脑必须自测",
        ):
            self.assertIn(kw, self.team)
        self.assertIn("C19", self.spec)
        self.assertIn("A18", self.spec)
        self.assertNotIn("代码审查（正确性/质量/注释/重复功能）归测试员", self.team)
        docs = (
            self.skill
            + self.readme
            + self.runbook
            + self.template
            + self.security_kb
            + self.changelog_root
            + self.changelog_skill
        )
        self.assertNotIn("代码审查归测试员", docs)
        self.assertNotIn("测试员条件必要", docs)
        self.assertNotIn("测试执行与代码审查归测试员", docs)
        self.assertNotIn("测试员测试+代码审查", docs)
        self.assertNotIn("由测试员测试后审查", docs)
        self.assertIn("只做验收测试", self.skill)

    # C20 审查员图像审查与测试执行环境
    def test_c20_image_and_test_environment(self) -> None:
        for kw in (
            "图像审查",
            "临时识图子智能体",
            "Windows/macOS",
            "浏览器",
            "截图",
            "Playwright",
        ):
            self.assertIn(kw, self.team)
        self.assertIn("C20", self.spec)
        self.assertIn("A19", self.spec)

    # C21 契约互审与质疑
    def test_c21_contract_cross_review(self) -> None:
        for kw in (
            "契约互审",
            "至少 1 轮",
            "汇总前反问",
            "至少提出 1 个质疑/反问",
            "主脑可反向质疑",
            "未解决疑问不得向用户呈现",
            "主脑第一版契约后自审",
            "前瞻性",
            "可维护性",
            "可扩展性",
            "不要等实现完",
            "语气友善",
        ):
            self.assertIn(kw, self.team)
        self.assertIn("C21", self.spec)
        self.assertIn("A20", self.spec)

    # C22 作者署名与商用说明
    def test_c22_author_attribution(self) -> None:
        for text in (self.readme, self.skill, self.team):
            self.assertIn("971554652@qq.com", text)
            self.assertIn("MIT", text)
            self.assertIn("8 年", text)
            self.assertIn("AI 产品架构师", text)
            self.assertIn("商用", text)
        self.assertIn("C22", self.spec)
        self.assertIn("A21", self.spec)

    # C23 审查员生命周期
    def test_c23_reviewer_lifecycle(self) -> None:
        for kw in (
            "契约生命周期",
            "不得主动结束",
            "inactive 不是结束标志",
            "下游",
            "PR 创建/Step 9 完成",
            "下游无任务",
            "换新审查员",
            "角色替换",
        ):
            self.assertIn(kw, self.team)
        self.assertIn("C23", self.spec)
        self.assertIn("A22", self.spec)
        self.assertIn("本次 dogfood 复盘", self.team)
        self.assertIn("逐文件小 commit push", self.team)
        self.assertIn("§9 在 tester/security 报告前预填", self.team)

    # 主脑是唯一用户对接人 / 不亲自开发测试审代码 / 5 分钟心跳
    def test_c10_main_brain_aggregator(self) -> None:
        for kw in ("唯一对用户交付", "不亲自开发/测试/审代码", "5 分钟无审查员消息"):
            self.assertIn(kw, self.team)
        self.assertIn("用户唯一对接人", self.skill)

    # 核心功能回归：frontmatter / 引用完整性
    def test_core_frontmatter_and_references(self) -> None:
        meta = frontmatter(self.skill)
        self.assertEqual(meta.get("name"), "ship-it")
        self.assertTrue(meta.get("description"))
        refs = set(re.findall(r"`(references/[A-Za-z0-9_.-]+\.md)`", self.skill))
        self.assertGreaterEqual(len(refs), 4)
        for rel in refs:
            self.assertTrue((ROOT / "ship-it" / rel).is_file(), f"缺少引用文件：{rel}")
        self.assertTrue((ROOT / "ship-it" / "scripts" / "check_spec.py").is_file())

    # 核心功能回归：check_spec.py 两阶段行为
    def test_core_check_spec_spec_stage(self) -> None:
        result = run_check_spec(SPEC, "spec")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        historical = ROOT / "docs" / "specs" / "2026-11-17-runtime-model-dispatch.md"
        result2 = run_check_spec(historical, "spec")
        self.assertEqual(result2.returncode, 0, result2.stdout + result2.stderr)

    # 核心功能回归：脚本语法 / build.ps1 BOM
    def test_core_scripts_parse(self) -> None:
        py = ROOT / "ship-it" / "scripts" / "check_spec.py"
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(py)],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        build = ROOT / "build.ps1"
        self.assertTrue(build.read_bytes().startswith(b"\xef\xbb\xbf"), "build.ps1 缺少 UTF-8 BOM")

    # 核销阶段：本 spec 的 check_spec --stage verify 必须退出码 0
    # Step 4 默认 skip（§9 尚未回填）；Step 5 回填后以 SHIP_IT_VERIFY=1 执行。
    @unittest.skipUnless(os.environ.get("SHIP_IT_VERIFY") == "1", "Step 5: 先回填 §9 再跑 verify")
    def test_spec_verify_exit_zero(self) -> None:
        result = run_check_spec(SPEC, "verify")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
