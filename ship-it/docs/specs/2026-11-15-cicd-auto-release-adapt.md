# 2026-11-15 CI/CD 自动发布通道适配 — spec 契约

> **本文件是需求的唯一事实来源（single source of truth）。**
> 在 Step 2 填写完毕、**用户确认 = 签约** 后才进入编码。
> 编码、测试、验收、PR 全部从本文件派生；需求变更先改本文件，再改代码（spec-first）。

---

## 1. 背景与目标（what & why）

用户已在实际项目（Resume-xianzhe.zhao）上用 GitHub Actions + 自托管 Runner 实现了 CI/CD 自动发布：test 分支→测试环境（自动部署）、main 分支→生产环境（PR 合并后自动部署）、main 开分支保护（require PR + required status checks）。而 ship-it skill v4.1.0 的全部部署相关内容（Step 4 部署测试系统、Step 6 用户验收、Step 8 发布正式系统、回滚预案、常见坑表、runbook 适配清单）都假设"agent 手动/脚本部署"，全文仅 1 处提到 CI/CD（判断系统形态时查文档）。改完之后：skill 在 CI/CD 自动发布模式下有明确、可核销的执行路径（推分支触发→等流水线完成→核对版本→才回归/验收；合并即发布；回滚走 git revert 重部署），且不影响手动部署项目的既有指引。

### 需求澄清记录（Step 1 产出，签约时展示给用户确认）

- **原始需求**：「我已经在Git 利用自动发布的runner 实现了CICD的自动发布。你可以查看记忆。然后你帮我查看一下这个项目的skill工作流是否需要变更或者更新。」
- **优化后需求**：审查 ship-it skill（v4.1.0）工作流与"GitHub Actions + 自托管 Runner 分支→环境自动发布"模式的差距，按审查结论 G1–G6 更新 skill：在系统形态判定、Step 4、Step 6、Step 8、常见坑表、project-adaptation.md 适配清单中加入 CI/CD 自动发布通道，版本号 4.1.0 → 4.2.0。
- **优化说明**：①读取 DSH 记忆 `~/.dsh/memory/ci-cd-setup.md` 确认 CI/CD 实际形态（双分支隔离、PM2、分支保护）；②grep 盘点 skill 全部部署相关触点（65 处命中，逐节核对）；③产出 6 处缺口 G1–G6 并与用户确认范围。
- **用户问答**：问「接下来怎么处理？」→ 答「走完整 spec 并实施（推荐）」；问「改动范围口径？」→ 答「SKILL.md + project-adaptation.md（推荐），一起进一个 PR」。

## 2. 方案自审（怎么做）

- **复用盘点**（实际查过）：`ship-it/SKILL.md` 前置「判断系统形态」表（L32–38）、Step 4「部署测试系统 + 跑回归」（L271–278）、Step 6 汇报 5 项（L323 附近）、Step 8 回滚预案表与服务类安全规则（L392–429）、常见坑表（L485–492）、`ship-it/references/project-adaptation.md` 逐项替换清单（L68–75）与接入检查清单（L100–107）、`ship-it/CHANGELOG.md`、SKILL.md frontmatter version: 4.1.0。仓库无 CLAUDE.md/AGENTS.md/runbook，skill 即流程真源。
- **决策**：B 扩展 —— 现有结构约 80% 满足（9 步骨架、闸门、「合并前不碰生产」红线全部保留且更贴切），在既有小节内加"部署通道"条件分支与新增表格行，保持向后兼容（无 CI/CD 项目不受影响）。
- **影响面**：仅 `ship-it/SKILL.md`、`ship-it/references/project-adaptation.md`、`ship-it/CHANGELOG.md` 三个文档文件；无页面/接口/表/配置/缓存变化；README.md 的 9 步流程表与核心机制节描述不与新内容冲突（描述的是步骤与闸门，不含部署通道细节）。
- **兼容性**：无接口/数据/配置影响；新增内容均为条件分支（"项目部署通道为 CI/CD 自动发布时"），手动部署指引原样保留。
- **成本预算**：无（纯文档，不涉及 LLM/付费 API）。
- **安全增量**：无新增依赖、无新外部输入面（纯 Markdown 文档变更）。本仓库自上次周期审查以来无攻击面变化。
- **测试策略**：①`check_spec.py --stage spec` / `--stage verify` 退出码 0；②每条 C 条款一个验证用例（文本断言：关键新增内容存在且位置正确）；③回归：手动部署指引、三形态表、9 步闸门、既有常见坑行不丢失（grep 断言）；④frontmatter version 与 CHANGELOG 一致性断言。

## 3. 技术蓝图（按涉及领域填，不涉及写"无变更"）

- **前端**：无变更（本仓库为 skill 文档，无页面）。
- **后端**：无变更（无代码/脚本逻辑；`scripts/check_spec.py` 不动）。
- **数据库**：无变更。
- **环境依赖**：无变更（不新增依赖/服务/配置；新增内容只引用 `gh run watch`、`gh run list` 等 GitHub CLI 命令作为示例，不作为硬依赖）。

## 4. 非目标（out of scope）

- 不做：不修改用户的 Resume 项目或其 `ci-deploy.sh`（`|| true` 吞错误码风险已单独提醒用户，属项目层面）。
- 不做：不改动 9 步骨架的顺序、闸门与"合并前不碰生产"红线。
- 不做：不新建独立的 references 文档（CI/CD 通道内嵌进 SKILL.md 既有小节，避免文件蔓延）。
- 不做：不改 `check_spec.py`、`spec-template.md`、`team-mode.md`、`self-check.md`、`security-review.md`。
- 不做：不在 skill 中写死具体项目值（Resume 的 IP/端口/PM2 进程名一律不出现，只写通用模式 + 占位说明）。

## 5. 契约条款（C1 / C2 / …）

### C1 系统形态判定新增部署通道维度

- **前置条件**：SKILL.md 前置「判断系统形态」节存在；项目侧信息源为项目文档与流水线配置文件（`.github/workflows/`、`.gitlab-ci.yml` 等）。
- **后置条件**：该节在"有无测试/正式系统"之外新增"部署通道"判定：手动/脚本部署 vs CI/CD 自动发布；判定依据写明"查项目文档与流水线配置文件中分支→环境的部署映射"；CI/CD 模式下要求把 分支→环境→workflow 名 的映射记入项目 `docs/deploy-runbook.md`。
- **失败行为**：文档与流水线文件均无法判定部署通道时，要求直接问用户，不得默认假设任一通道。
- **不变式**：原有三种系统形态行（单系统/有测试环境/测试+正式）及其 Step 4/Step 8 列引用不删除、不改变含义。

### C2 Step 4 部署测试系统补 CI/CD 通道与回归时序

- **前置条件**：项目部署通道为 CI/CD 自动发布，且项目有测试环境（对应分支推送即触发测试环境部署）。
- **后置条件**：Step 4「部署测试系统」小节含 CI/CD 通道完整序列：推送对应分支触发部署 → 等待 workflow 结束且结论为 success（给出 `gh run watch` / `gh run list` 查询方式）→ 核对线上版本或产物与待测 commit 一致 → 才开始跑分级回归。
- **失败行为**：workflow 失败、被取消或长时间未结束（含 runner 掉线卡 queued）→ 遇阻即停、排查流水线；禁止手动部署绕过（会造成环境与 git 状态漂移，且下次自动部署会覆盖手工改动）；此禁止写入正文。
- **不变式**：手动/脚本部署指引（"用项目既有部署脚本"与原子换目录要点）原样保留，作为非 CI/CD 项目的通道。

### C3 Step 6 验收前的部署完成确认

- **前置条件**：项目部署通道为 CI/CD 自动发布，用户验收在自动部署的测试环境上进行。
- **后置条件**：Step 6 汇报中要求：通知用户"测试环境已更新"之前，必须确认 workflow 结论为 success 且线上版本与待验收 commit 一致；汇报模板含部署状态（workflow 结论/run 标识）一行。
- **失败行为**：workflow 未成功或线上版本与待验收 commit 不一致 → 不得通知用户验收，先回到部署环节修复；含糊时主动询问用户。
- **不变式**：Step 6 汇报必含的 5 项（重点变更/验收清单/测试步骤/回滚方式/明确请求）不减少。

### C4 Step 8 发布与回滚预案补 CI/CD 变体

- **前置条件**：项目部署通道为 CI/CD 自动发布，生产发布由 main 分支合并自动触发。
- **后置条件**：Step 8 含：合并 PR 即触发生产部署（与「合并前不碰生产」红线衔接：合并是发布动作本身）；watch workflow 成功后执行既有端到端验证 5 条；回滚预案表新增 CI/CD 变体列或行——当前生产版本记录为 main 上的 commit/部署 run、上次可用产物记录为上一个成功部署的 run 或 release、回滚动作为 `git revert` 后推回 main 触发自动重新部署（或重跑旧 workflow run）。
- **失败行为**：发布 workflow 失败 → 停止并排查流水线；禁止直接手改服务器文件回滚（下次自动部署会冲掉手工改动、造成真源漂移），如确需应急手工介入，须事后把变更以 commit 形式补回 main 并注明。
- **不变式**：「合并前不碰生产」红线、端到端验证 5 条（服务状态/源站健康/对外入口/产物 hash 对比/入口资源可达）、"耗时不能作为部署失败判据"提醒均保留不删。

### C5 常见坑表新增 CI/CD 三个坑

- **前置条件**：SKILL.md「常见坑」表存在且现有 9 行。
- **后置条件**：新增 3 行：①workflow 未完成就跑回归 → 测的是旧版本、假通过（对策：等结论 success + 版本核对）；②为消流水线警告给命令加 `|| true` → 真失败被吞成成功退出码（对策：根治警告或把吞错范围缩到单条已知无害命令）；③手动改服务器救火 → 与 git 真源漂移、下次部署被冲掉（对策：一切变更走 git 提交触发重部署）。
- **失败行为**：任一行缺失、或行内只有"表现"没有"对策" → 本条款未达成。
- **不变式**：既有 9 行坑不删除、不改变含义；表格三列结构（坑/表现/对策）不变。

### C6 project-adaptation.md 适配清单补 CI/CD 项

- **前置条件**：`references/project-adaptation.md` 的「逐项替换清单」与「检查清单（新项目接入时逐条过）」存在。
- **后置条件**：逐项替换清单新增：部署通道与 分支→环境→workflow 映射（含 runner 形态）、CI/CD 回滚方式（revert 重部署）、workflow 状态查询命令；接入检查清单新增对应一条（runbook 是否记录了分支→环境映射与 CI/CD 回滚方式）。
- **失败行为**：两份清单任一处未加对应项 → 本条款未达成。
- **不变式**：两层落地结论、「不要第二份流程 skill」、编号对齐、保密脱敏规则不变；runbook 不写凭据的纪律适用于 workflow 中引用的密钥（写"见服务器/流水线密钥配置"）。

### C7 版本号与变更记录

- **前置条件**：SKILL.md frontmatter `version: 4.1.0`；`ship-it/CHANGELOG.md` 顶部为 v4.1.0 记录。
- **后置条件**：SKILL.md version 升为 4.2.0（新能力 = minor）；`ship-it/CHANGELOG.md` 顶部新增 v4.2.0 记录，含变更摘要（CI/CD 自动发布通道：形态判定/Step 4/6/8/常见坑/适配清单）。
- **失败行为**：version 与 CHANGELOG 记录的版本号不一致，或 CHANGELOG 无 v4.2.0 条目 → 本条款未达成。
- **不变式**：SemVer 规则遵循（非破坏性新增能力 → minor 递增）。

## 6. 验收标准（用户逐条打勾）

- [ ] A1 SKILL.md「判断系统形态」节可看到"部署通道"判定（含查流水线配置文件的依据、CI/CD 时记入 runbook 的要求、无法判定时问用户），且原有三形态表行未变。
- [ ] A2 Step 4 部署测试系统含 CI/CD 序列（推分支触发 → 等 workflow success → 版本核对 → 才跑回归；失败遇阻即停且禁止手动绕过），手动部署指引原样保留。
- [ ] A3 Step 6 要求在确认 workflow 成功且线上版本一致后，才通知用户"测试环境已更新"，汇报含部署状态行；5 项汇报内容未减少。
- [ ] A4 Step 8 含"合并 PR 即触发发布"、watch workflow 后执行端到端验证 5 条；回滚预案表含 CI/CD 变体（git revert 重部署），并禁止手改服务器回滚。
- [ ] A5 常见坑表新增 3 行（旧版本假通过 / `|| true` 吞错误码 / 手改服务器漂移），既有 9 行未删改。
- [ ] A6 project-adaptation.md 的逐项替换清单与接入检查清单各含 CI/CD 对应项。
- [ ] A7 SKILL.md frontmatter version 为 4.2.0，ship-it/CHANGELOG.md 顶部有 v4.2.0 记录且版本一致。

## 7. 边界与异常

| 场景 | 期望表现 |
|---|---|
| 项目无 CI/CD（纯手动/脚本部署） | 新增内容均以"部署通道为 CI/CD 时"为条件，不触发；手动指引不受影响 |
| 流水线文件存在但无部署 job（仅跑测试） | 不判定为 CI/CD 自动发布通道；存疑时问用户，不假设 |
| workflow 长时间不结束（runner 掉线卡 queued） | 按失败处理：遇阻即停、排查，不跑回归、不通知用户验收 |
| 流水线结论为 failure/cancelled | 同失败处理；禁止手动部署绕过 |
| 多环境多 workflow（测试/正式/其他 job 并存） | 以 runbook 记录的 分支→环境→workflow 映射为准，不猜 |
| 应急时已手工介入服务器 | 事后必须把变更以 commit 补回 main 并注明，消除真源漂移 |

## 8. 三问完整性检查 + DoR（不过不得开工）

- [x] ① **取值范围**：部署通道为二值枚举（手动/脚本 vs CI/CD 自动）；workflow 结论枚举（success/failure/cancelled/进行中）；版本号符合 `\d+\.\d+\.\d+`；条款/验收/坑行编号均连续可正则校验。
- [x] ② **状态流转**：CI/CD 下发布流程可画成状态机——推分支 → workflow running → success → 版本核对 → 回归/验收 → 合并 main → 生产 workflow running → success → 端到端验证；任一节点 failure/cancelled → 遇阻即停（回到排查），guard = 禁止手动绕过与手改服务器。
- [x] ③ **生成逻辑**：每处新增文本均可一句话描述（形态表加一维判定；Step 4 加部署序列；Step 6 加确认前置；Step 8 加回滚变体；坑表加 3 行；两份清单各加 CI/CD 项；版本与 CHANGELOG 同步）。

**DoR 自检**（Definition of Ready）：需求无歧义 ☑、技术可行 ☑、影响面已盘 ☑

---

## 9. 核销记录（Step 5 填写，PR 里引用）

| 条款 | 测试用例 | 结果 | 路径真实性 |
|---|---|---|---|
| C1 | `test_c1_channel_detection` | ✅ | 文本断言（脚本 grep + 逐节核对） |
| C2 | `test_c2_step4_sequence` | ✅ | 文本断言（脚本 grep + 序列顺序核对） |
| C3 | `test_c3_step6_confirm` | ✅ | 文本断言（脚本 grep + 逐节核对） |
| C4 | `test_c4_step8_rollback` | ✅ | 文本断言（脚本 grep + 逐节核对） |
| C5 | `test_c5_pitfalls` | ✅ | 文本断言（表格列解析核对） |
| C6 | `test_c6_adaptation_lists` | ✅ | 文本断言（脚本 grep + 逐节核对） |
| C7 | `test_c7_version_changelog` | ✅ | 文本断言（正则 + 版本一致性核对） |

- 核销率：7/7；测试脚本 `tmp/test_cicd_adapt.py`（一次性，Step 9 删除）：TOTAL 66 / PASS 66 / FAIL 0，退出码 0
- 分级回归：轻量冒烟（不触及核心功能）——手动部署指引（既有脚本用法 + 原子换目录要点）、三形态表三行、Step 6 五项汇报、Step 8 端到端验证 5 条与「合并前不碰生产」、常见坑既有 9 行、"两层落地/不要第二份流程 skill"结论：grep 断言全部保留 PASS
- 影响面（来自第 2 节）：SKILL.md / project-adaptation.md / CHANGELOG.md 三个文档文件
