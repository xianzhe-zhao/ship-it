# J1 裁判单 — 2026-11-19（第 1 轮，BLOCK）

角色：referee
审查者：referee-j1
会话标识：referee-j1 / 2026-11-19
未参与编码声明：是（只读；未写文件、未改 spec、未执行测试、未审代码实现）
结论：BLOCK

证据（至少 3 条，格式 path:line 或 命令+退出码）：
- [spec:22-23](docs/specs/2026-11-19-contract-gates-and-concision.md#L22-L23) 规定“只含两个字、多一个字都不算”，但 [C1:153](docs/specs/2026-11-19-contract-gates-and-concision.md#L153)/[C2:159](docs/specs/2026-11-19-contract-gates-and-concision.md#L159) 写成“去除首尾空白与标点后恰好等于”；用户发“签约。”或复制 [模板:86](docs/specs/2026-11-19-contract-gates-and-concision.md#L86) 的““签约””会被放行，[A1:227](docs/specs/2026-11-19-contract-gates-and-concision.md#L227)/[A2:228](docs/specs/2026-11-19-contract-gates-and-concision.md#L228) 又写“只含两个字”。
- [spec:214](docs/specs/2026-11-19-contract-gates-and-concision.md#L214) 把“可以”列为 FAIL 模糊词，但 [提醒语:86](docs/specs/2026-11-19-contract-gates-and-concision.md#L86)/[:92](docs/specs/2026-11-19-contract-gates-and-concision.md#L92) 必含“才可以”，[模板:88](docs/specs/2026-11-19-contract-gates-and-concision.md#L88)/[:94](docs/specs/2026-11-19-contract-gates-and-concision.md#L94) 也含“可以”；[C1:152](docs/specs/2026-11-19-contract-gates-and-concision.md#L152)/[C3:165](docs/specs/2026-11-19-contract-gates-and-concision.md#L165) 要求这段提醒语。C11 与 C1/C2/C3 不能同时满足；[README.md:203](README.md#L203)/[:205](README.md#L205) 的正常“可以/建议”也会被误杀。
- [spec:177](docs/specs/2026-11-19-contract-gates-and-concision.md#L177) 要求 5 份报告（`referee-J1/J3/J4`、`security`、`auditor`），[A5:231](docs/specs/2026-11-19-contract-gates-and-concision.md#L231) 却写“三份齐全”；J3/J4 在签约阶段尚不存在，`check_roles.py --stage sign` 无法按 :177 退出 0。
- [spec:98-104](docs/specs/2026-11-19-contract-gates-and-concision.md#L98-L104) 冲突表漏掉真实旧口径：[SKILL.md:3](ship-it/SKILL.md#L3)/[:88](ship-it/SKILL.md#L88)/[:205](ship-it/SKILL.md#L205) 仍写“用户确认 = 签约”，[:433-434](ship-it/SKILL.md#L433-L434) 仍写“接受任何明确表示验收通过”“测试没问题/没问题/提交 PR/发吧”；[README.md:12](README.md#L12)/[:16](README.md#L16)、[spec-template.md:5](ship-it/references/spec-template.md#L5) 同。[:101](docs/specs/2026-11-19-contract-gates-and-concision.md#L101) 废止的“v4.6.0 含糊同意判定表”在 v4.6.0 不存在（只在 2026-11-18 复盘提案与 [ship-it/CHANGELOG.md:10](ship-it/CHANGELOG.md#L10) 的“未发布”里）。
- `python ship-it/scripts/check_spec.py docs/specs/2026-11-19-contract-gates-and-concision.md --stage spec` → EXIT=0（未签约 draft 也 PASS）；`--stage verify` → EXIT=1，13 个 ERROR（含“verify 阶段三问仍有未勾选项”）。A1/A3 声称的“机器闸门”当前不存在；`sign_quote` 由主脑自填，无机制绑定用户原话。
- [C3:165](docs/specs/2026-11-19-contract-gates-and-concision.md#L165) 的 `sign_prompt` 子串校验不含“刚才的说明可能造成误解”，C1:152 却要求完整句；且 C3 只查 `--stage spec`，未要求 `--stage verify` 复校验签约块（复盘 P0-1 要求两阶段都查）。
- [C6:183](docs/specs/2026-11-19-contract-gates-and-concision.md#L183) 要求“报告文件存在”，但 5 列定义 [:138](docs/specs/2026-11-19-contract-gates-and-concision.md#L138)/[:268](docs/specs/2026-11-19-contract-gates-and-concision.md#L268) 没有“报告路径”列；“路径真实性”是旧 4 列表的“鼠标/API”语义。[:253](docs/specs/2026-11-19-contract-gates-and-concision.md#L253) 又承认“用例名在文件中但未运行，机器无法判定”，与 [A6:232](docs/specs/2026-11-19-contract-gates-and-concision.md#L232) 的“E2E 13/13 对 12/12 → FAIL”冲突。[:189](docs/specs/2026-11-19-contract-gates-and-concision.md#L189) C7“交付前检查大段删除”无阈值；复盘 P0-4 要求“>100 行删除需人工确认”。
- [C10:207](docs/specs/2026-11-19-contract-gates-and-concision.md#L207) 允许“SKIP 退出码 2 或写入报告计数”，[A10:236](docs/specs/2026-11-19-contract-gates-and-concision.md#L236) 规定“退出 0 → FAIL；退出 2 → PASS”；[C4:171](docs/specs/2026-11-19-contract-gates-and-concision.md#L171) 的 `--base` 可选，A4:230 未测“实现提交早于 spec 提交”。
- [spec:116](docs/specs/2026-11-19-contract-gates-and-concision.md#L116) 说本仓库无 UI 变更，[A8:234](docs/specs/2026-11-19-contract-gates-and-concision.md#L234) 仍要求“入口清单逐条跳转”；[C8:195](docs/specs/2026-11-19-contract-gates-and-concision.md#L195) 的“架构扫描”不可机器判定。[§8:260-262](docs/specs/2026-11-19-contract-gates-and-concision.md#L260-L262) 三问在 `--stage verify` 未勾，DoR 却全 ☑；状态机缺“改 spec 回 draft 重签”“验收后改代码撤销验收”。
- [spec-template.md:36-44](ship-it/references/spec-template.md#L36-L44) 仍是 C14–C23 流程规则，[:118-122](ship-it/references/spec-template.md#L118-L122) 仍是 4 列核销表；[team-mode.md:157](ship-it/references/team-mode.md#L157) 的裁判单输出是 `checkpoint/rules_source/checks/verdict/required_action`，C5:177 要的是“角色/审查者/会话标识/未参与编码声明/结论/证据”；[ship-it/CHANGELOG.md:10](ship-it/CHANGELOG.md#L10)/[:14](ship-it/CHANGELOG.md#L14) 仍写“含糊同意判定表”“入口三处（侧栏/仪表盘/移动底栏）”；[CHANGELOG.md](CHANGELOG.md) 版本索引最新 v4.6.0，无 v4.7.0。C12:219 只查三处版本字符串，不查内容。

问题清单（按 P0/P1/P2）：
- **P0-1 严格性自相矛盾/可绕过**：C1:153、C2:159 的“去标点”与 :22-23、A1:227、A2:228 的“只含两个字”冲突；模板 :86/:92 用引号展示“签约/验收”，用户复制即多字符。
- **P0-2 C11 与强制提醒语冲突**：:214 禁“可以”，:86/:92 必含“才可以”；README/SKILL 中正常“可以/建议”也会被字面误杀，C11 无法实现。
- **P0-3 审查报告闸门不可实现**：C5:177 五份文件 vs A5:231“三份”；J3/J4 在签约阶段不存在，未定义 stage→role→文件映射。
- **P0-4 旧口径废止不完整且对象错误**：SKILL.md:3/88/205/433-434、README.md:12/16、spec-template.md:5 的真实旧规则未列入冲突表；:101 废止的“含糊同意判定表”在 v4.6.0 不存在。
- **P1-1 C3 提醒语与阶段校验缺失**：未查“刚才的说明可能造成误解”；未要求 `--stage verify` 复校验签约块（复盘 P0-1 要求两阶段）。
- **P1-2 C6/C7 真实性机制缺失**：5 列无报告路径列、无报告 mtime、无“汇总数字=脚本断言数”比对；C7“大段删除”无 100 行阈值。
- **P1-3 C4 `--base` 可选**：不带 `--base` 时，spec 首次提交 docs-only 即可，实现更早提交仍可能过，未覆盖复盘 V1。
- **P1-4 C10 与 A10 冲突**：对“写报告计数但退出 0”的判定相反；必须删除“或写入报告计数”或规定验收脚本解析报告计数。
- **P1-5 A8/C8 在本仓库不可验收**：无 UI 变更却保留入口跳转验收；架构扫描无机器判定方式。
- **P1-6 §8 三问/DoR/状态机**：三问未勾但 DoR 全 ☑；状态机缺重新签约与验收撤销；§8③ 声称全部由脚本判定，C8/C11/C5 并非如此。
- **P1-7 旧 spec legacy 跳过清单未定义**：C3/C6/C9 对旧 spec 是无条件 FAIL，C12 只说 legacy；旧 spec 4 列核销表会被 C6 误杀。
- **P1-8 安全要求只在散文**：§2:113 的防路径穿越/防覆盖/不写密钥无 C 条款/A 项；`guard_large_write.py restore`、`check_roles.py --reviews-dir` 越界路径无负例。
- **P1-9 独立性与来源不可证**：C5:179 只要求“至少 1 名只读 subagent”，三份报告可同一会话；`sign_quote`/`accepted_items` 由主脑自填，无 transcript/hash 绑定；未签约 draft 的 `--stage spec` EXIT=0 即证据。
- **P1-10 模板/team-mode/CHANGELOG 未纳入验收**：template:36-44、:118-122、team-mode:157、ship-it/CHANGELOG:10/:14 与新版冲突，A1–A12 无一条覆盖；C12 只查版本字符串。
- **P2-1 C11“背景 ≤ 5 行”**：与第 1 节 70+ 行冲突，未定义“背景”指整节还是首段（:213）。
- **P2-2 A7/A8 细节**：A7 未要求先 `prepare`；A8“用户先发现”不是交付前可判定项（:233-234）。
- **P2-3 C12 版本口径**：前置“v4.7.0”当前不成立（SKILL.md:4 是 4.6.0）；A12 未写“三处均为 v4.7.0”（:218/:238）。
- **P2-4 枚举不一致**：§8① 的 `stage` 是 draft/spec/verify/accept，`check_roles.py` 用 sign；角色枚举是 referee/security/auditor，C5 用 referee-J1/J3/J4（:260 vs :132-134）。
- **P2-5 模板措辞**：:88 让用户“请确认”，:154 又把“确认”列为不算签约；应改“请核对/请阅读”。
- **P2-6 C3 子串语义**：:165 用“/”分隔，未说明“必须全部包含”还是“任一包含”。

必须修正项（BLOCK 时列全）：
- P0-1：明确“标点/引号算不算”，并让 C1/C2、A1/A2、模板措辞三者一致；带标点/带引号的输入必须有明确 PASS/FAIL 用例。
- P0-2：把“可以”从字面禁用词改为“规范性模糊词”判定，或为强制提醒语/引号内原文设机器可判定的例外；保证 `check_spec` 能同时通过 C11 与 C1/C3。
- P0-3：定义 `check_roles.py` 的 stage→role→文件表（sign 查 J1/security/auditor；verify 查 J1/J3/security/auditor；accept 查 J1/J3/J4/security/auditor），并统一 A5 的“三份/五份”。
- P0-4：逐条列出“旧文→新文→验证方式”，至少覆盖 SKILL.md:3/88/205/433-434、README.md:12/16、spec-template.md:5；把“含糊同意判定表”改为“提案未实施”，不得写成 v4.6.0 既有规则。
- P1-1/P1-2/P1-3：补 C3 的完整提醒语子串与 `--stage verify` 复校验；补 C6 报告路径/mtime/汇总数字比对与 C7 100 行阈值；C4 的 `--base` 改为默认必填或自动取 merge-base。
- P1-4/P1-5：消除 C10“或”与 A10 的冲突；给 A8 增加“无 UI 变更”N/A 分支，或用合成 fixture 验证 C8。
- P1-6/P1-7：`--stage spec` 校验 ①–③ 已勾；DoR 交裁判员/用户确认；补“改 spec 回 draft 重签”“验收后改代码撤销验收”；列出 legacy 跳过清单并加旧 spec 4 列 PASS 用例。
- P1-8/P1-9：给三个脚本加路径越界负例；要求三份报告审查者/会话标识互异、至少 1 名未参与 spec 编写；签约/验收 quote 附用户消息哈希或由裁判员核对原文。
- P1-10：把 template §2 改 P1..Pn、§9 改 5 列、team-mode 裁判单输出改 C5 字段、ship-it/CHANGELOG 的“未发布”改为“被 2026-11-19 spec 取代”，根 CHANGELOG 补 v4.7.0；A 项增加对应机器断言。
- P2-3/P2-4：统一 v4.7.0 三处版本与 `stage`/角色枚举；P2-5/P2-6 可随实现修，但不得留到验收。

建议（可执行，不要空话）：
- 先做一张 7 行判定表：`签约`、` 签约 `、`签约。`、`“签约”`、`签约，按这个做`、`确认`、`OK`，逐行写“期望 PASS/FAIL + 判定命令”，让用户先裁定标点/引号。
- 把 C11 改成“规范性模糊词白名单”：只检查未被引号包裹的“尽量/建议/适当/必要时/原则上/一般来说/视情况”；“可以”单列人工复核，否则强制提醒语永远过不了。
- 给 C5 画 stage→role 表并让 `check_roles.py` 按表取文件；增加“J3 在 sign 阶段缺失不得 FAIL”的正例。
- 给 C6 增加“报告路径”列或明确页脚统一填；加 `report.mtime >= 本次提交时间` 与“汇总数字 = 脚本断言数”的机器用例；C7 复用复盘 P0-4 的 >100 行人工确认。
- 把 C4 的 `--base` 改为默认必填（或自动取 merge-base），A4 增加“实现提交早于 spec 提交 → FAIL”负例。
- 在 `check_spec --stage spec` 增加 ①–③ 勾选检查；A11/A12 增加“模板 §2 无 C14–C23、§9 为 5 列、旧 spec legacy 仍 PASS”的机器断言。
- 安全：给 `check_spec.py <spec>`、`check_roles.py --reviews-dir`、`guard_large_write.py restore` 各加 `..`、绝对路径、符号链接三类负例，并把“不写密钥”变成报告字段检查。
