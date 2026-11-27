---
spec_version: 2
hash_scope: sections_1_8_a_normalized
spec_revision: 4
status: accepted
sign_prompt: "刚才的说明可能造成误解：是否要签约？如果需要签约，请发送“签约”两个字才可以；不发送“签约”两个字，我不会开始编码。只发送这两个字，不要加标点、引号或其他内容。"
sign_requested_at: "2026-11-20T12:20:00+08:00"
signed_by: "用户"
signed_at: "2026-11-20T12:31:27+08:00"
sign_quote: "签约"
sign_hash: "84ec58d8817ce900e74286350c31c89b40bfed7826202ea823b8a0814210b8e2"
confirmed_clauses: "C1-C12"
decisions: "D1=去废话/防矛盾/防幻觉; D2=git-push-firewall 传输边界; D3=ship-it 远端写边界; D4=check_text 机器检查; D5=v4.7.1; D6=复盘文件纳入 C3/C4/A3"
accept_prompt: "刚才的说明可能造成误解：是否需要验收？如果需要验收，请发送“验收”两个字才可以；不发送“验收”两个字，我不会进入 PR。只发送这两个字，不要加标点、引号或其他内容。"
accept_requested_at: "2026-11-20T13:15:00+08:00"
accepted_by: "用户"
accepted_at: "2026-11-20T13:18:00+08:00"
accept_quote: "验收"
accept_commit: "1014599d8a59e1c34e744234ca5d343a86dbea42"
accepted_items: "A1-A12"
---

# 2026-11-20 skill 文本质量与边界（v4.7.1）

## 1. 背景与目标

两个 skill 有废话、重复、前后矛盾、模糊措辞和越权暗示：`git-push-firewall` 文档写 `GH_BRANCH` 但代码只认 `--branch`，默认 main，未声明“只提供传输、不决定目的地/PR/合并”；`ship-it` Step 7 未要求远端写前读工具、验目标分支。目标：两 skill 精简、无矛盾、无幻觉暗示、边界明确。

## 2. 需求澄清记录

- 用户要求：两个 skill 防废话、防前后矛盾、防工具幻觉、防模糊文字；缩短全文；一句能说清不写两句；严格控字数。
- 本轮为明确需求，已完成口头澄清；无额外问答。
- `git-push-firewall` 是传输方法，可传 main 或任意分支；目的地/PR/合并不由它提供。

## 3. 方案自审与技术蓝图

- 复用 `check_docs.py` 的 stale/duplicate/long/contradiction 扫描。
- 新增 `check_text.py`：行数、禁词、PR/合并授权语、重复标题、矛盾计数。
- 修改 `git-push-firewall/SKILL.md`、`push-via-api.js`、`reference.md`；`ship-it/SKILL.md` 及必要的 README/模板。
- 上限：`git-push-firewall/SKILL.md` ≤60 行；`ship-it/SKILL.md` ≤350 行；本 spec 全文 ≤180 行。

## 4. 非目标

- 不改 ship-it 的 C1–C18 行为规则，只删废话/补远端写边界。
- 不做自动合并、不做自动发布。

## 5. 契约条款

### C1 `git-push-firewall` 传输边界

- 前置：用户要求绕过防火墙上传；目标分支明确。
- 后置：`SKILL.md` 写明“只提供上传方法；可传任意分支（含 main）；具体合到哪个分支/是否 PR/是否合并，不由此 skill 决定；按原计划执行”；不引用其他 skill；脚本显式 `--branch` 或 `GH_BRANCH`（同一来源），缺失即失败；启动打印 `repo/branch`；上传前 `GET ref`；文档与代码一致；`SKILL.md` ≤60 行。
- 失败：缺 branch、静默默认 main、文档/代码不一致、出现“可创建 PR/可合并”授权语、引用其他 skill、超行 → FAIL。
- 不变式：只传文件；不决定目的地/PR/合并；只声明“不由此 skill 决定”，不写“不创建/不合并”等越权结论；提醒按原计划执行。

### C2 `ship-it` 远端写边界

- 前置：Step 7；用户已验收。
- 后置：远端写前必须读上传工具的 skill 与脚本实际参数，确认目标分支；PR 仅在验收后创建；合并仅用户；只写通用“上传工具”，不点名其他 skill；`SKILL.md` ≤350 行。
- 失败：未读工具、未验分支、验收前创建 PR、主脑合并、点名其他 skill、超行 → FAIL。
- 不变式：PR 创建权在 Step 7 + 用户验收；合并权只在用户；两 skill 互不引用。

### C3 文本质量

- 前置：两 skill 文本。
- 后置：两 skill + 复盘文件 `docs/reviews/2026-11-19-retrospective.md` 无废话、重复、前后矛盾、模糊措辞；一句能说清不写两句；规则用“必须/禁止”；可选必须显式标“可选”；禁无规则的模糊词（清单见 `ship-it/references/rule-style.md`）；两 skill 互不引用；复盘 ≤150 行；`check_text.py` 扫描行数、禁词、重复标题、矛盾计数、互引。
- 失败：禁词、矛盾、重复、超行、PR/合并幻觉、互引 → FAIL。
- 不变式：文本质量由机器检查，不靠自证。

### C4 机器检查

- 前置：两 skill + 复盘文件。
- 后置：`check_text.py` 对两 skill + 复盘文件执行 C1–C3 扫描（含互引：`git-push-firewall` 不得出现 `ship-it`，`ship-it` 不得出现 `git-push-firewall`；复盘 ≤150 行）；`check_docs.py` 对 ship-it 文档 PASS。
- 失败：任一非零退出 → FAIL。
- 不变式：执行者≠裁定者；机器检查结果为准。

### C5 验证

- 前置：C1–C4 完成。
- 后置：`check_spec.py` 四阶段；`check_roles.py` start/pause/sign/verify/accept（含三份 start + patrol + failure log）；`check_text.py`；`check_docs.py`；J1/J3/J4/security/auditor 报告；测试；用户验收。
- 失败：任一非零退出 → FAIL。
- 不变式：未验收不进入 PR。

### C6 C14 首写标记

- 前置：start artifact/patrol 在首个写任务前。
- 后置：首个写任务前创建 `tmp/first-write.json`（first_write_at/path）；start artifact/patrol 的 started_at 必须早于 first_write_at；`check_roles start` 读取 marker；无 marker 或晚于 marker → FAIL。
- 失败：patrol 晚于首写、无 first-write 标记、仅 commit 校验 → FAIL。
- 不变式：闸门量写入，不量提交；不得空转。

### C7 C16 暂停前 spec

- 前置：契约变更，先暂停。
- 后置：暂停前把当前 spec 快照到 `tmp/spec-before-<rev>.md`；pause.md 记录 spec_before_revision/hash/snapshot；`check_roles pause` 校验 snapshot hash == pause.md + pause.md mtime < spec mtime；不要求 pause.md == 当前 spec；顺序：暂停/快照/置 paused/跑闸门/再改正文。
- 失败：先改 spec 后 pause、pause 记录当前 spec、hash 不一致、无 pause → FAIL。
- 不变式：pause 记录是变更前；spec 编辑在其后；不得事后补。

### C8 C4 历史 hash

- 前置：`check_spec --git-check --base`。
- 后置：每个 spec 文件 front matter 记录 `hash_scope`（full_body / sections_1_8 / sections_1_8_a_normalized）；`--git-check` 按该文件的 `hash_scope` 计算；旧 spec rev1–3 = full_body（front matter 后全文，含 §9）；v4.7.1 rev1 = sections_1_8；`d94613d` 提案 legacy；A8 base 含 df96d34/830d35f/03faf7d/54b1c61/660a6be。
- 失败：旧 hash 不匹配、提案提交早于首个签约、spec/实现同提交 → FAIL。
- 不变式：历史提交按当时定义校验；不得全用当前定义。

### C9 测试速度

- 前置：`test_process_gates`。
- 后置：四套测试在冻结快照 <5 分钟；测试报告记录 run_started/run_finished；慢测试标记 @slow + --fast；结果与基线一致；不写死调用次数。
- 失败：>5 分钟、逐用例起进程、无窗口/hash → FAIL。
- 不变式：速度是门禁；不得牺牲证据。

### C10 提交顺序

- 前置：实现提交。
- 后置：仓库内 `ship-it/scripts/pre_commit_check.py` + `install-hooks`；pre-commit 跑 `check_spec --git-check`；CI 留证；spec/docs-only 在实现前；不写“尽早”。
- 失败：spec+实现同提交、实现先于 spec、无 pre-commit → FAIL。
- 不变式：spec-first；docs-only spec；提交顺序。
### C11 reviewer 活跃/步骤闸门

- 前置：`check_roles` 五阶段（start/pause/sign/verify/accept）。
- 后置：reviewer = 审查员（auditor）；每个 stage 的 `auditor-patrol.md` 末轮 `last_active_at` 必须落盘；`last_active_at >= max(first_write_at, test_run_finished) - 5min`（start 阶段无 `test_run_finished` 时 max 只取 `first_write_at`）；`check_roles` 读 `tmp/first-write.json` 与 test report `run_finished` 校验；主脑在派发/返回时唤醒。
- 失败：`last_active_at` 缺失/早于 `max(...) - 5min` 容差、无 patrol → FAIL。
- 不变式：reviewer 是审查员；`last_active_at` 落盘；每 stage 唤醒；不得一次性 start。

### C12 reviewer 唯一汇总

- 前置：dev/tester 报告。
- 后置：reviewer = 审查员（auditor）；`汇总来源` 必须列全子代理报告路径/ID 且文件存在；`check_roles` 校验；主脑直接接收/汇总记录在 `auditor-patrol.md`（审查记录，不作为机器项）。
- 失败：`汇总来源` 缺失/路径不存在；主脑直收未记录 → 由裁判员判定 FAIL（通信项）。
- 不变式：reviewer 唯一汇总接口；执行者≠裁定者；机器项=`汇总来源`，通信项=patrol 记录。
## 6. 验收标准

- [x] A1 `git-push-firewall` 写明传输边界（不决定目的地/PR/合并、按原计划执行）；显式 branch；文档/代码一致；无互引；`SKILL.md` ≤60 行。
- [x] A2 `ship-it` Step 7 写明远端写前读工具/验分支；PR 仅验收后；合并仅用户；无互引；`SKILL.md` ≤350 行。
- [x] A3 两 skill + 复盘文件无废话/重复/矛盾/模糊/互引；禁词 0；行数达标（ship-it ≤350、git-push-firewall ≤60、复盘 ≤150）。
- [x] A4 `check_text.py`/`check_docs.py`/测试 PASS；`check_roles start/pause/sign/verify/accept` PASS（pause 如发生契约变更则必须 PASS）；J1/J3/J4/security/auditor 全 PASS。
- [x] A5 用户发送严格“验收”并确认 A1–A4 全部满足。
- [x] A6 first-write 标记；`check_roles start` 早于首写；patrol 覆盖写入。
- [x] A7 pause 记录绑定暂停前 spec；pause 闸门 PASS；spec 编辑在其后。
- [x] A8 `--git-check` 按文件 `hash_scope` 选 hash；base `df96d34`/`830d35f`/`03faf7d`/`54b1c61`/`660a6be` PASS。
- [x] A9 四套测试 <5 分钟；报告有 run_started/run_finished；慢测试标记；结果与基线一致。
- [x] A10 仓库内 pre_commit_check + install-hooks；CI 留证；spec/docs-only 在实现前。
- [x] A11 `auditor-patrol` 末轮 `last_active_at >= max(first_write_at, test_run_finished) - 5min`；`check_roles` PASS。
- [x] A12 `汇总来源` 列全子代理报告路径/ID 且文件存在；`check_roles` PASS；主脑直收记录在 patrol。

## 7. 边界与异常

| 场景 | 期望 |
|---|---|
| `git-push-firewall` 传 main | 允许；必须显式 branch，并声明目的地/PR/合并不由它决定 |
| 未传 branch | 失败，不静默默认 main |
| 文档与代码不一致 | FAIL |
| skill 出现 PR/合并授权语 | FAIL |
| 行数超限/禁词/矛盾 | FAIL |

## 8. 三问完整性检查

- [x] ① 需求无歧义
- [x] ② 技术可行
- [x] ③ 影响面已盘

## 9. 核销表

| 条款 | 用例名 | 用例文件 | 结果 | 路径真实性 |
|---|---|---|---|---|
| C1 | test_c1_transport_boundary | tests/test_text_quality.py | ✅ | 机器：check_text + 真实 skill |
| C2 | test_c2_remote_write_boundary | tests/test_text_quality.py | ✅ | 机器：check_text + 真实 skill |
| C3 | test_c3_text_quality | tests/test_text_quality.py | ✅ | 机器：check_text |
| C4 | test_c4_check_text | tests/test_text_quality.py | ✅ | 机器：check_text |
| C5 | test_c5_gates | tests/test_text_quality.py | ✅ | 机器：check_spec/check_docs/check_text |
| C6 | test_c6_first_write_marker | tests/test_process_gates.py | ✅ | 机器：check_roles start |
| C7 | test_c7_pause_pre_change | tests/test_process_gates.py | ✅ | 机器：check_roles pause |
| C8 | test_c8_git_check_revisions | tests/test_process_gates.py | ✅ | 机器：check_spec --git-check |
| C9 | test_c9_test_speed | tests/test_process_gates.py | ✅ | 机器：run_suite 184.475s |
| C10 | test_c10_commit_order | tests/test_process_gates.py | ✅ | 机器：pre_commit_check/install-hooks |
| C11 | test_c11_reviewer_liveness | tests/test_process_gates.py | ✅ | 机器：check_roles patrol last_active_at |
| C12 | test_c12_reviewer_sole_aggregation | tests/test_process_gates.py | ✅ | 机器：check_roles 汇总来源 |

- 测试报告：docs/reviews/2026-11-20-test-report.md
- 核销率：12/12
- 分级回归：65 tests / 0 failures / 0 errors / 0 skipped（184.475s）
