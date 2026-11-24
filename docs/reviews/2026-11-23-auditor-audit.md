# 2026-11-23 监察员专项审查分诊单（v5.0.0 越权/异常/派发前查容量）— monitor-audit

> 角色：auditor（只读）；审查者：monitor-audit；会话标识：monitor-audit / 2026-11-23；父会话 session-0af8bef5-2481-45c2-b896-64b58b99bcf2。
> 审查对象：v5.0.0「角色清晰化与一致性」开发全过程（编码阶段，截至 2026-11-23T14:52+08:00）。
> spec：`docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md`（v5.0.0 / rev3 / status: signed / sign_hash 007e274a…）。
> 未参与编码声明：是（本会话只读审计，仅写本分诊单）。
> 未参与 spec 编写声明：是。
> 交叉印证：本分诊单与裁判员 J2（`docs/reviews/2026-11-23-referee-J2.md`，PASS）独立得出一致结论；本席另补 J2 未覆盖的两项客观校验事实（check_text/check_docs 实跑结果）。

## 总结论

| 审查点 | 结论 | 性质 | 关键证据 | 是否阻断后续
|---|---|---|---|---
| 1 越权行为 | **无越权** | 主脑未亲编代码/角色卡/scripts | 文件 mtime 全部落开发角色 running 窗口 + 4 名开发代理在册 inactive=完成 + 文件集与 patrol 归属吻合 | 否
| 2 异常行为 | **无异常**（附 1 项过程记录未闭合 + 1 项校验红项待修） | 两批开发均有实质产出、无超时/空产出/卡住 | check_terms PASS EXIT=0；diff --stat 532+/122-；dev-script2 产出真实函数非桩 | 否（红项需在 Step 5 核销前清零）
| 3 派发前查容量 | **无硬条款违反**（附局限） | spec 无主脑派发前必查 list_agents 硬条款；8 并发上限全程未超 | grep spec 0 命中 + 各轮 running≤4 + 派发全成功 | 否

---

## 点 1 越权行为 — 无越权

### 1.1 主脑职责边界（契约依据）
- `ship-it/references/team-mode.md:86` 主脑职责：spec 唯一 owner……**只派活、决策、对用户交付**……**不亲自开发/测试/审代码**。
- `docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:158` 主脑职责：只派活、决策、对用户交付，不亲自开发/测试/审代码；统一创建与管理所有团队成员。
- `ship-it/SKILL.md:280` 原则 11：主脑不得代写审查记录、不得直接给子代理发结束令。

### 1.2 时间线证据：所有实现文件 mtime 落在开发角色 running 窗口内（非主脑独占时段）

派发时序（源自 `docs/reviews/2026-11-23-auditor-patrol.md`）：
- 13:29 lead 派发 monitor（开工准备）；13:34 派发 judge（J1）；13:40 派发 security；13:43 派发 dev-doc/dev-script（第一批）；14:01 派发 dev-doc2/dev-script2（第二批）。

实现文件 mtime（`Get-ChildItem ... LastWriteTime` 实测，按时间排序）：

| mtime | 文件 | 归属开发角色 | 派发窗口吻合 |
|---|---|---|---|
| 13:47:42 | `ship-it/references/role-glossary.md` | dev-script（C22 新建） | ✓ 在 13:43 第一批窗口 |
| 13:49:57 | `ship-it/scripts/check_terms.py` | dev-script（C22 新建） | ✓ 在 13:43 第一批窗口 |
| 13:57:53 | `README.md` / `docs/deploy-runbook.md` | dev-doc（C1-C8） | ✓ 在 13:43 第一批窗口 |
| 14:12:41 | `ship-it/scripts/check_roles.py` | dev-script2（C1 改名同步） | ✓ 在 14:01 第二批窗口 |
| 14:15:17 | `ship-it/references/spec-template.md` | dev-doc2（C11/C15） | ✓ 在 14:01 第二批窗口 |
| 14:15:58 | `ship-it/SKILL.md` | dev-doc2（C9-C20/C27/C28） | ✓ 在 14:01 第二批窗口 |
| 14:17:09 | `ship-it/scripts/check_text.py` | dev-script2（C21 通用化） | ✓ 在 14:01 第二批窗口 |
| 14:21:33 | `ship-it/scripts/check_docs.py` | dev-script2（C23 硬属性） | ✓ 在 14:01 第二批窗口 |
| 14:28:40 | `ship-it/scripts/check_spec.py` | dev-script2（C13/C16/C31） | ✓ 在 14:01 第二批窗口 |
| 14:42:22 | `ship-it/references/team-mode.md` | dev-doc2（C3-C8 身份/形态 + C27 收尾） | ✓ 在 14:01 第二批窗口 |

**关键事实**：没有任何实现文件的 mtime 落在「只有 lead running、无开发角色」的时段（13:29-13:43 开工准备期仅有 spec/reviews 文件落盘，无实现写入）。主脑若亲编，必然会在其独占的开工准备期留下实现文件 mtime——实测无此现象。

### 1.3 开发代理在册且完成
- `list_agents` 实测（14:47）：dev-doc / dev-script / dev-doc2 / dev-script2 四名开发角色均在册，status=inactive（=已完成），描述分别为「文档开发改名身份形态 / 脚本开发建词典校验 / 文档开发SKILL其余条款 / 脚本开发校验扩展」。
- 若主脑亲编而无开发代理，则不会有这 4 个 inactive 代理；既有代理又有对应产出，分工成立。

### 1.4 文件集与 patrol 归属一一吻合（git 佐证）
- `git status --short`：M README.md / docs/deploy-runbook.md / ship-it/SKILL.md / ship-it/references/spec-template.md / ship-it/references/team-mode.md / ship-it/scripts/check_{docs,roles,spec,text}.py；?? ship-it/references/role-glossary.md / ship-it/scripts/check_terms.py。
- `git diff --stat`：README.md 14、deploy-runbook.md 16、SKILL.md 60、spec-template.md 15、team-mode.md 164、check_docs.py 175、check_roles.py 9、check_spec.py 172、check_text.py 29（共 532+/122-）+ 2 新建文件。
- 归属对应（与 `docs/reviews/2026-11-23-auditor-patrol.md:70`/:86 派发明细一致）：dev-doc→README/deploy-runbook/SKILL(C1-8)/team-mode；dev-script→role-glossary/check_terms；dev-doc2→spec-template/SKILL(C9-20/C27/C28)/team-mode(C3-8收尾)；dev-script2→check_docs/check_roles/check_spec/check_text。**无孤儿改动指向主脑亲笔。**

### 1.5 关键定性：改 SKILL.md/team-mode.md/scripts 是契约内正当交付物
- `docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:28` 目标：给 8 角色赋专业身份并完成 2 个改名……使每个角色是谁/干什么/前后不矛盾都可机器核验。
- 本次 spec 的交付物**本身就是**改 SKILL.md/team-mode.md（C1-C8 改名/身份/形态）、新建 role-glossary.md+check_terms.py（C22）、扩展 check_*.py（C13/C16/C21/C23/C31）。
- 「主脑改 SKILL.md条款实现/team-mode.md角色卡/scripts扩展属越权」这一判定的**前提是主脑亲为**；由开发子代理按 spec 执行则属正当交付。本席未发现主脑亲为证据。

### 1.6 主脑自身的编辑落在职责内（非越权）
- `docs/reviews/2026-11-23-auditor-patrol.md:41-44`（第3轮）：spec 由 rev2(d24e625d) 升至 rev3(007e274a)，系主脑依裁判员 J1 DEVIATION 修 spec 三问②（A1-A22→A1-A28）/状态一致性。主脑是 spec 唯一 owner（team-mode.md:86），spec-first 修 spec 属职责，非越权。
- 审查记录（auditor-start/auditor-patrol/referee-start/security-start）由监察员/裁判员/代码安全员**本人落盘**（各文件含「本文件由XX本人落盘」声明），符合 team-mode.md 监察员 7 类审查记录写权限与各只读角色自写 start artifact 规范，非主脑代写。

### 1.7 局限
git 无法对未暂存改动归属作者，本席无法 100% 排除主脑隐蔽亲编。但综合证据（mtime 全落开发窗口 + 4 名开发代理在册 inactive=完成 + 监察员独立第三方逐文件归属 + spec 契约 + 文件集吻合 + 第6轮监察员主动盯 dev-doc2 与 dev-doc 同文件先后接力非并发）强力支持「主脑派活、开发执行」的合规分工，未见主脑亲编代码/角色卡/scripts 的证据。

---

## 点 2 异常行为 — 无异常（附 2 项待处理）

### 2.1 两批开发均有实质产出、无超时/空产出/卡住

**第一批（dev-doc/dev-script，13:43 派发 → 14:02 前 inactive=完成）**：
- `docs/reviews/2026-11-23-auditor-patrol.md:82-85`（第6轮）：dev-doc 改 4 文件（README/deploy-runbook/SKILL/team-mode，123+/115-）；dev-script 新建 role-glossary.md（含 8 权威角色名+别名+allowlist+改名纪律）+ check_terms.py。
- 自检 `python ship-it/scripts/check_terms.py` → **PASS（0 处旧名 / 0 错误 / 0 警告，EXIT=0）**（本席 14:48 复跑确认一致）。非空产出。

**第二批（dev-doc2/dev-script2，14:01 派发 → 14:47 前 inactive=完成）**：
- `git diff --stat` 实测：dev-doc2 产出 spec-template.md +15、SKILL.md C9-20/C27/C28 段、team-mode.md C3-8 收尾；dev-script2 产出 check_docs.py +175、check_spec.py +172、check_text.py +29、check_roles.py +9。
- **dev-script2 产出为真实函数实现，非桩代码**（本席 grep 实证）：
  - check_spec.py 新增 `check_step_output_schema`(C13 产出物 schema)、`check_file_boundaries`(C16 路径白名单)、`check_execution_mode`(C31 执行模式闸门)。
  - check_docs.py 新增 `check_role_hard_attributes`(C23 跨文件硬属性) + `_extract_capability_forms`/`_extract_card_forms`/`_extract_matrix_forms`/`_extract_failure_forms` 4 个抽取器。
  - check_text.py `check_contradictions` 通用化（解析全部 C/A 区间，保留原 3 组为子集）。
- 两批均 inactive=完成且有实质 diff，无空产出/卡住迹象。

### 2.2 关于「dev-script2 曾长时间无通知但产出完整」——非异常
- 第二批 14:01 派发，最早产出 mtime 14:12（check_roles.py），最晚 14:28（check_spec.py），跨度约 27 分钟产出 4 个脚本文件的真实函数实现。
- 此时长与工作量匹配（check_docs +175 行含 4 个抽取器 + 一致性判断、check_spec +172 行含 3 个新校验函数），属正常开发耗时，非「卡住」。
- 「无通知」是因为一次性 subagent 的完成以**完成通知回执主脑**为载体（team-mode.md:457），不以中途消息为载体；patrol 第6轮 14:02 记录第二批「刚派发 running，尚未产出」属正常起步观测，非异常。

### 2.3 judge/security inactive 属阶段性待命（非偷懒/超时）
- `docs/reviews/2026-11-23-auditor-patrol.md:74`/:87 明确：judge（J1 阶段完成待命）、security（开工就位后待命）inactive 属阶段性完成，符合 J1 阶段完成后待命的正常生命周期。

### 2.4 待处理项 R1（过程记录未闭合，非阻断）
- 巡逻日志止于第6轮 14:02（第二批刚派发），截至本席审计 14:52 未见第7轮正式闭环第二批完成与改后自检。
- 第二批 OUTPUT 已存在（无空/卡），但改后自检证据的正式巡逻闭环待补。此为**过程记录未闭合**，非开发工作本身的异常。建议主脑/监察员补第7轮闭环记录（与裁判员 J2 观察项 O1 一致）。

### 2.5 待处理项 R2（校验红项，需 Step 5 核销前清零）
本席 14:48 实跑校验链，结果如下：

| 脚本 | 实跑结果 | 根因 | 性质 |
|---|---|---|---|
| check_terms | **PASS（EXIT=0）** | — | 绿 |
| check_text | **PASS（EXIT=0）** | 初次用 `--root ship-it` 致路径拼成 `ship-it/ship-it/SKILL.md` 误报；不带 `--root` 跑即 PASS，SKILL.md:246 边界语齐全 | 绿（实跑无误） |
| check_spec --stage spec | **PASS（0 错误 / 7 警告）** | 7 警告均为验收块待补（accept_* 键），不影响签约阶段 | 绿 |
| check_docs | **FAIL（2 错误）** | `docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:138` 非目标节「不改既有 C1-C18/A1-A19 条款编号体系」措辞，被 check_docs 过期计数检测当作旧口径误报 | **红——待修** |

**R2 定性**：check_docs 的 2 个 ERROR 是 **spec 文本与 check_docs 检测规则的摩擦**，非 dev-script2 脚本扩展的功能缺陷（C23 硬属性检测等新增功能本身正常工作）。修法二选一：
1. 改 spec:138 措辞，避开「C1-C18/A1-A19」字样（如改为「不改既有条款编号体系」）；或
2. check_docs 对 spec 非目标节（§4）加 allowlist，放过此类「不改既有 X-Y」的历史口径陈述。

**此项必须在 Step 5 核销前清零**（C26 校验链全绿要求 check_docs 退出码 0），否则不得进入 Step 6 验收。属开发交付质量问题，但不构成越权/异常行为。

### 2.6 附注：无 dev 报告文件落盘
- `glob docs/reviews/2026-11-23-dev*.md` = 空。与 team-mode.md:457「一次性 subagent……最终报告交主脑」一致（开发报告以完成通知回执主脑，非必落文件）；patrol `:14` 汇总来源 dev 标「待落盘」系期望口径差异，非工作异常（与裁判员 J2 观察项 O2 一致）。

---

## 点 3 派发前检查可用智能体 — 无硬条款违反（附局限）

### 3.1 契约层面：spec 无主脑派发前必查 list_agents 的硬条款
- 本席 `grep` spec 全文 `list_agents|容量|并发|派发前|派发可行性|capacity|空闲|可用智能体` = **0 命中**。
- 契约性的 list_agents 巡检义务归于监察员 watchdog：`ship-it/references/team-mode.md:156`「检查 list_agents 状态」。监察员已在第1-6轮每轮记录成员/状态（`list_agents`，N 名），履职充分。
- 故「主脑每次派发 subagent 前是否查了 list_agents」在本 spec 下**不是主脑的硬性义务**，谈不上违反。

### 3.2 容量未超限（间接证据）
- 全程 8 并发上限未突破：第6轮峰值 running=lead/monitor/dev-doc2/dev-script2（4 并发）+ inactive 4；后续加派 monitor-audit、judge-audit 仍在限内（14:47 实测 running≈2-3）。
- 所有派发均成功上线（各轮 list_agents 见对应角色 running），无因容量不足导致的派发失败/排队。

### 3.3 局限
- 本席为只读叶子 subagent，无法访问主脑（lead）自身会话日志，故无法给出主脑在每次派发前亲自调用 list_agents 的直接证据。
- 可得间接证据（派发全部成功且未触容量上限 + 监察员每轮 list_agents 巡检 + 无容量耗尽）与「容量感知派发」相符，但主脑个人 pre-dispatch list_agents 调用的直接证明超出本只读席位可达。
- 鉴于本 spec 未对此设硬要求、且 watchdog 机制已覆盖容量观测，本点在契约要求层级上**无问题**。

### 3.4 建议（非强制，提升稳健性）
- 若未来希望主脑派发前自查容量成为硬约束，应在 spec/team-mode.md 增设条款（如「主脑每次 subagent 派发前必须调 list_agents 确认 running < limit 且无同名闲置可复用」），并由 check_roles 或新脚本机器校验。当前无此条款，不宜事后追责。

---

## 观察项与建议汇总

| 编号 | 类型 | 描述 | 建议处置 | 阻断 |
|---|---|---|---|---|
| R1 | 过程记录未闭合 | patrol 止于第6轮 14:02，第二批改后自检未正式闭环 | 主脑/监察员补第7轮闭环记录（记 check_docs/check_spec/check_text/check_roles 实跑结果） | 否 |
| R2 | 校验红项 | check_docs FAIL 2 错误（spec:138 措辞与检测规则摩擦） | Step 5 核销前清零：改 spec:138 措辞 或 check_docs 对非目标节加 allowlist | **是（Step 5 前）** |
| O1 | 口径差异 | 无 dev 报告文件落盘（符合一次性 subagent 回执口径） | 主脑/监察员对齐 dev 报告载体约定（文件 vs 完成通知） | 否 |
| 建议 | 提升 | 主脑派发前自查容量目前非硬条款 | 未来若需硬化，增设 spec 条款 + 机器校验 | 否 |

---

## 交叉印证
- 裁判员 J2（`docs/reviews/2026-11-23-referee-J2.md`）独立得出 PASS，三点结论与本席一致；本席以其未覆盖的 check_text/check_docs 实跑结果补充 R2。
- 监察员 patrol（`docs/reviews/2026-11-23-auditor-patrol.md`）6 轮逐文件归属为本席 1.2/1.4 提供第三方独立观测基础。

## 非最终裁定声明
本分诊单为监察员审计意见，不是最终裁定。监察员只审不裁、不面向用户；报告交主脑。最终是否合格以 Step 5 核销（check_spec.py 退出码 0 + 校验链全绿）、Step 6 用户验收、代码安全员/测试员结论为准。

## 证据口径
以上证据均为 `path:line` 或 命令+退出码，≥3 条，符合 team-mode.md 证据要求。审计时点 2026-11-23T14:52+08:00（Asia/Shanghai）。