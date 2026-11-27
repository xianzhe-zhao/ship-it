---
spec_version: 2
name: 测试服务器分支策略增强
status: accepted
spec_revision: 1
hash_scope: sections_1_8_a_normalized
created_at: 2026-11-27T20:25:00+08:00
created_by: lead
sign_prompt: "刚才的说明可能造成误解：是否要签约？如果需要签约，请发送"签约"两个字才可以；不发送"签约"两个字，我不会开始编码。只发送这两个字，不要加标点、引号或其他内容。"
sign_requested_at: 2026-11-27T20:35:00+08:00
signed_by: lead
signed_at: 2026-11-27T20:37:14+08:00
sign_quote: 签约
sign_hash: 7187109d772f0fb4bced90d053dd6195beb29db857efc085c53f655bcf9b8091
confirmed_clauses: C1,C2,C3,C4
decisions: 分支策略=A, 判定方式=C
accept_prompt: "刚才的说明可能造成误解：是否需要验收？如果需要验收，请发送“验收”两个字才可以；不发送“验收”两个字，我不会进入 PR。只发送这两个字，不要加标点、引号或其他内容。"
accept_requested_at: 2026-11-27T22:10:00+08:00
accepted_by: lead
accepted_at: 2026-11-27T22:11:30+08:00
accept_quote: 验收
accept_commit: 54e560d5925d46e1f9a60974db9cc9bc3fc648aa
accepted_items: A1,A2,A3,A4,A5,A6,A7,A8
---

# 2026-11-27 测试服务器分支策略增强 — spec 契约

## 1. 背景与目标

当前 ship-it SKILL.md Step 7 流程只支持直接提 PR 到 `main`，但很多项目有测试服务器，需要先合并到 `test` 分支测试通过后再合并到 `main`。目标：增强 SKILL.md，支持"有测试服务器时先合并到 test"的场景。

### 需求澄清记录

- **原始需求**：用户说"虽然这个skill 项目测试的分支。但是其他项目肯定是有测试服务器的这个时候要先合并到test 这个内容也补充进去吧。然后提交PR"
- **优化后需求**：在 SKILL.md Step 7/8 加"测试服务器分支策略"——有测试服务器时先提 PR 到 `test`，测试通过后再提 PR 到 `main`
- **优化说明**：查了当前 SKILL.md Step 7/8 流程，确认只支持直接提 PR 到 main
- **用户问答（分轮决策清单）**：
  - R1：查验了分支策略和判定方式两个关键决策（详见方案分析 `docs/reviews/2026-11-27-test-server-branch-strategy-analysis.html`）→ 据此提问：用 ask_user_question 一次性问两个决策 → 用户答：A 先 test 后 main + C 查 runbook 判定
- **用户约束**：未找到（本项目无 AGENTS.md / runbook 红线）
- **决策展示记录**：两个决策已在 ask_user_question 完整列出，用户逐一选择
- **四零件清晰度自评**（C10）：角色 高、任务 高、背景 高、要求 高

## 2. 方案自审

### 2.1 复用盘点

既有 SKILL.md Step 7（版本号 + PR）和 Step 8（合并后发布正式系统）流程。

### 2.2 决策

**B 扩展**：在 SKILL.md Step 7/8 加"测试服务器分支策略"，不改既有流程，只在有测试服务器时启用新流程。放弃"重写 Step 7/8"的彻底解耦（没必要，只是加分支策略）。

### 2.3 解决方案

**方案 1：SKILL.md Step 7 加测试服务器分支策略**
- 修法：在 Step 7 加一段"测试服务器分支策略"，说明有测试服务器时先提 PR 到 `test`，测试通过后再提 PR 到 `main`
- 改动：`ship-it/SKILL.md` Step 7 节
- 为什么：当前流程只支持直接提 PR 到 main，需要支持有测试服务器的场景

**方案 2：判定方式查 runbook**
- 修法：Step 2 方案自审时查 `docs/deploy-runbook.md` 里有没有测试服务器配置
- 改动：`ship-it/SKILL.md` Step 2 节 + `ship-it/references/project-adaptation.md`
- 为什么：runbook 是项目配置的唯一事实源，查 runbook 最准确

**方案 3：方案分析产出物（必须）**
- 修法：生成 `docs/reviews/2026-11-27-test-server-branch-strategy-analysis.html`
- 改动：新增 HTML 文件
- 为什么：C9[A5-C] 要求方案分析产出物

**方案 4：可视化修复报告（必须）**
- 修法：生成 `docs/reviews/2026-11-27-test-server-branch-strategy-report.html`
- 改动：新增 HTML 文件
- 为什么：用户要求可视化报告

### 2.4 影响面

受影响文件：
- `ship-it/SKILL.md`：Step 7 加测试服务器分支策略
- `ship-it/references/project-adaptation.md`：加"测试服务器配置"检查项

不影响：`references/` 其他文档、`docs/specs/`、用户契约

入口清单：无 UI 变更

### 2.5 兼容性

无

### 2.6 成本预算

无

### 2.7 安全增量

无新增依赖/新外部输入面

### 2.8 测试策略

验收条件为本机 `tests.run_suite` 退出码 0；回归范围为既有测试全部通过

### 2.9 前端演示

N/A（无 UI 变更）

### 2.10 变更涉及的文件清单

ship-it/SKILL.md, ship-it/references/project-adaptation.md, docs/reviews/2026-11-27-test-server-branch-strategy-analysis.html, docs/reviews/2026-11-27-test-server-branch-strategy-report.html

### 2.11 降级声明

无可选能力缺失

### 2.12 执行形态/角色矩阵

形态 0 单干；必派 无；按需 无；未启用 团队模式（小范围修复）

### 2.13 闸门

开工前 `check_roles.py --stage start`（单干例外自测）；核销 `--stage verify`；验收 `--stage accept`

**流程规则**：

- **P1** 沿用 skill 默认流程

## 3. 技术蓝图

- **前端**：无变更
- **后端**：无变更
- **数据库**：无变更
- **环境依赖**：无变更

## 4. 非目标

- 不改既有 Step 7/8 流程（只在有测试服务器时启用新流程）
- 不改 SKILL.md 其他章节
- 不改 references/ 其他文档

## 5. 契约条款

### C1 SKILL.md Step 7 加测试服务器分支策略
- **前置**：项目有测试服务器（查 runbook 判定）
- **后置**：SKILL.md Step 7 说明有测试服务器时先提 PR 到 `test`，测试通过后再提 PR 到 `main`
- **失败**：SKILL.md 缺测试服务器分支策略说明
- **不变式**：既有流程不变，只在有测试服务器时启用新流程

### C2 判定方式查 runbook
- **前置**：项目有 `docs/deploy-runbook.md`
- **后置**：Step 2 方案自审时查 runbook 里有没有测试服务器配置
- **失败**：Step 2 没查 runbook 就判定有没有测试服务器
- **不变式**：runbook 是项目配置的唯一事实源

### C3 方案分析产出物（必须）
- **前置**：需求分析员完成问题分析与方案推导
- **后置**：`docs/reviews/2026-11-27-test-server-branch-strategy-analysis.html` 存在且包含决策树结构标记（选项/推荐/决策树/理由 ≥2 个）
- **失败**：`check_spec.py --stage draft` 报 C9[A5-C] 错误
- **不变式**：方案分析产出物是 spec 的附件，改动 = spec 改动 = 重新签约

### C4 可视化修复报告（必须）
- **前置**：修复完成后，生成可视化修复报告
- **后置**：`docs/reviews/2026-11-27-test-server-branch-strategy-report.html` 存在且包含分区清楚的 before/after 对比、逻辑流程图、每个改动的三要素（改了什么/为什么改/怎么验证）
- **失败**：报告文件不存在或缺少必要区块
- **不变式**：修复报告与契约条款一一对应（C1→区块1，C2→区块2...）

## 6. 验收标准

- [x] A1 SKILL.md Step 7 包含"测试服务器分支策略"说明
- [x] A2 判定方式查 runbook（`docs/deploy-runbook.md`）
- [x] A3 有测试服务器时先提 PR 到 `test`，测试通过后再提 PR 到 `main`
- [x] A4 没有测试服务器时沿用现有流程（直接提 PR 到 `main`）
- [x] A5 `references/project-adaptation.md` 加"测试服务器配置"检查项
- [x] A6 方案分析产出物存在且包含决策树结构标记
- [x] A7 可视化修复报告存在且包含分区清楚的 before/after 对比、逻辑流程图
- [x] A8 向上游提 PR（用户审核后合并）

## 7. 边界与异常

- 如果项目没有 `docs/deploy-runbook.md`，Step 2 方案自审时问用户有没有测试服务器
- 如果 runbook 里没写测试服务器配置，按"没有测试服务器"处理（直接提 PR 到 main）
- 如果 `test` 分支不存在，先创建 `test` 分支再提 PR

## 8. 三问完整性检查 + DoR

- [x] ① **取值范围**：分支名 `test|staging|main`；判定方式 `runbook|ask_user`
- [x] ② **状态流转**：不适用（改文档，不加状态）
- [x] ③ **生成逻辑**：判定 `has_test_server = check_runbook()`；分支策略 `if has_test_server: pr_to_test_then_main() else: pr_to_main()`

**DoR 自检**：需求无歧义 ☑、技术可行 ☑、影响面已盘 ☑

## 9. 核销记录

| 条款 | 用例名 | 用例文件 | 结果 | 路径真实性 |
|---|---|---|---|---|
| C1 | test_c1_test_server_branch_strategy | tests/test_process_gates.py | ✅ | 机器：python -m unittest tests.test_process_gates...test_c1_test_server_branch_strategy exit=0 |
| C2 | test_c2_detection_via_runbook | tests/test_process_gates.py | ✅ | 机器：python -m unittest tests.test_process_gates...test_c2_detection_via_runbook exit=0 |
| C3 | test_c3_analysis_deliverable | tests/test_process_gates.py | ✅ | 机器：docs/reviews/2026-11-27-test-server-branch-strategy-analysis.html 存在且包含决策树结构标记 |
| C4 | test_c4_visual_report | tests/test_process_gates.py | ✅ | 机器：docs/reviews/2026-11-27-test-server-branch-strategy-report.html 存在且包含分区清楚的 before/after 对比、逻辑流程图 |

- 测试报告：`docs/reviews/2026-11-27-test-server-branch-strategy-test-report.md`
- 核销率：4/4（100%）
- 分级回归：轻量冒烟通过（125 tests, 0 failures, 0 errors, 4 skipped；CI 四步闸门 PASS/SKIP exit=2）
