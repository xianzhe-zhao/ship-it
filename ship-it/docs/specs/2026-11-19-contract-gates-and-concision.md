---
spec_version: 2
spec_revision: 5
status: accepted
sign_prompt: "刚才的说明可能造成误解：是否要签约？如果需要签约，请发送“签约”两个字才可以；不发送“签约”两个字，我不会开始编码。只发送这两个字，不要加标点、引号或其他内容。"
sign_requested_at: "2026-11-19T17:30:00+08:00"
signed_by: "用户"
signed_at: "2026-11-20T07:40:29+08:00"
sign_quote: "签约"
sign_hash: "5d99c28ae23d6e56e11c59861c6305067ab32e2403f12de21756e0c0f63affe9"
confirmed_clauses: "C1-C18"
decisions: "D1=全量P0+P1+写作铁律; D2=精简SKILL/README/模板/本spec; D3=硬阻断; D4=不启用目标管理; D5=旧spec按日期兼容; D6=v4.7.0; D7=新增C14/C15审查员开工闸门; D8=新增C16契约变更暂停闸门; D9=新增C17失败分类与三次尝试; D10=新增C18全文一致性与去废话"
accept_prompt: "刚才的说明可能造成误解：是否需要验收？如果需要验收，请发送“验收”两个字才可以；不发送“验收”两个字，我不会进入 PR。只发送这两个字，不要加标点、引号或其他内容。"
accept_requested_at: "2026-11-20T08:10:00+08:00"
accepted_by: "用户"
accepted_at: "2026-11-20T08:11:30+08:00"
accept_quote: "验收"
accept_commit: "b2ddf2c"
accepted_items: "A1-A19"
---

# 2026-11-19 契约闸门与文本精简（v4.7.0） — spec 契约

> 本文件是唯一事实来源。改动涉及流程规则 / skill 本身 / agent 行为约束，按反偷懒红线 #2 **必须完整 spec**。
> **签约唯一判定**：用户消息去除首尾空白后**严格等于“签约”两个字**；标点、引号、其他字都不算。
> **验收唯一判定**：用户消息去除首尾空白后**严格等于“验收”两个字**；标点、引号、其他字都不算。
> 编码、测试、验收、PR 全部从本文件派生；需求变更先改本文件。
>
> **修订 1（2026-11-19）**：用户指出审查员未派发。根因：C5 只查结束报告，不查开工派发；1 分钟巡视无机器可读 patrol log；SKILL Step 3 允许“主脑内联分诊”与 team-mode 的独立审查员冲突。新增 C14/C15 + `check_roles --stage start`；旧签约失效，需重新签约。
>
> **修订 2（2026-11-19）**：用户指出契约变更未先暂停子代理。根因：C18 只有散文，无 `status: paused`、无 pause 记录、无 `check_roles --stage pause`；spec 改 draft 后子代理仍可继续跑。新增 C16 + C6 测试证据时效 + C17 失败分类与三次尝试；旧签约再次失效，需重新签约。
>
> **修订 3（2026-11-19）**：全文体检 + J1 BLOCK 6 项；统一修 C4/C5/C6/C14–C18（最新 docs-only 提交、审查员唯一汇总、多文件 hash/run window、start artifact、paused 机器入口、失败 ledger、全文一致性/去废话）；旧签约失效，需重新签约。
>
> **修订 4（2026-11-19）**：Step 5 发现 sign_hash 覆盖 §9 核销记录，填 ✅ 后签约失效、verify 永远无法完成。改为 sign_hash 只覆盖 §§1–8；§9 是签约后核销记录，不参与签约哈希；旧签约失效，需重新签约。
>
> **修订 5（2026-11-19）**：J4 BLOCK：A1–A19 在 §6（§§1–8 内），验收勾选会改 sign_hash；代码层归一化未写入契约。rev5 在 C1/C3/§3/A19 明确：A 复选框 `[ ]`/`[x]` 归一化为 `[ ]` 后参与哈希；验收勾选不改 sign_hash；A19 的“§§1–8 改动”不含 A 复选框状态。旧签约失效，需重新签约。

---

## 1. 背景与目标（what & why）

2026-11-18 复盘暴露 4 类违规：未签约先编码、必派角色零派发却自证、核销表 3 条虚构用例、1450 行部署记录被写成 649 行。
根因一句话：**闸门靠“我声明我做了”，不靠状态与证据**；执行者同时是裁定者，所以“看起来合规”。
本次把 4 个自证入口改成机器闸门，并新增文本铁律：结论前置、禁废话、禁模糊词、每条规则有判定方式。
修订 1：审查员未在开工前派发；补 C14/C15，把“监督角色开工”变成 `check_roles --stage start` 硬闸门。
修订 2：契约变更未先暂停；补 C16 暂停闸门与 C6 测试证据时效。

### 需求澄清记录（Step 1 产出，签约时展示给用户确认）

- **原始需求**：
  1. 复盘文档：`docs/specs/2026-11-18-process-violation-retrospective-and-gates.md`（V1–V4 / R1–R5 / P0-1–P1-3）。
  2. 用户 2026-11-19 追加（原话摘录）：
     - “必须是用户说签约两个字。其他字都不可以意思相近也不可以。”
     - “勾选内容必须是用户统一验收。寓意要明确验收两个才可以。”
     - “skill.md 和 readme 文件要加少废话。契约也是不要太多的废话反而会让裁判员误判。”
     - “这个部分内容这么写是不是会被限制在我的个人开发流程skill呢 我这是通用版大家都能用。”
     - “这个内容也是这也是局限于单个程序项目了……重要的是前期做好准备扫描出关键性的前后的架构。”
     - “要提醒用户是否签约……是否要签约如果需要签约就要发送‘签约’两个字才可以。”
- **优化后需求（R1–R12）**：
  - R1 签约状态机：`draft/signed` 两态；用户消息**只含“签约”两个字**才触发；机器校验签约块。
  - R2 验收状态机：用户消息**只含“验收”两个字**才触发；全部 A 项由用户确认；机器校验验收块。
  - R3 自证闸门：三类独立只读报告（referee/security/auditor）+ `check_roles.py`；单会话至少 1 名只读 subagent。
  - R4 核销真实性：5 列 + 用例文件/用例名/报告路径可追溯。
  - R5 大文件写保护：以写前基线为准，不写死项目行数。
  - R6 入口清单：Step 2 扫描实际架构产出清单，Step 4/6 逐条跳转验收；不硬编码“三处”。
  - R7 编号隔离与 SKIP：流程规则 P1..Pn，产品条款 C1..Cn；SKIP 非零退出。
  - R8 文本铁律：结论前置、一条一句、禁模糊词、每条有判定方式、删废话不删语义；SKILL/README/模板/本 spec 同步精简。
  - R9 审查员开工闸门：第一个写任务前必须派审查员并落盘 patrol log；`check_roles --stage start` 退出码 0 才可开工。
  - R10 契约变更暂停：用户要求改契约 → `status: paused` + 审查员暂停令 + pause 记录；重新“签约”后才恢复。
  - R11 失败分类与三次尝试：派发失败 1 次后换新子智能体；执行失败 3 次（初次+2 重试）后换新子智能体；不得主脑自做；仍失败报用户；无收尾消息=执行失败。
  - R12 全文一致性与去废话：`check_docs.py` 退出码 0；旧口径/过期计数/重复/超长/矛盾清零；allowlist 仅历史 CHANGELOG/旧口径表/canonical 提醒语。
- **优化说明**：
  - 把“继续/同意/可以”从签约判定中删除；把“没问题/发吧”从验收判定中删除；只认“只有两个字”的消息。
  - 把复盘里的项目特定例子（deploy-log 1400 行、侧栏/仪表盘/底栏）改成通用规则与合成负例。
  - 把 v4.6.0 的“接受多种验收表述”整条废止，改为只认只含“验收”两个字的消息。
  - 把 spec §2 的流程规则从 C 编号改为 P 编号，消除裁判员误判。
- **用户问答**：
  - 问：签约能否接受“继续/同意/按这个做”？答：不可以，只有“签约”两个字。
  - 问：用户消息里带“签约”但还有别的内容（如“签约，按这个做”）算吗？答：不算；必须只有“签约”两个字。
  - 问：用户发“签约。”或““签约””算吗？答：不算；标点、引号、其他字都不算。
  - 问：验收能否接受“测试没问题/提交 PR/发吧”？答：不可以，只有“验收”两个字。
  - 问：主脑怎么提醒才不会误会？答：必须写“刚才的说明可能造成误解：是否要签约？如果需要签约，请发送‘签约’两个字才可以；不发送‘签约’两个字，我不会开始编码。只发送这两个字，不要加标点、引号或其他内容。”验收同理。
  - 问：大文件保护是否要写死 deploy-log 行数？答：不，通用版不能限制在个人流程。
  - 问：入口是否固定侧栏+仪表盘+底栏？答：不，先扫描架构；测试/验收阶段加跳转检查。
  - 问：文档与契约是否要精简？答：要，废话会让裁判员误判。
  - 问：为什么审查员没有派发？答：C5 只查结束报告，不查开工派发；已新增 C14/C15 与 `check_roles --stage start`，未过 start 闸门不得开工。
  - 问：为什么改契约时没有暂停？答：C18 只有散文，没有 pause 记录与 `check_roles --stage pause`；已新增 C16，改契约先暂停、盘点、重新签约后才恢复。
  - 问：子代理失败一次就自做，还是三次？答：派发失败（未启动：权限/路由/工具缺失）1 次后换新子智能体；执行失败（已启动但超时/报错/空产出/无收尾消息）3 次尝试后换新子智能体；都不得主脑自做；仍失败报用户。
- **用户约束（裁判员规则源）**：
  - 签约/验收必须原字命中，不接受近义词、错别字、其他对话引用。
  - 签约消息必须**只有“签约”两个字**；验收消息必须**只有“验收”两个字**；多一个字、标点、引号都不算。
  - 主脑必须提醒“刚才的说明可能造成误解：是否要签约？如果需要签约，请发送‘签约’两个字才可以；不发送‘签约’两个字，我不会开始编码。只发送这两个字，不要加标点、引号或其他内容。”验收同理。
  - skill 必须是通用版：不得出现个人项目文件名、固定行数、固定页面入口。
  - SKILL.md、README、spec 模板、spec 必须少废话；重要内容前置；语义强势。
  - 不得降低 9 步、用户验收、禁止 AI 合并 PR 等既有红线。
- **决策展示（D1–D10，正文完整列出；用户可在签约前否决任一项）**：

| # | 决策 | 选定 | 理由 |
|---|---|---|---|
| D1 | 范围 | 全量 P0-1–P0-4 + P1-1–P1-3 + 写作铁律 | 一次修完四个自证入口，避免半套闸门 |
| D2 | 精简范围 | SKILL.md + README + spec 模板 + 本 spec；team-mode 只改涉及章节 | 用户点名三处；全文重写 team-mode 语义漂移风险高 |
| D3 | 闸门强度 | 硬阻断（非零退出即停） | 复盘证明“警告”会被忽略 |
| D4 | 目标管理 | 不启用（未答 = 不启用） | ship-it 规则：主脑不得代选；timeline 仅作进度记录 |
| D5 | 旧 spec 兼容 | 2026-11-19 前按旧规则；新 spec 强制新规则；`--strict` 可强制 | 不伪造历史签约/验收块 |
| D6 | 版本 | v4.7.0（minor） | 新增闸门与脚本，向后兼容 |
| D7 | 修订 1 | 新增 C14/C15 审查员开工闸门 + `check_roles --stage start` | 补 C5 只查结束报告的缺口；需重新签约 |
| D8 | 修订 2 | 新增 C16 契约变更暂停闸门 + C6 测试证据时效 | 补 C18 只有散文、无 pause 记录的缺口；需重新签约 |
| D9 | 修订 2 | 新增 C17 失败分类与三次尝试 | 补“执行失败被当成派发失败、1 次就自做”的口径漏洞；3 次后换新子智能体，不得主脑自做；需重新签约 |
| D10 | 修订 3 | 新增 C18 全文一致性与去废话 + `check_docs.py` | 补全文冲突/废话/过期计数缺口；需重新签约 |

**签约请求模板（必须原样询问）**：

> 刚才的说明可能造成误解：是否要签约？如果需要签约，请发送“签约”两个字才可以；不发送“签约”两个字，我不会开始编码。只发送这两个字，不要加标点、引号或其他内容。
>
> spec：`docs/specs/2026-11-19-contract-gates-and-concision.md`；请核对 C1–C18 与 D1–D10。继续/同意/可以/确认/通过/按这个做/没问题/OK/同意约人 均不算签约；“签约，按这个做”也不算。

**验收请求模板（必须原样询问）**：

> 刚才的说明可能造成误解：是否需要验收？如果需要验收，请发送“验收”两个字才可以；不发送“验收”两个字，我不会进入 PR。只发送这两个字，不要加标点、引号或其他内容。
>
> 请按 A1–A19 验收。没问题/测试通过/提交 PR/发吧/可以/同意 均不算验收；“验收，可以发”也不算。

### 冲突与裁定

| # | 冲突 | 裁定 |
|---|---|---|
| 1 | v4.6.0 接受“测试没问题/提交 PR/发吧”为验收 | 废止；只认只含“验收”两个字的用户消息 |
| 2 | 2026-11-18 复盘提案 P0-1 的“含糊同意判定表”允许“同意/按这个做”签约（未实施） | 不采用；只认只含“签约”两个字的用户消息 |
| 3 | 复盘 P1-1 固定“侧栏+仪表盘+移动底栏” | 改为通用“入口清单 + 架构扫描 + 跳转验收” |
| 4 | 复盘 P0-4 示例 `--expect-lines-min 1400` | 改为基线相对校验，不写死项目行数 |
| 5 | spec 模板 §2 复制 C14–C23 流程规则 | 改为 P1..Pn 一行一条，不复制 skill 正文 |

### 旧口径废止清单（必须逐条改，不能只写“已废止”）

| # | 旧文位置（精确） | 旧口径 | 新口径 | 验证（可执行） |
|---|---|---|---|---|
| 1 | `ship-it/SKILL.md` 文件头 description | 用户确认 = 签约；接受多种验收表述 | 只认严格“签约/验收” | `grep -n "用户确认 = 签约" ship-it/SKILL.md` 与 `grep -n "接受多种验收表述" ship-it/SKILL.md` → 均 0 命中 |
| 2 | `ship-it/SKILL.md` Step 2 签约节 | 用户确认 = 签约 | 只认严格“签约” | 同上 |
| 3 | `ship-it/SKILL.md` Step 6 验收判定 | 接受任何明确表示验收通过；测试没问题/没问题/提交 PR/发吧 | 只认严格“验收” | `grep -n "接受任何明确表示验收通过" ship-it/SKILL.md` → 0 命中 |
| 4 | `README.md` 9 步表（第 12、16 行附近） | 用户确认 = 签约；用户明确表示通过 | 只认严格“签约/验收” | `grep -n "用户确认 = 签约" README.md` 与 `grep -n "用户明确表示通过" README.md` → 均 0 命中 |
| 5 | `ship-it/references/spec-template.md` 头部第 5 行 | 用户确认 = 签约 | 只认严格“签约” | `grep -n "用户确认 = 签约" ship-it/references/spec-template.md` → 0 命中 |
| 6 | `ship-it/references/spec-template.md` §2 | C14–C23 流程规则 | P1..Pn | `grep -nE '^- \*\*C[0-9]+' ship-it/references/spec-template.md` → 0 命中；单测断言 |
| 7 | `ship-it/references/spec-template.md` §9 | 4 列核销 | 5 列 + 报告 footer | 单测断言表头 = 条款/用例名/用例文件/结果/路径真实性 |
| 8 | `ship-it/CHANGELOG.md` “未发布”条目 | 含糊同意判定表；入口三处 | 本 spec 取代 | `grep -n "含糊同意判定表" ship-it/CHANGELOG.md` 与 `grep -n "入口三处" ship-it/CHANGELOG.md` → 均 0 命中 |
| 9 | `ship-it/SKILL.md` Step 3 团队模式 | “审查员对子代理返回做轻量分诊（主脑内联）” | 审查员独立 patrol；主脑不得内联替代 | `grep -n "主脑内联" ship-it/SKILL.md` → 0 命中；`check_roles --stage start` |
| 10 | `ship-it/references/team-mode.md` 审查员巡视 | “每 1 分钟巡视”无 patrol log | 必须有 `auditor-patrol.md` 轮次/时间/证据 | `check_roles --stage start` |
| 11 | `ship-it/SKILL.md` Step 2 执行中需求变更 / `team-mode.md` C18 | “通知审查员暂停子代理”只有散文，无 pause 记录/无 paused 状态 | 契约变更必须先 `status: paused` + `check_roles --stage pause` + pause 记录；重新签约后恢复 | `check_roles --stage pause`；`grep -n "status: paused" ship-it/SKILL.md` |
| 12 | `ship-it/SKILL.md` 反越权红线 #6 / team-mode 失败表 | “同类失败一次后主脑自做”被误用于执行失败 | 派发失败 1 次后换新子智能体；执行失败 3 次（初次+2 重试）后换新子智能体；不得主脑自做；仍失败报用户；覆盖 `SKILL.md:73/668`、`team-mode.md:143/144/288/347` | `grep -n "主脑自做" ship-it/SKILL.md ship-it/references/team-mode.md` → 0 命中；failure log |
| 13 | SKILL/README/spec-template/team-mode/spec/CHANGELOG/runbook | 旧口径/过期 C-A 计数/重复/超长/跨文件矛盾 | `check_docs.py` 退出码 0；allowlist 仅历史 CHANGELOG/旧口径表/canonical 提醒语 | `python ship-it/scripts/check_docs.py --root .` |

## 2. 方案自审（怎么做）

- **复用盘点**：`ship-it/scripts/check_spec.py`（扩展四态与真实性校验）、`ship-it/references/spec-template.md`（加 front matter/入口清单/5 列核销）、`ship-it/references/team-mode.md`（最小独立审查/裁判员调用）、`tests/test_reviewer_judge_contract.py`（核心回归基线）。
- **决策**：B 扩展。理由：现有 9 步、模板、脚本、角色矩阵可直接复用；新建独立流程会与现有 skill 漂移。
- **影响面**：`ship-it/SKILL.md`、`ship-it/references/spec-template.md`、`ship-it/references/team-mode.md`、`ship-it/scripts/check_spec.py`、新增 `check_roles.py`/`guard_large_write.py`/`check_docs.py`/`rule-style.md`、`README.md`、`ship-it/CHANGELOG.md`、`CHANGELOG.md`、`tests/test_process_gates.py`、`docs/deploy-runbook.md`、`docs/reviews/`。
- **现状基线（Step 3 前）**：当前 `check_spec.py` 只有 `spec/verify` 两态，不支持签约/验收块、5 列核销、P 编号校验；A1/A3/A6/A9/A13 是 Step 3 后的目标行为，Step 3 完成前不得用它们作为“已通过”证据。
- **兼容性**：旧 spec（文件名日期 < 2026-11-19）走 legacy：`--stage spec` 只做旧结构检查；`--stage verify` 用旧 4 列核销；不校验签约/验收块、5 列、P 编号；`--strict` 强制新规则；新 spec 不得用 legacy。
- **成本预算**：无 LLM/付费 API；无新增第三方依赖；仅 Python 标准库。
- **安全增量**：无新增依赖/外部输入面；新增脚本只读写本地路径，必须防路径穿越、防符号链接逃逸、防覆盖非目标文件、报告不写密钥（C13）。
- **测试策略**：`tests/test_process_gates.py` 覆盖 C1–C18 正负例（含“签约，按这个做”“签约。”““签约””“验收，可以发”必须 FAIL；C14 未派/首轮晚于实现/轮次不足必须 FAIL；C16 继续派发/无 pause 记录必须 FAIL；C17 执行失败 1 次就自做/派发失败 3 次空转必须 FAIL；C6 测试文件运行中变更必须 FAIL；C18 旧口径/重复/矛盾必须 FAIL）；核心回归跑现有契约测试 + `py_compile` + `build.ps1` BOM + 旧 spec legacy；测试报告落 `docs/reviews/2026-11-19-test-report.md`。
- **执行形态/角色矩阵**：形态 3（规则变更、多文件、高风险）。主脑写 spec/集成；开发 subagent 写脚本与文档（先做 1 次写权限探针；失败换新子智能体，不得主脑自做；仍失败报用户）；测试员 subagent 跑测试；代码安全员/审查员/裁判员只读。**审查员必须在第一个写任务前派发；`check_roles --stage start` 退出码 0 才可开工；主脑不得内联替代；用户改契约时先按 C16 暂停、盘点、重新签约后才恢复。**9 步编号不变。
- **入口清单**：本仓库为 skill 文档/脚本，无页面路由 → `入口清单：无 UI 变更`；C8 在本仓库为 N/A，用合成 fixture 验证。
- **流程规则（P1–P10，一行一条）**：
  - P1 签约只认只含“签约”两个字的消息；未命中不编码。
  - P2 验收只认只含“验收”两个字的消息；未命中不交付。
  - P3 必派角色必须有独立报告与 `path:line` 证据；执行者不得自判。
  - P4 核销 ✅ 必须能追到用例文件、用例名、报告路径。
  - P5 >50KB 文本整体重写必须先备份，写后按基线校验。
  - P6 文档与契约结论前置、一条一句、禁模糊词、每条有判定方式。
  - P7 审查员在第一个写任务前派发；patrol log 落盘；`check_roles --stage start` 未过不得开工。
  - P8 用户改契约先暂停：`status: paused` + pause 记录 + 审查员暂停令；重新签约后才恢复。
  - P9 失败先分类：派发失败 1 次后换新子智能体；执行失败 3 次后换新子智能体；不得主脑自做；仍失败报用户；无收尾消息=执行失败。
  - P10 全文一致性与去废话：`check_docs.py` 退出码 0；旧口径/过期计数/重复/超长/矛盾清零。

## 3. 技术蓝图（按涉及领域填，不涉及写“无变更”）

- **前端**：无变更。
- **后端**：无变更。
- **数据库**：无变更。
- **环境依赖**：无新增；Python 3.8+ 标准库（argparse/pathlib/hashlib/json/re）。
- **脚本接口**：
  - `check_spec.py --stage draft|spec|verify|accept [--git-check] [--base <ref>] [--print-sign-hash] [--strict|--legacy] [--json]`
  - `check_roles.py --date <YYYY-MM-DD> --stage start|pause|sign|verify|accept [--reviews-dir docs/reviews] [--spec <spec>] [--json]`
  - `guard_large_write.py prepare|check|restore <file> [--backup <path>] [--manifest <path>] [--allow-shrink N] [--tail-marker <text>] [--json]`
  - `check_docs.py [--root .] [--json]`
- **check_spec 阶段表**：

| stage | 校验 |
|---|---|
| draft | 结构 + 条款/验收编号 + 三问（可不勾） |
| spec | draft + 签约块（含 sign_hash）+ ①–③已勾 |
| verify | spec + 5 列核销 + 用例文件/用例名/报告 + 分数可追溯 |
| accept | verify + 验收块 + A 全勾 |

- **check_roles 阶段表**：

| stage | 必查报告 |
|---|---|
| start | `<date>-auditor-patrol.md` + `<date>-referee-start.md`、`<date>-security-start.md`、`<date>-auditor-start.md`（start artifact；启动早于第一个实现提交；轮次 ≥3；间隔 ≤5 分钟或事件触发降级） |
| pause | `<date>-pause.md`（暂停时间/触发原话/活跃成员/结束指令清单/新派发=0/旧契约停止/产出保留/未停住项/恢复条件；先于任何 spec 编辑） |
| sign | `<date>-referee-J1.md`（不要求 patrol log；patrol 在签约后 start 阶段） |
| verify | `<date>-referee-J1.md`、`<date>-referee-J3.md`、`<date>-security.md`、`<date>-auditor.md` + patrol + failure log |
| accept | 上述四份 + `<date>-referee-J4.md` + patrol + failure log |

> referee 的 J1/J3/J4 可同一审查者/会话；security/auditor 必须与 referee 不同，且彼此不同。patrol log 由审查员在开工前启动，主脑不得代写。

- **数据格式**：
  - spec front matter 固定键：`spec_version/spec_revision/status/sign_prompt/sign_requested_at/signed_by/signed_at/sign_quote/sign_hash/confirmed_clauses/decisions/accept_prompt/accept_requested_at/accepted_by/accepted_at/accept_quote/accepted_items`；`sign_quote` 只能是“签约”，`accept_quote` 只能是“验收”，`sign_hash` 为 **§§1–8** SHA-256（从 `## 1.` 行到 `## 9.` 行的前一行，按行用 `\n` 连接（CRLF→LF），不追加尾随换行；不含 front matter 与 §9；A1–A19 复选框 `[ ]`/`[x]` 归一化为 `[ ]`），`accept_commit` 为验收时 HEAD SHA。
  - 审查报告固定节：`角色/审查者/会话标识/未参与编码声明/未参与 spec 编写声明/结论/证据/spec_revision/spec_hash/汇总来源`。
  - start artifact 固定字段：`role/reviewer/session/started_at/spec_revision/spec_hash/未参与编码声明/未参与 spec 编写声明`。
  - 审查员写权限例外：仅 `docs/reviews/<date>-auditor-patrol.md`、`<date>-pause.md`、`<date>-auditor.md`、`<date>-failure-log.md`、`<date>-referee-start.md`、`<date>-security-start.md`、`<date>-auditor-start.md`；其他文件不得写。
  - patrol log 固定字段：`启动时间/巡检间隔/轮次/每轮（时间、成员、状态、证据、异常、动作）/结论`；首轮早于实现首次提交。
  - pause 记录固定字段：`暂停时间/触发原话/活跃成员及状态/新派发=0/旧契约停止/产出保留/未停住项/恢复条件`。
  - 测试报告固定字段：每个测试文件 `path/pre_sha256/post_sha256/run_started_at/run_finished_at`；运行窗口内测试文件不得变更。
  - 文档体检固定字段：`check_docs.py --json` 的 `stale/duplicate/long/contradiction/allowlist` 结果；C18 退出码 0。
  - failure log 固定字段：`task/subagent/failure_class/attempt/证据/动作/结论`。
  - 核销表固定列：`条款|用例名|用例文件|结果|路径真实性`；§9 必须有 `- 测试报告：<path>` footer。

## 4. 非目标（out of scope）

- 不做：不改 9 步编号、用户验收归属、禁止 AI 合并 PR、反越权/反偷懒红线。
- 不做：不引入 PyYAML/第三方依赖；不依赖 CI 平台。
- 不做：不全文重写 `team-mode.md`；只改涉及章节。
- 不做：不迁移历史 spec 的签约/验收块；按日期 legacy。
- 不做：不写死个人项目文件名、固定行数、固定页面入口。
- 不做：不做 GUI、不做自动合并、不做自动部署。

## 5. 契约条款（C1 / C2 / …）

### C1 签约唯一判定
- 前置：spec 通过 draft 结构校验；主脑已发送完整提醒：“刚才的说明可能造成误解：是否要签约？如果需要签约，请发送‘签约’两个字才可以；不发送‘签约’两个字，我不会开始编码。只发送这两个字，不要加标点、引号或其他内容。”
- 后置：用户消息 `strip()` 后**严格等于“签约”** → 写入 `sign_quote=签约`/`status: signed`/`sign_hash`（**§§1–8 的 SHA-256：从 `## 1.` 行到 `## 9.` 行的前一行，按行用 `\n` 连接（CRLF→LF），不追加尾随换行；不含 front matter 与 §9；A1–A19 复选框状态 `[ ]`/`[x]` 归一化为 `[ ]` 后参与哈希**）；否则继续等待。
- 失败：继续/可以/同意/同意约人/确认/通过/按这个做/没问题/OK/签一下/签了吧/收到/开始吧 → 不算；“签约。”““签约””“签约，按这个做”“我签约” → 不算；提醒缺关键词 → FAIL；未签约编码 → FAIL。
- 不变式：`sign_quote` 必须是用户原话且严格为“签约”；`sign_hash` 必须绑定 §§1–8（A 复选框状态归一化为 `[ ]`）；§§1–8 任何**文本**变更 → 签约失效，回 draft 重签；§9 填 ✅/改核销记录、A1–A19 复选框 `[ ]`/`[x]` 不改变 sign_hash；主脑不得代写、补记、推断。

### C2 验收唯一判定
- 前置：Step 5 核销通过；主脑已发送完整提醒：“刚才的说明可能造成误解：是否需要验收？如果需要验收，请发送‘验收’两个字才可以；不发送‘验收’两个字，我不会进入 PR。只发送这两个字，不要加标点、引号或其他内容。”
- 后置：用户消息 `strip()` 后**严格等于“验收”** → 写入 `accept_quote=验收`/`accept_commit`（当前 HEAD）；A1..A19 全勾选；`accepted_items` 覆盖全部 A。
- 失败：没问题/测试通过/提交 PR/发吧/可以/同意 → 不算；“验收。”““验收””“验收，可以发”“我验收” → 不算；提醒缺关键词 → FAIL；验收后代码文件变更（`accept_commit..HEAD` 含代码）→ 撤销验收；未验收进入 Step 7 → FAIL。
- 不变式：验收 ≠ 签约；`accept_quote` 必须是用户原话且严格为“验收”；验收后改代码/spec → 撤销验收，回 verify/accept；主脑不得代写。

### C3 签约/验收块机器校验
- 前置：spec front matter 使用固定键。
- 后置：`--stage spec|verify|accept` 都校验签约块；`--stage accept` 另校验验收块；字段齐全；`sign_prompt`/`accept_prompt` 的下列关键词必须全部包含（all）：sign_prompt = 刚才的说明可能造成误解/是否要签约/发送/签约/两个字/不会开始编码/不要加标点、引号或其他内容；accept_prompt = 刚才的说明可能造成误解/是否需要验收/发送/验收/两个字/不会进入 PR/不要加标点、引号或其他内容；`sign_quote` 严格“签约”、`accept_quote` 严格“验收”；`sign_hash` 等于当前 spec **§§1–8** SHA-256（从 `## 1.` 行到 `## 9.` 行的前一行，按行用 `\n` 连接（CRLF→LF），不追加尾随换行；不含 front matter 与 §9；A1–A19 复选框 `[ ]`/`[x]` 归一化为 `[ ]`）；§9 填 ✅、A 复选框勾选后 sign_hash 不得变化；`--stage accept --git-check` 校验 `accept_commit` 存在且 `accept_commit..HEAD` 只含 docs/CHANGELOG/spec；条款/验收项全覆盖 → 退出码 0。
- 失败：缺字段/空值/占位符/提醒缺任一关键词/quote 多字少字/`sign_hash` 不匹配/`accept_commit` 缺失或含代码变更/条款未全覆盖 → 非零退出。
- 不变式：签约块编码前写入；验收块 PR 前写入；不得提前填；`--stage verify` 必须复校验签约块。

### C4 spec 先于实现
- 前置：spec 已签约。
- 后置：`--git-check` 必须提供 `--base <ref>`；spec 首次提交必须为 docs-only 且该提交中的 spec 已含 `status: signed`、`sign_quote: 签约` 与正确的 `sign_hash`（§§1–8，定义同 C1）；spec 修订必须产生新的 docs-only 提交且该提交同样已 signed；实现文件（`docs/` 下仅 spec/reviews 算 docs；`ship-it/**/*.md`、`README.md`、SKILL、模板、team-mode、scripts/tests 均为实现文件）首次提交不得早于最新 signed spec 提交。
- 失败：未提供 `--base`/spec 未提交/同提交含实现/首次提交为 draft/空签约块/最新 docs 提交未 signed/无 `sign_quote`/`sign_hash` 与当前正文不一致/实现更早/把 `.md` 当天然豁免 → FAIL。
- 不变式：先 spec 后代码；spec 修订必须重新签约并产生新的 docs-only 提交；旧 `sign_hash` 不得复用；`.md` 不是天然“非实现文件”；首次提交不得是 draft。

### C5 独立审查闸门
- 前置：形态 1–3 或改动涉及流程规则/skill/agent 行为约束。
- 后置：按 §3 阶段表存在报告；每份含角色、审查者、会话标识、未参与编码声明、结论 PASS、≥3 条 `path:line` 或命令+退出码、`spec_revision`、`spec_hash`；`spec_hash` 必须等于当前 spec **§§1–8** SHA-256；审查员报告含 `汇总来源`（子代理报告路径/ID 列表）；三类角色报告（referee/security/auditor）的审查者/会话标识两两不同；referee 的 J1/J3/J4 可同一审查者/会话；报告固定节含 `未参与编码声明` 与 `未参与 spec 编写声明`，至少 1 名声明未参与 spec 编写；`--reviews-dir` 必须在仓库根内；报告不得含密钥模式；**审查员是唯一汇总接口：所有子代理报告先交审查员，主脑只接收审查员汇总；主脑直接接收/采纳子代理报告 = FAIL。** **start 阶段见 C14；verify/accept 同时校验 patrol log。**
- 失败：缺文件/缺声明/结论非 PASS/证据 <3/`spec_hash` 不匹配/`汇总来源` 缺失/三类角色身份重复/目录越界/含密钥/主脑绕过审查员直接收报告 → FAIL。
- 不变式：执行者 ≠ 裁定者；单会话至少 1 名只读 subagent；不得自检替代；报告原文不得删除/篡改。

### C6 核销真实性
- 前置：§9 核销表使用 5 列，并有 `- 测试报告：<path>` footer。
- 后置：每行有用例名/用例文件/结果 ✅/路径真实性；文件存在；用例名在用例文件中出现；报告文件存在且为 UTF-8 文本；每个用例名出现处 ±2 行内必须有 PASS/通过/✅；§9 每个 `n/n`（核销率除外）能在报告或用例文件中找到；报告必须为每个测试文件记录 `path/pre_sha256/post_sha256/run_started_at/run_finished_at`；`pre_sha256 == post_sha256 == 当前文件 SHA-256`；`run_started_at` 晚于该文件最后修改时间；时间戳由 runner 生成；多文件逐个记录；`--stage verify` 退出码 0。
- 失败：虚构用例名/文件不存在/结果非 ✅/路径空/无报告/用例名不在报告/报告缺 PASS/分数无来源/任一文件 hash 不匹配/运行窗口缺失/运行中改文件 → FAIL。
- 不变式：格式通过 ≠ 事实成立；✅ 必须可追溯；报告是全局证据，不塞进单行；测试证据必须绑定每个测试文件的 hash 与运行窗口，运行中改测试文件 = 证据作废。

### C7 大文件写保护（通用）
- 前置：>50KB 文本文件整体重写前执行 `guard_large_write.py prepare`。
- 后置：写后 `check` 校验 UTF-8、无 U+FFFD、行数 ≥ 基线 - `--allow-shrink`（默认 0）、尾部标记仍在尾部、非空；`prepare` 写 manifest（path/sha256/bytes/lines/tail），`check`/`restore` 读 manifest；删除 >100 行必须显式 `--allow-shrink N` 并人工确认；文件/备份/manifest 必须在仓库根内，拒绝符号链接逃逸。
- 失败：未备份/异常缩水/乱码/尾标丢失/越界/符号链接/manifest 缺失或不一致 → FAIL；失败立即 `restore`。
- 不变式：以写前基线为唯一参照；不写死项目行数；备份仅在 check 通过后删除。

### C8 入口清单与架构扫描（通用）
- 前置：改动涉及页面/路由/入口；无 UI 变更时 §2 必须写 `入口清单：无 UI 变更`，C8 为 N/A。
- 后置：有 UI 变更时，Step 2 从实际架构扫描产出入口清单（导航/仪表盘/底栏/深链/搜索/快捷入口/API 调用方等，按项目实际）；每个入口有跳转验收（打开 → 无 404/无未捕获 JS 异常）；未新增入口写明理由；Step 6 逐条核对。
- 失败：只写一个入口/未扫描架构/入口 404/未捕获异常/用户先发现 → FAIL。
- 不变式：入口清单来自架构扫描，不是固定“三处”；禁止硬编码项目特定入口。

### C9 编号隔离
- 前置：spec 第 2 节流程规则。
- 后置：流程规则用 P1..Pn；产品契约用 C1..Cn；§2 不得出现 `**C<n>` 标签；check_spec 校验。
- 失败：流程规则占用 C 编号/§2 出现 C 标签 → FAIL。
- 不变式：C 只属产品契约；P 只属流程规则。

### C10 SKIP 语义
- 前置：测试脚本支持 SKIP。
- 后置：SKIP 必须退出码 2；退出码 0 + SKIP = FAIL；报告计数只作证据，不替代退出码。
- 失败：SKIP 退出 0 → FAIL。
- 不变式：SKIP ≠ PASS；假绿零容忍。

### C11 文本简洁与强语义
- 前置：SKILL.md / README / spec 模板 / spec。
- 后置：结论前置；一条一句；硬禁用词见 `references/rule-style.md`（本条款不重复词表，避免自匹配）；规范性句子中的“建议/可以”由裁判员判 FAIL（“才可以”等强制短语除外）；样例：`建议使用 X` = FAIL，`必须使用 X` = PASS；每条规则有判定方式；删铺垫/重复/口号；spec 背景 ≤5 行（§1 标题到“需求澄清记录”之前）、每条条款 ≤6 行或 ≤800 字符；check_spec 对超长告警/报错。
- 失败：硬禁用词（按 `rule-style.md`）/规范性“建议/可以”/规则无判定方式/条款超长/复制 skill 正文 → FAIL（裁判员 + check_spec 长度检查）。
- 不变式：删废话不删语义；前置/后置/失败/例外/边界保留；冲突取严。

### C12 版本与文档同步
- 前置：版本号 v4.7.0。
- 后置：`ship-it/SKILL.md` frontmatter、`ship-it/CHANGELOG.md`、根 `CHANGELOG.md` 三处均为 v4.7.0；`spec-template.md` §2 用 P1..Pn、§9 用 5 列；`team-mode.md` 裁判单字段与 C5 一致；`ship-it/CHANGELOG.md` “未发布”条目改为本 spec 取代；C18 `check_docs.py` 退出码 0；旧 spec 按日期 legacy；`--strict` 强制新规则。
- 失败：版本不一致/文档仍用旧口径/旧 spec 误杀/新 spec 走旧规则 → FAIL。
- 不变式：9 步编号、用户验收归属、禁止 AI 合并 PR 不变。

### C13 脚本路径与密钥安全
- 前置：四个脚本接收路径参数。
- 后置：所有路径 `resolve()` 后必须在仓库根内；拒绝 `..` 越界、绝对路径越界、符号链接逃逸；`restore` 只能从 prepare 生成的 `--manifest` 恢复；spec/报告不得含真实密钥值；`API_KEY=`/`TOKEN=`/`PASSWORD=`/`SECRET=` 等模式无论是否有值均 FAIL（扫描时排除本条款的模式示例）；`check_docs.py --root` 同样拒绝越界路径。
- 失败：越界/符号链接/非 manifest 恢复/含真实密钥 → 非零退出。
- 不变式：只读写显式目标与备份；不跟随越界符号链接；不打印密钥。

### C14 审查员开工闸门
- 前置：spec 已签约；主脑准备派发第一个写任务（开发/测试）前。
- 后置：`docs/reviews/YYYY-MM-DD-auditor-patrol.md` 存在；启动时间早于第一个实现提交；首轮早于第一个实现提交；轮次 ≥3；有定时：间隔 ≤5 分钟；无定时：事前声明事件触发，每轮记录 `trigger`（派发/返回/检查点），至少 3 轮；审查员只读，但允许写 `docs/reviews/<date>-auditor-patrol.md`、`<date>-pause.md`、`<date>-auditor.md`、`<date>-failure-log.md`、`<date>-referee-start.md`、`<date>-security-start.md`、`<date>-auditor-start.md`，其他文件不得写；start 文件由该角色本人写；`check_roles.py --stage start` 退出码 0。
- 失败：未派/首轮晚于实现/轮次少于 3/间隔超过 5 分钟且未事前声明事件触发/无 trigger/审查员写其他文件/无证据/主脑代写 → FAIL。
- 不变式：审查员只读；patrol log 原文不得篡改；主脑不得等用户提醒才派；主脑不得内联替代审查员。

### C15 角色 start/report 双闸门
- 前置：必派角色（referee/security/auditor）。
- 后置：每个必派角色有 start artifact：`docs/reviews/<date>-referee-start.md`、`<date>-security-start.md`、`<date>-auditor-start.md`，由该角色本人写，每份含 `role/reviewer/session/started_at/spec_revision/spec_hash/未参与编码声明/未参与 spec 编写声明`；`started_at` 早于第一个实现提交；security/auditor 另加 patrol；`check_roles --stage start|pause|sign|verify|accept` 按 §3 阶段表校验；报告结论 PASS；三类身份互异。
- 失败：开工后补派/缺 start 文件/缺字段/`started_at` 晚于实现/报告与 patrol log 矛盾/身份重复 → FAIL。
- 不变式：执行者 ≠ 裁定者；start artifact 是硬闸门，不是口号；角色 inactive 不等于结束，主脑必须唤醒。

### C16 契约变更暂停闸门
- 前置：用户要求修改已签约 spec（新增/修改/删除条款、验收项、决策）。
- 后置：主脑立即把 spec 置 `status: paused`；**审查员**向所有活跃子代理发暂停/结束令；主脑只向审查员下达意图，不得直接给子代理发结束/暂停指令；`docs/reviews/YYYY-MM-DD-pause.md` 落盘且**先于任何 spec 编辑**（pause.md mtime 必须早于 spec 文件 mtime），含暂停时间、触发原话、活跃成员、结束指令清单（目标/时间/确认）、新派发=0、旧契约停止、产出保留、未停住项、恢复条件；审查员只读例外同上；`check_roles --stage pause --spec <spec>` 退出码 0（校验 `status: paused`、pause.md mtime < spec mtime）；暂停期间只允许只读盘点与 spec 编辑；重新“签约”+新 `sign_hash` 后才恢复；恢复时审查员盘点，受影响闸门重跑。
- 失败：先改 spec 后落 pause/主脑直接发结束令/继续派发/继续跑旧契约/无 pause 记录/未盘点/未重新签约就恢复/暂停期间写代码或提交 → FAIL。
- 不变式：暂停是硬闸门；pause 记录不得事后补写；主脑不得代写审查员暂停令；旧 `sign_hash` 作废。

### C17 失败分类与三次尝试
- 前置：子代理派发或执行失败。
- 后置：failure log 固定 schema（task/subagent/failure_class/attempt/证据/动作/结论）；`dispatch_failed` 1 次后换新子智能体（新会话/新模型/新范围）；`execution_failed` 3 次后换新子智能体（第 4 个，新会话/新模型/新范围）；不得主脑自做；仍失败报用户；用户显式授权才可自做；审查员失败 → 换新审查员，仍失败声明「无独立审查」并**阻塞 start**；裁判员失败 → 换新 subagent/workflow，仍失败报用户，不得自判 PASS；旧“同类失败一次后主脑自做”整条废止。
- 失败：把执行失败当派发失败（1 次就自做）/把派发失败当执行失败（3 次空转）/无 failure log/未满 3 次自做/3 次后主脑自做未获用户授权/审查员失败仍放行 start/裁判员失败后自判 PASS → FAIL。
- 不变式：失败分类以客观事实为准（是否启动、是否有产出）；尝试计数写入 `docs/reviews/YYYY-MM-DD-failure-log.md`；failure log 是硬证据；主脑不得自做执行任务，除非用户显式授权；不得静默重试或静默降级。

### C18 全文一致性与去废话
- 前置：SKILL.md / README / spec-template / team-mode / spec / CHANGELOG / runbook。
- 后置：`check_docs.py` 退出码 0；旧口径/过期 C-A 计数/stage 列表/版本三处/重复段落/超长行/跨文件矛盾全部清零；重复=规范化后 ≥30 字符且出现 ≥2 次；矛盾=同一概念出现两种相反口径；allowlist 仅允许历史 CHANGELOG、spec 旧口径表、canonical 签约/验收提醒语；4.7.0 CHANGELOG ≤300 字符；README 重复 URL 去重。
- 失败：旧口径/过期计数/矛盾/重复/超长（非 allowlist）→ FAIL。
- 不变式：单一事实来源；文档引用 spec，不复制规则；删废话不删语义；历史记录不改写。

## 6. 验收标准（用户逐条打勾）

> 验收唯一判定：用户消息只含“验收”两个字；多一个字、标点、引号都不算。勾选内容必须由用户确认；主脑不得代勾。

- [x] A1 只有用户消息严格等于“签约”才写签约块；“继续/同意/可以/同意约人”“签约。”““签约””“签约，按这个做”不写；`check_spec --stage spec` 对无签约块 FAIL、对严格“签约” PASS。
- [x] A2 只有用户消息严格等于“验收”才写验收块；“没问题/发吧”“验收。”““验收””“验收，可以发”不写；`--stage accept` 对缺验收 FAIL、对严格“验收” PASS。
- [x] A3 签约/验收块字段齐全；`sign_prompt`/`accept_prompt` 含全部关键词；`sign_quote` 严格“签约”、`accept_quote` 严格“验收”；`sign_hash`/`accept_commit` 正确；`confirmed_clauses`/`accepted_items` 全覆盖；§§1–8 文本改动后旧签约块 FAIL；§9 填 ✅、A 复选框 `[ ]`/`[x]` 后 sign_hash 不变。
- [x] A4 spec 与实现同提交 → `--git-check` FAIL；实现提交早于 spec → FAIL；spec 首次提交为 draft/空签约块 → FAIL；spec 修订后最新 docs-only 提交含新 `sign_hash`、实现晚于该提交 → PASS；仍用旧 `sign_hash` → FAIL；把 `.md`（SKILL/README/模板/team-mode）当非实现文件绕过 spec-first → FAIL。
- [x] A5 sign 阶段缺 J1/旧 J1 的 `spec_hash` 不匹配 → FAIL；verify 阶段缺 J1/J3/security/auditor 任一 → FAIL；accept 阶段缺 J4 → FAIL；三类角色报告齐全且 PASS、`spec_hash` 匹配、`汇总来源` 非空、身份互异 → PASS；referee J1/J3/J4 同会话不 FAIL；主脑绕过审查员直接收报告 → FAIL。
- [x] A6 虚构用例名/文件不存在/E2E 13/13 对 12/12/报告缺用例名或 PASS/测试文件运行中被修改/任一文件 pre/post hash 与当前不一致 → `--stage verify` FAIL；冻结后重跑 → PASS。
- [x] A7 1000 行文件先 `prepare`（生成 manifest）再截断为 400 行 → `check` FAIL；`restore` 后 PASS；`..` 越界 → FAIL。
- [x] A8 本仓库 `入口清单：无 UI 变更` → N/A；合成 fixture 只写一个入口/入口 404 → FAIL；入口清单逐条跳转通过 → PASS。
- [x] A9 §2 出现 `**C14` → `check_spec` FAIL；改为 `**P1` → PASS。
- [x] A10 SKIP 退出 0 → 验收脚本 FAIL；退出 2 → PASS。
- [x] A11 SKILL/README/spec 无 `rule-style.md` 硬禁用词、结论前置、条款不超长；裁判员检查 PASS。
- [x] A12 三处版本号均为 v4.7.0；模板 §2 无 C 编号、§9 为 5 列；team-mode 裁判单字段一致；旧 spec 仍 PASS；新 spec 强制新规则；改 spec 后旧签约块 FAIL；验收后代码变更（`accept_commit..HEAD` 含代码）→ FAIL/撤销。
- [x] A13 `--reviews-dir ..` → FAIL；`guard restore` 越界 → FAIL；报告含 `API_KEY=`（无论是否有值）→ FAIL；正常路径 PASS。
- [x] A14 未派审查员/无 patrol log/首轮晚于实现 → `check_roles --stage start` FAIL；轮次少于 3/有定时但间隔超过 5 分钟/无定时未事前声明或每轮无 trigger → FAIL；合规 patrol（有定时或事件触发 3 轮）→ PASS。
- [x] A15 开工后补派/缺 `referee-start/security-start/auditor-start` 文件或字段/`started_at` 晚于实现/非本人写/报告与 patrol log 矛盾 → FAIL；三类身份互异、start 早于实现 → PASS。
- [x] A16 用户要求改契约 → spec `status: paused` + `check_roles --stage pause --spec` PASS；先改 spec 后落 pause/pause.md mtime 晚于 spec/主脑直接发结束令/继续派发/跑旧契约/无 pause 记录 → FAIL；重新“签约”后恢复 → PASS。
- [x] A17 执行失败（无收尾消息/空产出）→ 3 次尝试记录；1 次就自做 → FAIL；3 次后主脑自做未获用户授权 → FAIL；3 次后换新子智能体 → PASS；派发失败 1 次后换新子智能体 → PASS；审查员失败仍放行 start/裁判员 3 次失败后自判 PASS → FAIL。
- [x] A18 `check_docs.py` 对旧口径/过期计数/重复/超长/跨文件矛盾 → FAIL；allowlist（历史 CHANGELOG、旧口径表、canonical 提醒语）→ PASS；4.7.0 CHANGELOG ≤300 字符、README 重复 URL 去重 → PASS。
- [x] A19 sign_hash 只覆盖 §§1–8：填 §9 ✅ 后 sign_hash 不变、`--stage verify` PASS；A1–A19 复选框 `[ ]`/`[x]` 不改变 sign_hash；§§1–8 文本改动 → sign_hash 不匹配 FAIL；`--print-sign-hash` 与 §§1–8（A 归一化）一致。

## 7. 边界与异常

| 场景 | 期望表现 |
|---|---|
| 用户讨论“签约”规则，不是回复签约请求 | 不算签约；重发完整提醒 |
| 用户消息含“签约”但还有其他字/标点/引号 | 不算；重发完整提醒，要求只发送两个字 |
| 用户发“签约。”或““签约”” | 不算；重发完整提醒，明确不要加标点、引号 |
| 用户说“签约”前先提问题 | 先回答；再重发完整提醒；不得跳过 |
| 用户说“验收”但仍有未修问题 | 不算验收；先修再重发提醒 |
| 用户说“验收”但 A 项未勾 | 补勾或重问；不得代勾 |
| 用户消息含“验收”但还有其他字/标点/引号 | 不算；重发完整提醒，要求只发送两个字 |
| 旧 spec 无 front matter | 按日期 legacy 放行；`--strict` 强制新规则 |
| 新 spec 日期早于 2026-11-19 | 视为 legacy 风险；CI 用 `--strict`；回填日期=违规 |
| spec 正文改动但 `sign_hash` 未更新 | FAIL；回 draft 重签；旧签约块作废 |
| 验收后代码文件变更 | `accept_commit..HEAD` 含代码 → FAIL；撤销验收，重跑 verify/accept |
| 审查报告缺 `path:line` | FAIL；不得用摘要代替证据 |
| 审查员未在第一个写任务前派发 | `check_roles --stage start` FAIL；不得开工 |
| patrol log 首轮晚于实现/轮次 <3/间隔 >5 分钟 | FAIL；补巡检或重派 |
| 主脑内联替代审查员 | FAIL；审查员必须独立只读 |
| 主脑直接发结束/暂停令 | FAIL；只能由审查员发 |
| 主脑直接收/采纳子代理报告 | FAIL；必须经审查员汇总 |
| 角色开工后补派 | FAIL；start artifact 必须早于其监督的工作 |
| 用户要求改契约时继续派发/跑旧契约 | `check_roles --stage pause` FAIL；立即暂停并落盘 pause 记录 |
| 无 pause 记录/未盘点/未重新签约就恢复 | FAIL；重新签约后才恢复 |
| 测试文件在运行中被修改/报告 hash 不匹配 | FAIL；冻结后重跑 |
| 旧口径/过期计数/重复/超长/跨文件矛盾（非 allowlist） | `check_docs.py` FAIL；修完再交付 |
| 执行失败（无收尾消息/空产出）按派发失败处理 | FAIL；执行失败必须 3 次尝试并记录 failure log |
| 派发失败（权限/路由）反复重试 3 次 | FAIL；同类派发失败 1 次后换新子智能体 |
| 未满 3 次就自做/静默降级 | FAIL；记录 attempt 与证据 |
| 3 次失败后主脑自做未获用户授权 | FAIL；再派新子智能体，仍失败报用户 |
| 用例名在文件中但未运行 | 报告必须含该用例名与 PASS；否则 FAIL |
| 大文件 `check` 失败 | 立即 `restore`；不得继续交付 |
| 入口清单为空 | 无 UI 变更写“无 UI 变更”；否则 FAIL |
| Windows 中文编码 | 脚本统一 UTF-8；`.ps1` 保持 BOM；写后抽查中文行 |
| 路径含 `..`/绝对路径/符号链接 | 非零退出；不得读写仓库外文件 |
| 报告/spec 含密钥模式 | 非零退出；报告不写密钥 |

## 8. 三问完整性检查 + DoR（不过不得开工）

- [x] ① **取值范围**：`check_spec` stage ∈ {draft,spec,verify,accept}；`check_roles` stage ∈ {start,pause,sign,verify,accept}；`status` ∈ {draft,signed,paused,accepted}；角色 ∈ {referee,security,auditor}；结论 ∈ {PASS,BLOCK,DEVIATION}；`failure_class` ∈ {dispatch_failed,execution_failed}；`sign_quote` 严格“签约”、`accept_quote` 严格“验收”；条款/验收项编号连续；长度上限明确。
- [x] ② **状态流转**：draft →（用户只发送“签约”+签约块+`sign_hash`）signed →（派审查员 + patrol log + `check_roles --stage start`）执行 →（用户改契约 → `status: paused` + pause 记录）→（改 spec 回 draft）→（重新“签约”）signed →（Step 5 verify）→（用户只发送“验收”+验收块+`accept_commit`）accepted；§§1–8 文本变更 → `sign_hash` 失效，回 draft 重签；§9 填 ✅、A 复选框 `[ ]`/`[x]` 不改变 sign_hash；验收后代码变更 → `accept_commit..HEAD` 含代码 → 撤销验收并重跑 verify/accept；失败 → 派发失败 1 次后换新子智能体/执行失败 3 次后换新子智能体；不得主脑自做；记录 failure log；guard 为 prepare → 写 → check →（失败 restore）。
- [x] ③ **生成逻辑**：机器可判定项由 `check_spec.py` / `check_roles.py` / `guard_large_write.py` / `check_docs.py` 的命令+退出码生成；C8 架构扫描、C11 规范性“建议/可以”由裁判员按清单判定；C16 pause 记录、C6 测试文件 hash、C17 failure log、C18 文档体检由 `check_roles`/`check_spec`/`check_docs` 或裁判员校验；两类都必须留证据。

**DoR 自检**：需求无歧义 ☑、技术可行 ☑、影响面已盘 ☑。

## 9. 核销记录（Step 5 填写，PR 里引用）

| 条款 | 用例名 | 用例文件 | 结果 | 路径真实性 |
|---|---|---|---|---|
| C1 | `test_c1_sign_exact_word` | `tests/test_process_gates.py` | ✅ | 机器：临时 spec + check_spec |
| C2 | `test_c2_accept_exact_word` | `tests/test_process_gates.py` | ✅ | 机器：临时 spec + check_spec |
| C3 | `test_c3_sign_accept_block` | `tests/test_process_gates.py` | ✅ | 机器 |
| C4 | `test_c4_git_check_spec_first` | `tests/test_process_gates.py` | ✅ | 机器：临时 git 仓库 |
| C5 | `test_c5_roles_gate` | `tests/test_process_gates.py` | ✅ | 机器：临时 reviews |
| C6 | `test_c6_reconciliation_truth` | `tests/test_process_gates.py` | ✅ | 机器：临时 spec/用例 |
| C7 | `test_c7_guard_large_write` | `tests/test_process_gates.py` | ✅ | 机器：临时大文件 |
| C8 | `test_c8_entry_inventory` | `tests/test_process_gates.py` | ✅ | 机器：模板/文档断言 + 合成 fixture |
| C9 | `test_c9_p_c_number_isolation` | `tests/test_process_gates.py` | ✅ | 机器：§2 C 标签负例 |
| C10 | `test_c10_skip_must_exit_2` | `tests/test_c10_skip.py` | ✅ | 机器：sample skip → runner exit 2 |
| C11 | `test_c11_concise_style` | `tests/test_process_gates.py` | ✅ | 机器：长度；裁判员：硬禁用词 |
| C12 | `test_c12_version_compat` | `tests/test_process_gates.py` | ✅ | 机器：三处版本/旧 spec |
| C13 | `test_c13_path_and_secret_safety` | `tests/test_process_gates.py` | ✅ | 机器：越界/密钥负例 |
| C14 | `test_c14_auditor_start_gate` | `tests/test_process_gates.py` | ✅ | 机器：patrol log 正负例 |
| C15 | `test_c15_role_start_report` | `tests/test_process_gates.py` | ✅ | 机器：start artifact + 报告 |
| C16 | `test_c16_contract_change_pause` | `tests/test_process_gates.py` | ✅ | 机器：pause 记录正负例 |
| C17 | `test_c17_failure_attempts` | `tests/test_process_gates.py` | ✅ | 机器/裁判员：failure log 正负例 |
| C18 | `test_c18_docs_consistency` | `tests/test_process_gates.py` | ✅ | 机器：check_docs 正负例 |

- 测试报告：`docs/reviews/2026-11-19-test-report.md`
- 核销率：18/18（C1–C18 全 ✅；A19 由测试套件覆盖，不计入 C 核销率）
- 分级回归：新套 Ran 19 tests OK（07:41:31–08:03:44，test file 61CCB152…）；旧套 Ran 28 tests OK（0 skip，08:03:58–08:04:05，8C3C9B5C…）；C10 行为级 3 tests OK（C79CE91D…，08:04:05–08:04:08）；A19 行为级 3 tests OK（09B286A2…，07:41:31–07:42:18）；报告 docs/reviews/2026-11-19-test-report.md（SHA 07A81FDB…）
