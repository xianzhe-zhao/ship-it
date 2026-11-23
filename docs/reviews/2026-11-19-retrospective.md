# 2026-11-19 v4.7.0 复盘（记录员：recorder）

> 结论：交付成立，过程不合格。三门禁 PASS、53 用例、5 份报告都在；但第一次审查员晚派 33 分钟且没落盘，C16 暂停顺序倒置，测试证据跨两个文件版本；契约 5 版、hash 定义 3 次，4 次重签把同一批报告刷了 4 遍。补跑 C4 的 `--git-check` 仍 FAIL——验收时没人跑它。

## 0. 口径与证据

- 时间以 git 提交时间、文件 mtime、报告内时间戳为准；三者冲突时注明来源。
- 起点：rev1 签约提交 `830d35f`（2026-11-19T10:00:06+08:00）；终点：验收提交 `83593bd`（2026-11-20T08:12:33+08:00）。
- 本次复核（2026-11-20T08:14–08:24，HEAD=`83593bd`，worktree clean）：`check_spec --stage verify|accept` EXIT=0；`check_roles --stage verify|accept` EXIT=0；`check_docs --root .` EXIT=0。
- 补跑 C4：`check_spec --stage accept --git-check --base df96d34` → FAIL 2；`--base 830d35f` → FAIL 1（详见 §4.4）。

## 1. 时间线

| 时间（+08:00） | 事件 | 证据 |
|---|---|---|
| 11-18 19:34:53 | 复盘提案入库（4 类违规 → 闸门提案），改 `ship-it/CHANGELOG.md` | `git log d94613d` |
| 11-19 10:00 前 | J1 第 1 轮 BLOCK + 3 轮复核至 PASS（无逐轮时间戳） | `referee-J1-v1.md:11-14` |
| 10:00:06 | rev1 签约提交（C1–C13 / A1–A13，335 行） | `830d35f` |
| 10:00:58 / 10:08:42 | 首个写探针 / tester 开工＝第一个写任务 | `tmp/write-probe.txt` mtime；`auditor-patrol-r2-BLOCK.md:6` |
| 10:18–10:48 | 实现落盘：check_roles 10:18:56、guard 10:19:38、rule-style 10:25:47、check_spec 10:44:57、test_process_gates 10:48:37 | `auditor-patrol.md:19` |
| 10:40:08–10:57:01 | 4 个分块测试 2/2/3/6 条，404/451/300/168 秒 | `tmp/chunk_a–d.log` |
| 10:41 / 10:41:59 | auditor 第二实例补派；用户追问“审查员有没有派出去” | `patrol-r2:6,13` |
| 10:49:13 / 10:52:43 | 用户再追问“为什么没有派发…重新审视契约” / spec 置 `status: draft`（rev2 开始） | `pause.md:7`；`spec:3` |
| 10:56 / 10:57:01 | 暂停令下发（比改 spec 晚 3 分 17 秒）/ chunk_d 才结束（跨过暂停令） | `pause.md:3,24` |
| 10:59:58 / 11:05:00 | auditor 第一实例 / referee-j1 失败，均无收尾 | `pause.md:9` |
| 11:17–11:18 | 用户二次要求改契约；pause 记录落盘 | `pause.md:3,8` |
| 12:25:51 / 12:36:47 | J1 v1 PASS（第 4 次确认）/ rev3 签约提交（C1–C18 / A1–A18） | `referee-J1-v1.md` mtime；`03faf7d` |
| 12:37:07–12:41:18 | auditor3 派发＋start＋3 轮 patrol（85/86 秒） | `auditor-patrol.md:9,13,24,35` |
| 12:41:45–12:41:59 | 第二波写任务派发；12:52:48 security1 start（晚 11 分钟） | `auditor-patrol.md:56`；`security-start.md:6` |
| 15:23:12–15:48:42 | rev4 暂停 → 重签 | `pause.md:33`；`54b1c61` |
| 16:02:33–16:26:28 | 测试窗口：旧套 28 条 5.2 秒＋新套 19 条 1331.6 秒 | `test-report.md:8`；`tmp/rev4_pg.log` |
| 16:12:39 / 16:31:05 | referee-j1f start（晚第二波 3h31m）/ patrol 第 4 轮（post-dev，距第二波 3h50m） | `referee-start.md:6`；`auditor-patrol.md:59` |
| 16:33:22 / 16:37:49–16:41 | J3 BLOCK（C10）/ 测试报告定稿；failure log | `referee-J3-BLOCK.md`；文件 mtime |
| 16:59:49–17:01:42 | rev5 暂停；A 归一化写入 check_spec | `pause.md:44`；`auditor.md:16` |
| 17:12:02 / 17:26:54–17:28:26 | J4 BLOCK（A 复选框）/ rev5 测试落盘 | `referee-J4-BLOCK.md`；`tmp/final3_pg.log` |
| 17:30:00 / 11-20 07:40:29–07:40:48 | 签约请求（用户已下班）/ 用户“签约”；rev5 提交 | `spec:6`；`spec:8`；`660a6be` |
| 07:41:31–08:04:08 | 最终测试窗口：19/28/3/3 条 | `test-report.md:8-11` |
| 08:04:16–08:05:50 | test/security/auditor/J3 定稿 | 文件 mtime |
| 08:07:34–08:07:36 / 08:10:00–08:12:33 | §9 证据提交 → 实现提交 / 验收请求 → 用户“验收” → 验收提交 | `eab96d9`；`b2ddf2c`；`spec:14,16`；`83593bd` |

## 2. 更改内容

- **spec rev1–rev5**（`docs/specs/2026-11-19-contract-gates-and-concision.md`，433 行）：rev1 C1–C13/A1–A13（签约/验收严格判定、5 列核销、大文件写保护、入口清单、编号隔离、SKIP、文本铁律、版本同步、路径密钥安全）；rev2 新增 C16 暂停闸门、C17 失败分类与三次尝试、C6 测试证据时效；rev3 全文体检 + J1 BLOCK，统一修 C4/C5/C6/C14–C18，新增 `check_docs.py`；rev4 `sign_hash` 只覆盖 §§1–8；rev5 A 复选框归一化为 `[ ]` 后参与哈希。
- **脚本**（3148 行）：`check_spec.py` 1105 行（四阶段、5 列核销、签约/验收块、`--git-check`、路径/密钥、A 归一化）；`check_roles.py` 837 行（start/pause/sign/verify/accept、start artifact、patrol、pause mtime、failure log）；`check_docs.py` 847 行（stale/duplicate/long/contradiction/allowlist）；`guard_large_write.py` 359 行（prepare/check/restore、manifest、尾标）。
- **文档**：`ship-it/SKILL.md`（568 行变更）、`README.md`（91）、`spec-template.md`（110）、`team-mode.md`（134）、新增 `rule-style.md`（119）、两份 CHANGELOG、`docs/deploy-runbook.md`（54）。版本三处 v4.7.0。
- **测试**（2262 行 / 53 条）：`test_process_gates.py` 19 条、`test_reviewer_judge_contract.py` 28 条、`test_c10_skip.py` 3 条、`test_a19_accept_hash.py` 3 条。
- **报告**：5 份独立报告（J1/J3/J4 + security + auditor）＋ 3 份 start artifact ＋ patrol ＋ failure log ＋ 3 段 pause；身份 referee-j1f / security1 / auditor3 两两不同。提交：`b2ddf2c` 16 文件 / +6407 −591；验收提交 `83593bd` 只改 spec 验收块与 A 勾选（54 行）＋ J4 一行路径。

## 3. 犯了什么错、为什么

### 3.1 十条违规（按证据归并）

| # | 违规 | 证据与原因 |
|---|---|---|
| 1 | C14 审查员晚派 33 分钟，首轮无落盘 | 首个写任务 10:08:42，auditor 10:41 才派；10:56 `docs/reviews/` 仍无 patrol（`patrol-r2:13,23`）。原因：旧 C5 只查结束报告，不查开工派发 |
| 2 | C14 巡检间隔 15/9 分钟，超 ≤5 分钟；记录事后补 | `patrol-r2:7`；文件 mtime 11:17:58。原因：宿主无持久定时，未事前声明事件触发 |
| 3 | C16 先改 spec（10:52:43）后发暂停令（10:56） | `pause.md:3,7,23`。原因：C16 当时只有散文，无 `status: paused`/pause 记录 |
| 4 | 暂停令未即时停住在跑任务 | chunk_c 至 10:53:56、chunk_d 10:54:13–10:57:01 跨过暂停（`pause.md:23-24`）。原因：在跑子代理无 kill/超时 |
| 5 | 测试证据过期 | test_process_gates.py mtime 10:48:37；chunk_a 10:40:08、chunk_b 10:48:13 早于该 mtime；13 条跨两个版本，tester 自述 12/13（`pause.md:25`） |
| 6 | 契约自相矛盾、不可实现 | J1 第 1 轮 P0×4＋P1×10（`referee-J1-round1-BLOCK.md:10-19,22-41`）：C1“去标点”对“只含两个字”、C11 禁“可以”对提醒语“才可以”、C5 五份对 A5 三份 |
| 7 | 机器闸门未实现先标 ✅ | `check_spec --stage spec` 对未签约 draft EXIT=0；`check_roles --stage start/pause` EXIT=2；核销率 0/16（`pause.md:26`） |
| 8 | 审查员/裁判员实例失败无收尾 | auditor 10:59:58、referee-j1 11:05:00 failed（`pause.md:9`）；当时无 failure log |
| 9 | 提交/工作时序倒置 | 实现 mtime 10:18–10:48 早于 rev3 签约 12:36:47；§9 证据提交 `eab96d9` 08:07:34 早于实现提交 `b2ddf2c` 08:07:36；J4 定稿 08:12:18 晚于验收 08:11:30 |
| 10 | 主脑代写/转述审查报告 | `referee-J1.md:3`“主脑转录”；`auditor.md:11`“主脑转述 rev5 冻结/verify 结论”。C5 要求审查员是唯一汇总接口，落盘环节由执行者代劳 |

### 3.2 结构性根因

- **“早于第一个实现提交”全部是空判**：实现直到 08:07 才提交，所以 C14 首轮、C15 `started_at`、C4 时序全部自动成立。实际上 referee 16:12 才开工（晚于第二波 3h31m）、security 12:52 才开工（晚 11 分钟），却都“早于实现提交”。闸门量的是提交，不是写入。
- **C4 只看提交先后**：实现一直留在工作区，最后一次性提交，机器查不出“先写后签”。
- **patrol 3 轮落在空窗**：12:38:27–12:41:18 只有 lead＋auditor running、HEAD 未变；真正开发窗口 12:41–16:31 只有 16:31 一次事后检查点（`patrol.md:50,56-57`）。程序上 PASS，实质上没看住。
- **hash 定义改了 3 次**：rev1–3 全文（`f5906b95`/`c18f8d1b`）→ rev4 §§1–8（`fd8ef014`）→ rev5 A 归一化（`5d99c28a`）。每改一次就全体重签、全部报告刷 hash。

### 3.3 J1 BLOCK 口径（统一）

- J1 第 1 轮实际 **4×P0＋10×P1＋6×P2**；仓内没有“6 项”版本的 J1 报告，`spec:33` 的“6 项”是记录错误，以报告为准。
- P0：严格性自相矛盾（C1/C2“去标点”与“只含两个字”）；C11 禁“可以”与强制提醒语“才可以”冲突；报告闸门不可实现（C5 五份 vs A5 三份，J3/J4 在 sign 阶段不存在）；旧口径废止不完整（SKILL/README/template 未入冲突表）。
- P1：C3 缺完整提醒语与 verify 复校验；C6 无报告路径列；C7 无 100 行阈值；C10 与 A10 冲突；C4 `--base` 可选；A8/C8 不可验收；§8 三问未勾但 DoR 全 ☑。

### 3.4 J3 C10 / J4 A 复选框 BLOCK

- J3：旧套 28 tests OK（1 skip）exit 0，skip 来自 `test_reviewer_judge_contract.py:440`；C10 要求 SKIP 退出码 2，§9 C10 却标 ✅。处置：新增 `test_c10_skip.py` 3 条行为级用例＋`SHIP_IT_VERIFY=1` 重跑旧套 28 条 0 skip；J3 复审 PASS。
- J4：A1–A19 在 §6 ⊂ §§1–8，勾 `[x]` 会改 `sign_hash`（实测 `406f9386` ≠ `fd8ef014`）；代码层归一化未写入契约。处置：用户选 A，rev5 在 C1/C3/§3/A19 写明归一化；重签；`test_a19_accept_hash.py` 3 条行为级用例。

### 3.5 子代理慢/失败

- 第一波：auditor 10:59:58 failed、referee-j1 11:05:00 failed，均无收尾（`pause.md:9`）。
- 裁判员共 6 个会话（j1、j1b、j1c、j1d、j1e、j1f），J1 审 4 轮；全流程约 20 个 agent（`pause.md:35,48`）。
- 慢的主因是测试：19 条 1331.576 秒（22 分 11 秒），4 个分块合计约 1323 秒，分块并不省时（`tmp/chunk_*.log`、`tmp/rev5_pg.log`）。

## 4. 怎么修、修后怎么验证

1. **C14/C15**：`check_roles --stage start` 校验 patrol＋三份 start artifact＋首轮早于实现＋轮次/间隔；本次复核 EXIT=0（10 份记录 PASS）。
2. **C16**：`status: paused`＋pause.md mtime < spec mtime＋`check_roles --stage pause`；rev4/rev5 两段 pause 记录均先落盘（`pause.md:33,46`），rev4 暂停时 `check_roles --stage pause` EXIT=1 是预期（spec 仍 signed），置 paused 后重跑（`pause.md:38,42`）。
3. **C17**：failure log 固定 schema；rev4 窗口声明 0 派发失败/0 执行失败，J3 BLOCK 归为契约发现不计失败（`failure-log.md:7,13`）。
4. **C18**：`check_docs.py` 8 文件 2516 行，stale/duplicate/long/contradiction=0（本次 EXIT=0）。
5. **rev4/rev5**：`sign_hash` 只覆盖 §§1–8，填 §9 ✅ 不再使签约失效；A `[ ]`/`[x]` 哈希相同，填 acceptance 后 `--stage accept` PASS，§§1–8 改一行 FAIL（`test-report.md:65-68`）。
6. **53 条测试**：19＋28＋3＋3，四文件 pre/post SHA 与运行窗口齐全（`test-report.md:18-42`）；J3 独立复算四处 hash 与 mtime（`referee-J3.md:24-27`）。
7. **三门禁**：check_spec verify / check_roles verify / check_docs 均 EXIT=0（J4 报告 `:16`；本次复核同）。
8. **验收**：`83593bd` 写入 `accept_quote=验收`、`accept_commit=b2ddf2c`、A1–A19 全勾；`check_spec --stage accept` 与 `check_roles --stage accept` 本次复核 EXIT=0。

### 4.4 但 C4 的 git 闸门没通过（验收时未跑）

- `--stage accept --git-check --base df96d34` → FAIL 2：① `830d35f` 的 `sign_hash` 按现规则不匹配（rev1 用全文定义）；② `d94613d` 改了 `ship-it/CHANGELOG.md`，早于首个签约提交。
- `--base 830d35f` → FAIL 1：`03faf7d` 的 `sign_hash` 同样不匹配（rev3 仍是全文定义）。
- 结论：C4 只在“单次签约、不换 hash 定义、干净基线”时可用；改一次 hash 定义就让历史签约提交全红。验收只跑了三门禁，没人跑第四条。

## 5. 还能改进什么

- **P2 S-1（未修）**：`check_roles.py:759` 的 `check_failure_log` 无密钥扫描，其余 4 类报告有（`security.md:24`）；复核仍在。
- **P3 S-2（未修）**：`.gitignore` 无 `*.bak`/`*.guard.json`，guard 备份可能被误提交（`security.md:25`）。
- **P3 S-3**：`guard restore` 只靠 manifest 标记，手写 manifest 可驱动 restore（`security.md:26`）。
- **P3 S-4**：>100 行缩水的“人工确认”无法机器校验（`security.md:27`）。
- **审查员及时性**：patrol 应绑定事件（派发/返回/检查点），不是固定 3 轮；首轮必须在第一个写任务派发前；巡检窗口内必须有 running 写任务，否则 PASS 无意义。
- **测试速度**：22 分钟/次是重签成本的主因；改 in-process 调脚本或合并 fixture，目标 <3 分钟。
- **子代理超时**：C17 只有失败分类，没有超时阈值；5 分钟无输出 = execution_failed attempt。
- **CI**：无 CI；`--strict` 只能本地跑；流水线跑三门禁＋`py_compile`＋`--git-check`。
- **提交顺序**：实现必须在最新签约后提交；证据提交不得早于实现提交；J4 必须在用户验收前定稿。
- **hash 定义**：C5 未写“定义同 C1/含 A 归一化”（J1 `:22` 非阻断观察）；实现接受 `A\d+`/`[X]` 略宽于 spec 的 A1–A19；C5 加指针、脚本只认 A1–A19、C4 对历史签约提交给 legacy 豁免。

## 6. 如何提升效率

- **批量测试**：一次全量跑代替 4 分块（分块 1323 秒≈全量 1331 秒，没有收益，还制造跨版本证据）。
- **并行审查**：security 可与 J1 并行（本次 12:52 才 start）；J3 依赖测试报告不能并行；J4 可与 security 并行。
- **timebox**：patrol 5 分钟一轮、事件触发；子代理单任务 15 分钟无产出报警。
- **pre-commit**：本地 hook 跑三门禁＋`py_compile`，不要等到提交前才发现红灯。
- **自动 patrol**：用脚本记录 `git status`/mtime/`list_agents`，人工只审异常；本次 68 行 patrol 手写，信息量低于成本。
- **减少契约修订**：rev1 前做一次全文一致性体检（J1 第 1 轮已证明能查出 4 个 P0）；把 `sign_hash` 边界、验收勾选、暂停入口一次设计完，可省掉 rev4/rev5 两次重签。

## 7. 直接回答

- **审查员是否及时查看？** 第一次：不。10:41 晚于 10:08 开工 33 分钟；10:56 仍无 patrol 落盘；间隔 15/9 分钟超限；10:59:58 实例失败（`patrol-r2:6,7,13,23`；`pause.md:9`）。第二次：程序及时（12:37:07 派发早于 12:41:45 第二波），但实质覆盖不足——3 轮在 12:38:27–12:41:18 的 2 分 51 秒空窗内，期间只有 lead＋auditor running、HEAD 未变；开发窗口 12:41–16:31 只有 16:31 一次事后检查点（`patrol.md:50,56-57,59`）。结论：程序补上了，实质没看住。
- **有没有进度？** 有：4 个脚本 3148 行、53 用例、5 份报告、4 次签约提交、1 次实现提交、1 次验收提交。但返工大：J1 6 个会话/4 轮、报告随 4 次重签刷新、测试全量跑 3 次（16:02、07:41，另加 4 个分块）。
- **是否比预计晚完成？** spec 无工期预算（`spec:159` 只有成本预算），不存在“预计”；只能对照节奏：10:00 签约、17:30 才发签约请求、次日 08:11 验收，跨 2 个自然日。晚的直接原因：4 次重签（10:52/12:36/15:48/16:59）＋隔夜等用户签约 14h10m。
- **耗时（按时间戳算术，估算）**：墙钟 22h12m（11-19 10:00:06 → 11-20 08:12:33）；隔夜等用户签约 14h10m（17:30:00 → 07:40:29）；日内暂停 1h24m（10:49:13–11:18、15:23:12–15:48:22、16:59:49–17:30:00）；等测试 ≈56m（10:40:08–10:57:01 扣暂停约 9m；16:02:33–16:26:28 24m；07:41:31–08:04:08 22.5m）；有效工作 ≈5h42m（22h12m − 14h10m − 1h24m − 56m）。

## 8. 结论

1. 闸门是补上了，但补在“提交”这一层，没补在“写入”这一层；只要实现不提交，“早于实现”的检查全部空转。
2. 第一次派审查员晚 33 分钟、暂停顺序倒置、测试证据跨版本，是本次三个硬伤；三处都有书面证据，不能算“差不多”。
3. 契约改了 5 版、hash 定义改了 3 次，是 22 小时墙钟的主因，也是报告反复刷新的根源；下一版应先把 hash 边界与验收勾选定死。
4. 交付物本身可信：53 用例、5 份报告、三门禁 PASS、验收块完整；但 C4 的 `--git-check` 仍 FAIL，PR 前必须决定是修契约（legacy 豁免）还是修提交历史。
