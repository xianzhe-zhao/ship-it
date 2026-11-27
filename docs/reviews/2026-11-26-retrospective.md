# 复盘记录 · v5.2.1-reliability-fixes 契约作废与重新立项

> 本记录为 A4「废弃契约流程」四步之「复盘」环节产物。回顾作废根因、过程教训、重做方案要点，供未来契约作废参照。

## 一、作废事件概述

| 字段 | 值 |
|------|-----|
| 作废 spec | `ship-it/docs/specs/2026-11-26-v5.2.1-reliability-fixes.md` |
| 作废时间 | 2026-11-26T16:40:00+08:00 |
| 作废发起 | 用户判定"改动根本没达到预期"，宣布契约作废 |
| 当时进度 | C1-C7 已实现并测试通过（25 用例），尚未验收 |
| 重新立项 | `ship-it/docs/specs/2026-11-26-v5.2.1-reliability-fixes-redo.md`（待落盘） |

## 二、作废根因（B1-B12 + A4/A5/A6）

### 实现层 Bug（B1-B6）

| 编号 | 问题 | 根因 |
|------|------|------|
| B1 | 反复签约 3 次 | 签约前未预跑 check_docs，spec 正文触发 STALE/DUP，sign_hash 反复失效 |
| B2 | C1 路径迁移漏盘测试 fixture | 影响面分析只扫脚本/CI，漏扫 tests/；test_v5_1_0_self_consistency.py 路径+版本号双重过期（7 failed） |
| B3 | C5 改术语漏改 check_text | 术语检测分散在 check_terms + check_text 两脚本，TERM_PAIRS 5 组硬编码未同步 |
| B4 | spec_flow front matter 格式与手填不一致 | spec_flow 复制字段定义，与 check_spec 常量漂移 |
| B5 | 核销表用例名与测试方法名不匹配 | reconcile 校验用例名存在性逻辑不够严格 |
| B6 | 核销表文本触发 check_docs STALE/计数检测 | check_docs 对 spec §9 核销表区域未豁免 DUP/STALE |

### 流程层缺口（B7-B12）

| 编号 | 问题 | 根因 |
|------|------|------|
| B7 | 反复催促（goal 续轮 vs 等用户输入） | harness goal 机制与等用户输入协调不当（归属全局 harness 纪律，不进 ship-it spec） |
| B8 | blocked 用得过滥 | harness blocked 状态误用，等用户输入≠技术死锁（同 B7 归属） |
| B9 | 未拍板就生成最终方案 HTML | 需求分析师未区分"分析+决策点"与"最终方案"两步（本轮已纠正） |
| B10 | 一次性扔给用户所有问题 | C7 校验分轮格式但未强化"一次只问一个"纪律 |
| B11 | 主脑没按工作流走（反复问"确认我开始吗"） | team-mode.md 主脑卡未明示"启动即派角色"强制性 |
| B12 | 方案分析与写契约搅在一起 | Step 1→Step 2 转换无硬约束"方案分析产出物未就绪不得落盘 spec" |

### 元规则缺失（A4/A5/A6）

| 编号 | 缺失规则 | 影响 |
|------|----------|------|
| A4 | 废弃契约流程未标准化 | 作废靠临时操作，无标准流程，无机器校验 |
| A5 | "先分析后契约"未固化 | 主脑可跳过方案分析直接落盘 spec（B12 即因此发生） |
| A6 | "启动团队模式即派角色"未明示 | 主脑把"启动团队模式"当需确认请求（B11 即因此发生） |

## 三、过程教训

1. **方案分析必须先于契约**：本次 spec 是别人写好交接的，没做方案分析就签了，实施中反复返工。教训：方案分析产出物（决策树 HTML）未就绪不得落盘 spec。
2. **签约前必须预跑 check_docs**：只跑 check_spec --stage draft 不够，spec 正文可能触发 STALE/DUP。教训：sign 前置三闸门（draft + docs + print-sign-hash dry-run）。
3. **影响面分析必须扫 tests/**：路径/前缀类改动只扫脚本/CI 会漏测试 fixture。教训：影响面 = 脚本 + CI + 文档 + 测试 fixture。
4. **术语检测必须单一入口**：分散在两脚本会导致改一处漏另一处。教训：长期收敛到 check_terms 单一入口。
5. **启动团队模式即授权**：用户说"启动团队模式"就等于授权派角色，主脑不该反复问"确认我开始吗"。
6. **一次只问一个最关键问题**：一次性抛多问题加重用户负担、决策混乱。
7. **等用户输入≠技术死锁**：blocked 仅限技术死锁，等用户输入不算（B7/B8 归属全局 harness 纪律）。
8. **改规则者受规则约束**：A4 改的是 ship-it 流程规则，本 spec 自身适用新规则——A4 这条规则本身也受"废弃契约流程"约束，自洽。

## 四、重做方案要点（D1-D9 锁定）

| 决策 | 锁定值 | 核心结论 |
|------|--------|----------|
| D1 | A | 废旧 spec + 重起 spec，C1-C7 作基线事实 |
| D2 | A | 按功能域分组，baseline+fix 合并入同一 C 条款（~10 条） |
| D3 | A | 每 bug 作后置条件子项，独立可验证，核销表每 bug 一行 |
| D4 | A | A4 双重形态：C 条款机器校验 + SKILL.md 小节 |
| D5 | A | A5 双重形态：C 条款 draft 闸门 + SKILL.md Step 1 硬约束 |
| D6 | A | A6 双轨：C 条款 ai+human 拆分 + SKILL.md/team-mode.md 明示 |
| D7 | A | B7/B8 属全局 harness 纪律，不进 ship-it spec |
| D9 | A | 旧 spec 原名置 paused + 新 spec -redo 后缀 + C8 扩展 find_spec |

新 spec 条款草案（10 条）：
- C1 spec 目录统一 + B2（影响面 grep tests/ + test_v5_1_0 改造）
- C2 版本动态读
- C3 spec_flow 一条命令 + B1（签约前三闸门）+ B4（import 常量）+ B5（reconcile 精确匹配）+ B6（核销表豁免）
- C4 local_check 本地复刻 CI
- C5 文档盲区 + B3（TERM_PAIRS 5 组改读词典）
- C6 解冻重跑
- C7 分轮可查 + B10（一次只问一个）
- C8 废弃契约流程标准化（A4 + find_spec 扩展）
- C9 先分析后契约（A5）
- C10 启动团队模式即派角色（A6 + B11）

## 五、保留资产

C1-C7 已实现代码作"基线事实"保留（不丢弃）：
- 脚本：spec_flow.py / local_check.py / check_docs.py / check_spec.py / check_terms.py / check_text.py / check_roles.py / pre_commit_check.py / check_writes_before_sign.py
- 词典：term-glossary.md（新建）
- 测试：tests/test_v5_2_1_reliability.py（25 用例）
- 配置：.github/workflows/ship-it-gates.yml
- 文档：SKILL.md（v5.2.1）/ CHANGELOG.md

待改造（B2 深化发现）：tests/test_v5_1_0_self_consistency.py（路径前缀 + EXPECTED_VERSION 改 5.2.1，保留改造不废弃）。

## 六、B7/B8 归属说明

B7（goal 续轮催促）、B8（blocked 滥用）属全局 harness 使用纪律，不进 ship-it spec（D7=A）：
- 守零耦合原则（voided spec §2 明确"不引入宿主依赖"）
- check_spec 验不了 goal/blocked，立 C 即 theater 假绿
- 全局 AGENTS.md 已是 harness 行为强制规范载体，补进去对所有会话/项目生效

本次留痕：本复盘 + memory-lesson。正式固化：另起全局 AGENTS.md 改动（独立 spec，"改规则者受规则约束"），由 lead 立 team_task 跟踪。

## 七、下一步

1. 落盘新 spec `ship-it/docs/specs/2026-11-26-v5.2.1-reliability-fixes-redo.md`（A4 第四步：重新立项）
2. 新 spec 经 security/judge 审查 + 用户签约后进入 Step 3 编码
3. 验收后 save_lesson 22+ 条入库（C8 式记忆沉淀）
4. B7/B8 正式固化另起 team_task（全局 AGENTS.md 改动）
