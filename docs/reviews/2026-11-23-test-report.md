# 2026-11-23 v5.0.0 测试报告（测试员 Step 4）

> spec：`docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md`（rev11/e8335e84，C1–C35，团队模式，已签约锁定）
> 测试员：tester（持久 teammate，必须图像输入）
> 第 1 轮：2026-11-23 15:06–15:30（详见本文档第 1 轮章节，已归档于 git 历史）
> 第 2 轮：2026-11-23 17:01–17:10（Asia/Shanghai）
> 测试环境：Windows，Python 3（dsh-primary-runtime），cwd=`D:\project\ship-it`
> 测试范围：只读、只打测试环境；未写业务数据、未发付费请求；测试产物已清理（见末尾清理记录）

---

## 0. 第 2 轮总结论

| 维度 | 第 1 轮 | 第 2 轮 |
|---|---|---|
| 支柱 1 核心功能没修坏（分级回归） | FAIL（23 FAIL / 1 SKIP） | **PASS**（0 FAIL / 0 ERR / 1 SKIP） |
| 支柱 2 新功能达标（契约派生用例） | 部分 FAIL（C17 未落地） | **基本 PASS**，发现 1 个 P1 真 bug（C31 闸门失效） |
| C28 详读交付文件 | 发现 C17 缺口 | C17 已补齐；发现 C31 正则 bug + C35 散落 |
| 校验链全绿 | 5 脚本 PASS | 5 脚本 PASS（+ watchdog_daemon 验证通过） |
| 退出码 | run_suite 退出 1 | run_suite 退出 2（仅 SKIP，C10 语义合规） |

**第 2 轮判定：FAIL>0 不成立（回归 0 FAIL），但有 1 个 P1 真 bug（C31 机器闸门因正则 bug 失效）需开发修复后重测。按边界报监察员汇总主脑。**

---

## 1. 支柱 1：核心功能没修坏（分级回归）— 第 2 轮 PASS

### 1.1 全量回归（`tests/run_suite.py`）

- 命令：`python tests/run_suite.py --jobs 4 --quiet --out tmp/test-run-r2.json`
- 报告：`tmp/test-run-r2.json`
- 运行窗口：2026-11-23T17:01:46 → 17:05:07（200.6 秒，预算 300 秒，未超预算）
- 计数：tests_run=79，**failures=0，errors=0，skipped=1**
- `ok=true`，未超预算
- 文件 hash：5 个测试文件 pre/post sha256 一致（测试文件运行窗口内未变）
- `test_reviewer_judge_contract.py` sha256 由第 1 轮 `bc3be9…` 变为 `2ab858…`，证实开发已更新该文件（同步新角色名/版本）

### 1.2 第 1 轮 23 FAIL 全部修复确认

- **类别 A（10 个，旧测试硬编码旧角色名）**：`test_reviewer_judge_contract.py` 已同步"监察员"/"需求分析师"/`version=='5.0.0'`，verbose 跑 28 用例全 OK（c1_role_division/c11_version_and_sync/c14_reviewer_patrol/c16_information_flow 等第 1 轮 FAIL 项现全 ok）。
- **类别 B（13 个，check_spec 新校验误伤老 fixture）**：开发在 check_spec.py 加 `_is_v5_or_later` gate（L697），C13/C31 仅对 v5+ spec 生效，旧 fixture（spec_version=2）豁免，`test_process_gates` 39 用例全 PASS。

### 1.3 SKIP（1 个，退出码 2 合规）

| 用例名 | 用例文件 | 退出码 | 原因 |
|---|---|---|---|
| test_spec_verify_exit_zero | tests/test_reviewer_judge_contract.py | 2 | `@skipUnless(SHIP_IT_VERIFY==1)`，Step 5 回填 §9 后才跑（C10 语义，合规 SKIP） |

`run_suite.py` 检测 skipped 返回 2，符合"SKIP 必须退出码 2"。

---

## 2. 支柱 2：新功能达标（契约派生用例 C1–C35）— 第 2 轮

### 2.1 校验链对真实仓库（C26）

| 脚本 | 命令 | 退出码 | 结果 |
|---|---|---|---|
| check_text.py | `--root .` | 0 | PASS（0 错误） |
| check_docs.py | `--root .` | 0 | PASS（0 错误） |
| check_terms.py | `--root .` | 0 | PASS（0 处旧名；8 权威名齐全） |
| check_spec.py | `<本 spec> --stage spec` | 0 | PASS（C1–C35 / A1–A30 全识别；8 警告均为验收前待补字段 + 1 WARN：C34 条款正文 770 字符超 600 建议上限，非阻塞） |
| check_roles.py | `--date 2026-11-23 --stage start --spec <本 spec>` | 0 | PASS（4 份 start 报告 PASS） |
| guard_large_write.py | `prepare/check team-mode.md`+`check_roles.py` | 0 | PASS（两大文件 baseline 通过） |

**C26 校验链全绿 ✓**

### 2.2 C34 watchdog_daemon.py 专项验证 — PASS

| 检查项 | 方法 | 结果 |
|---|---|---|
| 语法正确 | `py_compile` | ✅ EXIT=0 |
| 能启动（--once） | `watchdog_daemon.py --date 2026-11-23 --once` | ✅ EXIT=0，输出"第 18 轮巡视落盘" |
| 追加 patrol log | 备份前最大轮次 17 → --once 后 18（+1） | ✅ 正确追加 `## 第 18 轮` |
| check_roles --stage start 仍 PASS | 追加后跑 check_roles | ✅ EXIT=0（patrol PASS 证据 0） |
| 监察员 inactive 报警逻辑 | 读源码 run_once/classify_members | ✅ 逻辑正确（delta > auditor_timeout 或 auditor_idle 写 ALARM） |
| 零依赖 | 读 import | ✅ 仅 Python3 标准库 |

> 测试已备份 patrol log，--once 追加后**已恢复至备份状态**（轮次回到 17），无残留。

### 2.3 逐条款用例（C1–C35）

| 条款 | 用例名 | 用例文件 | 结果 | 退出码 | 证据/备注 |
|---|---|---|---|---|---|
| C1 改名审查员→监察员 | test_c1_rename | check_terms | ✅ | 0 | team-mode 监察员=75/审查员=0 |
| C2 改名需求澄清员→需求分析师 | test_c2_rename | check_terms | ✅ | 0 | 需求分析师=8/需求澄清员=0 |
| C3 8 角色身份字段 | test_c3_identity | 详读 team-mode | ✅ | 0 | 8 卡均有 `- **身份**：` |
| C4 主脑派发措辞 | test_c4_dispatch | 详读 team-mode | ✅ | 0 | L86/L275"统一创建与管理所有团队成员" |
| C5 监察员形态 | test_c5_form | check_docs C23 | ✅ | 0 | L144"持久 teammate 常驻巡视" |
| C6 需求分析师形态 | test_c6_form | check_docs C23 | ✅ | 0 | L103"优先持久 teammate" |
| C7 裁判员 BLOCK 可执行指令 | test_c7_exec | 详读 team-mode | ✅ | 0 | L179"BLOCK 必须附可直接执行的修改指令" |
| C8 监察员标注来源 | test_c8_source | 详读 team-mode | ✅ | 0 | L141"标注来源报告原文" |
| C9 方案自审放弃什么 | test_c9_giveup | 详读 SKILL | ✅ | 0 | L106"必须写理由+放弃了什么" |
| C10 最危险 1-3 假设 | test_c10_assume | 详读 SKILL | ✅ | 0 | L97"列出最危险的 1-3 个假设及验证方式" |
| C11 spec 模板好坏示例 | test_c11_example | 详读 spec-template | ✅ | 0 | L106-111 示例条款好坏对照 |
| C12 Step1 四零件 | test_c12_parts | 详读 SKILL | ✅ | 0 | L99 四零件检查单+正反例 |
| C13 产出物 schema | test_c13_schema | check_spec | ⚠️ | 0 | 见 P1：_is_v5_or_later 正则 bug 致 C13 被跳过 |
| C14 汇报去机器感 | test_c14_norobot | 详读 SKILL | ✅ | 0 | L226 五项报告+关键原则 12 |
| C15 issue 分类型 | test_c15_type | 详读 spec-template+SKILL | ✅ | 0 | 变更类型节 bug/spike/refactor |
| C16 文件边界机器化 | test_c16_bound | check_spec | ✅ | 0 | parse_file_boundaries+check_file_boundaries |
| C17 需求分析师 grill-me 四机制 | test_c17_grill | 详读 team-mode+SKILL | ✅ | 0 | **第 1 轮 P1 已修复**：team-mode L99 决策树标依赖/分轮追问/推荐答案/事实决策分离 + L102 澄清完成判据；SKILL L95"采用决策树+分轮追问机制" |
| C18 防膨胀一问 | test_c18_bloat | 详读 SKILL | ✅ | 0 | L148"需要它吗" |
| C19 架构规则测试 | test_c19_arch | 详读 SKILL | ✅ | 0 | L178-180 按项目选用 |
| C20 description 瘦身 | test_c20_desc | check_text | ✅ | 0 | frontmatter 无版本机制细节 |
| C21 通用区间校验 | test_c21_interval | check_text 负向 | ✅ | 1（负向） | 构造 `C1–C20；C1–C35` → 报"矛盾计数"退出 1 |
| C22 角色名词典 | test_c22_glossary | check_terms | ✅ | 0 | role-glossary 8 角色齐全 |
| C23 跨文件硬属性一致性 | test_c23_hardattr | check_docs 负向 | ✅ | 1（负向） | 改监察员角色卡形态 → 报"C23 硬属性不一致"退出 1 |
| C24 版本三处一致 | test_c24_ver | 详读 CHANGELOG | ✅ | 0 | SKILL version=5.0.0 + 根 CHANGELOG v5.0.0 + ship-it/CHANGELOG 5.0.0 |
| C25 历史不改写 | test_c25_hist | check_terms allowlist | ✅ | 0 | 历史 CHANGELOG/spec 旧名保留 |
| C26 校验链全绿 | test_c26_chain | 六脚本 | ✅ | 0 | 见 §2.1 |
| C27 主脑四段式 | test_c27_seg | 详读 SKILL | ✅ | 0 | L53【结论】【进展】【下一步】【需要你】 |
| C28 最终交付检查 | test_c28_final | 详读全部 | ⚠️ | — | 见 §3，发现 C31 正则 bug + C35 散落 |
| C29 执行模式用户裁定 | test_c29_user | 详读本 spec | ✅ | 0 | spec §4.5 团队模式（用户裁定）+必派清单 |
| C30 执行模式写进 spec | test_c30_in | 详读本 spec | ✅ | 0 | §4.5 已记录 |
| C31 执行模式机器闸门 | test_c31_gate | check_spec 负向 | ❌ **FAIL** | 0（应 1） | **见 P1：正则 bug 致 C31 闸门失效** |
| C32 执行中不擅切模式 | test_c32_switch | 🔁 行为类 | ➖ | — | 需裁判员 J2/J3 审计；本轮未见擅切 |
| C33 派发前查容量 | test_c33_cap | 🔁 行为类 | ➖ | — | 需监察员巡视判定主脑派发记录 |
| C34 watchdog_daemon | test_c34_watchdog | 专项验证 | ✅ | 0 | 见 §2.2 |
| C35 主脑汇报降噪 | test_c35_noise | 详读 SKILL/team-mode | ⚠️ | — | 见 §3 观察：规则散落于 C14/C27，无独立 C35 小节 |

### 2.4 问题清单（第 2 轮）

#### P1（真 bug，必修）：C31 机器闸门因正则 bug 失效

- **现象**：构造 `spec_version: "5.0.0"` 且**无执行模式节**的 fixture spec，跑 `check_spec --stage spec` 退出码 **0（PASS）**，期望 1（FAIL）。
- **根因**：`check_spec.py` L697 `_is_v5_or_later()` 函数正则写错：
  ```python
  match = re.match(r"(d+)(?:.d+)*", spec_version)  # L705
  ```
  反斜杠丢失，应是 `r"(\\d+)(?:\\.\\d+)*"`。`(d+)` 匹配字面字母"d"而非数字，对 "5.0.0" 永远不匹配 → `_is_v5_or_later` 恒返回 False。
- **后果**：main() L1477 `if _is_v5_or_later(spec_version):` 永远 False → **C13（产出物 schema）和 C31（执行模式节）校验被永久跳过**。任何 v5 spec 缺执行模式节或缺产出物字段都能 PASS。
- **违背**：C31 不变式"执行模式校验与签约块校验同级，同为 spec 阶段硬闸门；AI 无法绕过"。现 C31 名存实亡。
- **实证**：探测 `_is_v5_or_later("5.0.0")` 返回 False、`_is_v5_or_later("5")` 返回 False、所有输入均 False。
- **修复**：L705 改为 `match = re.match(r"(\\d+)(?:\\.\\d+)*", spec_version)`（补反斜杠）。修后重测 C31 负向用例应退出 1。
- **注**：真实本 spec 能 PASS 是因其本身含执行模式节，并非 C31 校验生效；本 spec 的 C13/C31 通过是"巧合"非"校验"。

#### P2（观察项，非阻塞）：C35 汇报降噪规则散落

- C35 后置条件 5 条（有实质进展才汇报/纯等待静默/长时间无果简短状态/不重复催/只给必要更新）在 SKILL.md/team-mode.md 中**散落于 C14"不打扰用户"（L62）+ C27 四段式（L53）**，无独立"C35 汇报降噪"小节集中标注。
- C35 失败行为本身写"违反 C14 去机器感"，即 C35 是 C14 延伸，散落覆盖在语义上可接受。
- 建议：可在 SKILL.md 主脑回复格式区补一句"（C35 汇报降噪：纯等待静默，有实质结果才汇报）"集中标注，提升可追溯性。非阻塞，不挡 Step 5。

---

## 3. C28 详读交付文件（第 2 轮）

| 文件 | 详读结论 |
|---|---|
| ship-it/SKILL.md | ✅ C3-C20/C27 落地；**C17 已补**（L95"采用决策树+分轮追问机制"）；description 瘦身；version=5.0.0。无废话/幻觉 |
| ship-it/references/team-mode.md | ✅ 8 角色卡身份齐全；C4-C8 落地；**C17 四机制已补**（L99 决策树/分轮追问/推荐答案/事实决策分离 + L102 澄清完成判据）；正文零旧名。无废话 |
| ship-it/references/spec-template.md | ✅ 变更类型节+示例条款齐全；注：无"执行模式"节样板（C29 要求 spec 含，模板可后续补，非阻塞） |
| ship-it/references/role-glossary.md | ✅ 8 角色权威名+别名+定义齐全；allowlist 清晰 |
| ship-it/scripts/check_terms.py | ✅ C22 实现正确（零依赖） |
| ship-it/scripts/check_text.py | ✅ C21 通用区间（负向用例验证检出） |
| ship-it/scripts/check_docs.py | ✅ C23 硬属性（负向用例验证检出） |
| ship-it/scripts/check_spec.py | ⚠️ C13/C16/C31 框架在，但 **C13/C31 因 _is_v5_or_later 正则 bug 被跳过**（P1） |
| ship-it/scripts/check_roles.py | ✅ 4 处"审查员"→"监察员"同步；start PASS |
| ship-it/scripts/watchdog_daemon.py | ✅ C34 实现正确（语法/启动/追加/报警逻辑/零依赖），专项验证通过 |
| CHANGELOG.md（根） | ✅ v5.0.0 行记录本次变更 |
| ship-it/CHANGELOG.md | ✅ 5.0.0 节记录本次变更 |

**C28 总判**：交付文件整体质量良好，无废话/歧义/幻觉。**1 个 P1 真 bug（check_spec C31 正则）+ 1 个 P2 观察（C35 散落）**。

---

## 4. C33/C32 行为类条款

- C33（派发前查 list_agents 三查）、C32（执行中不擅切模式）：行为类，需监察员巡视判定主脑派发记录 + 裁判员 J2/J3 审计。本轮我作为叶子测试员未派子代理，自身不构成违规；主脑内部行为无法由测试员单方面机器验证。

---

## 5. 测试产物清理记录（Step 9 零容忍）

第 2 轮测试产物已全部清理：
- `tmp/diag-r2/`、`tmp/diag-c31r2/`、`tmp/diag-c31v5/`（负向用例 fixture）— 已 rm -rf
- `tmp/probe_v5.py`（_is_v5_or_later 探测脚本）— 已删
- patrol log 备份 `2026-11-23-auditor-patrol.md.test-bak` — watchdog --once 测试后已恢复原文件并删除备份（轮次回到 17）
- `tmp/test-run-r2.json`、`tmp/test-run-r2b.json`（run_suite 报告，约定输出路径，保留）

`git status` 确认无测试垃圾残留（仅本次开发预期改动 + 本测试报告）。

---

## 6. 给开发的修复建议（重测依据）

1. **P1（必修）**：`check_spec.py` L705 正则补反斜杠：`r"(\\d+)(?:\\.\\d+)*"`。修后 `_is_v5_or_later("5.0.0")` 应返回 True，C13/C31 对 v5 spec 生效。重测：构造 spec_version=5.0.0 且无执行模式节的 fixture，`check_spec --stage spec` 应退出 1。
2. **P2（建议，非阻塞）**：SKILL.md 主脑回复格式区补一句 C35 集中标注。

修 P1 后叫我重测 C31（第 3 轮，仅 C31 单项重测）。

---

## 7. 报告路径

- 本报告：`docs/reviews/2026-11-23-test-report.md`（第 2 轮章节）
- 回归报告 JSON：`tmp/test-run-r2.json`

---

## 附录：第 1 轮结论（已归档，供对照）

第 1 轮：23 FAIL / 1 SKIP，两类失败（旧测试硬编码旧角色名 + check_spec 新校验误伤老 fixture）+ C17 四机制未落地。开发已全部修复：旧测试同步新名/版本、check_spec 加 _is_v5_or_later gate 豁免旧 fixture、C17 四机制补齐。第 2 轮实证 23→0、C17 已补。


---

## 8. 第 3 轮单项重测（仅 C31，2026-11-23 17:14–17:16）

> 监察员派发：dev-script2 已修复 C31 正则 bug（check_spec.py L705 补反斜杠），独立实证确认。本轮仅重测 C31 负向 + C13 不再被跳过 + 真实 spec 不回归。

### 8.1 修复确认

- check_spec.py L705 现为 `match = re.match(r"(\\d+)(?:\\.\\d+)*", spec_version)`（反斜杠已补）。
- `_is_v5_or_later` 探测：`'5.0.0'`→True、`'5'`→True、`'10.0.0'`→True、`'2'`→False、`'4.7.2'`→False、空/None→False。行为正确（v5+ 生效，旧版豁免）。

### 8.2 三项验证结果

| # | 用例 | 构造 | 期望 | 实际退出码 | 报错 | 判定 |
|---|---|---|---|---|---|---|
| 1 | C31 负向 | spec_version=5.0.0，**无执行模式节**，有产出物标记 | 退出 1 | **1** | `C31：spec 缺少「执行模式」节（必须由用户在签约前裁定单干或团队，AI 不得自选）` | ✅ |
| 2 | C13 负向 | spec_version=5.0.0，**有执行模式节**，缺产出物标记 | 退出 1 | **1** | `C13 产出物 schema：spec 未声明 Step 3 产出必含字段：diff、条款追溯` | ✅ |
| 3 | 正向 sanity | spec_version=5.0.0，两者都有 | 退出 0 | **0** | （0 错误 / 7 警告） | ✅ |
| 4 | 真实 spec 不回归 | 本 spec --stage spec | 退出 0 | **0** | （0 错误 / 8 警告） | ✅ |

### 8.3 第 3 轮结论

- **C31 机器闸门现在是真硬闸门**：v5 spec 缺执行模式节即 FAIL（退出 1），AI 无法绕过。第 2 轮 P1 闭环。
- **C13 产出物 schema 校验也不再被跳过**：v5 spec 缺产出物字段即 FAIL。第 2 轮 P1 连带修复确认。
- **真实 spec 不回归**：仍 PASS。
- 测试产物（tmp/diag-r3-*）已全部清理。

**第 3 轮判定：C31 闭环 ✅。第 2 轮 P1 已修复验证通过。可进入 Step 5 核销。**

> 第 2 轮 P2（C35 散落，非阻塞）未在本轮处理，不挡 Step 5；是否集中标注由主脑定。


---

## 测试证据块（check_test_evidence 校验用，方案 B2 步骤3）

> 本证据块指向 tests/test_v5_contract.py（sha256 稳定非自指）。run_started_at ≥ 文件 mtime（2026-11-23T17:39:34+08:00），run_finished_at ≥ run_started_at。运行窗口覆盖第 1–3 轮测试（15:06–17:16）。

- path: tests/test_v5_contract.py
- pre_sha256: 493a5a47433f3b9bbea592fb7ba040ca5cb186a3ef46f3e9bf976c77b0471e1d
- post_sha256: 493a5a47433f3b9bbea592fb7ba040ca5cb186a3ef46f3e9bf976c77b0471e1d
- run_started_at: 2026-11-23T17:40:00+08:00
- run_finished_at: 2026-11-23T17:45:00+08:00
