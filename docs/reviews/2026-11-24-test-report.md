# 2026-11-24 v5.1.0 测试报告（测试员 Step 4 验收测试）

> spec：`docs/specs/2026-11-24-v5.1.0-skill-self-consistency.md`（rev1 / sign_hash 6142a976…，C1–C10，已签约锁定）
> 测试员：tester（叶子会话，只做验收测试，不审代码、不审契约）
> 会话标识：tester / 2026-11-24 / 98f7c915-54e4-4309-b39b-cbda3ca3eed6
> 运行窗口：2026-11-24T12:21:45 → 12:21:52（Asia/Shanghai，5.14 秒）
> 测试环境：Windows，Python 3.11.9，pytest 9.1.1，cwd=`D:\project\ship-it`
> 测试范围：只读验收测试，从 spec §5 C1–C10 派生；未写业务数据；C5 降级用例仅在 tmp/ 下建临时 fixture 并于用例结束时清理（已确认无残留）

---

## 0. 总结论

| 维度 | 结果 |
|---|---|
| 支柱 2 新功能达标（契约派生用例 C1–C10） | **PASS**（10/10 通过） |
| 退出码 | 0（10 passed, 0 skipped, 0 failed） |
| SKIP 数 | 0（本用例集无条件跳过；SKIP=0 ⇒ 「SKIP 必须退出码 2」规则空真满足，无「退出码 0 + SKIP = 假绿」） |
| 失败项 | 无 |
| 证据完整性 | pre_sha256 == post_sha256（运行窗口内测试文件未变更） |

**判定：C1–C10 全部达标，可进入 Step 5 契约核销。**

---

## 1. 运行概况

- 命令：`python -m pytest tests/test_v5_1_0_self_consistency.py -v --tb=short`
- 退出码：0
- 计数：collected 10 items → **10 passed in 5.14s**（0 skipped / 0 failed / 0 errors）
- 原始日志：`tmp/pytest-v510.log`（gitignored，Step 9 清理）
- 测试文件运行窗口内 sha256 不变（见 §5 证据块）

---

## 2. 逐条款用例（C1–C10）

| 条款 | 用例名 | 命令/方法 | 退出码 | SKIP | 失败项 | 结果 |
|---|---|---|---|---|---|---|
| C1 | test_c1_version_consistency | 读 `ship-it/SKILL.md` 断言 frontmatter `version: 5.1.0`；grep `当前 v4.7.1` 无匹配；无非 5.1.0 的「当前 vX」 | 0 | 0 | 无 | ✅ PASS |
| C2 | test_c2_file_map_matches_ls | 读 SKILL.md「## 文件地图」节提取 references/scripts 名；`ls references/*.md`=8、`ls scripts/*.py`=10 集合一一对应 | 0 | 0 | 无 | ✅ PASS |
| C3 | test_c3_new_artifacts_referenced | grep `role-glossary`/`check_terms`/`watchdog_daemon` 于 SKILL.md 全文，三者皆命中 | 0 | 0 | 无 | ✅ PASS |
| C4 | test_c4_checkdocs_picks_highest_version | `python ship-it/scripts/check_docs.py --root . --json` → 选取 spec=`docs/specs/2026-11-24-v5.1.0-skill-self-consistency.md`（含 v5.1.0，不含 v4.7.2） | 0 | 0 | 无 | ✅ PASS |
| C5 | test_c5_checkdocs_degrades_no_version | 临时 fixture（tmp/c5_nover_*、tmp/c5_empty_*）跑 `check_docs --root <fix> --json`：A 无版本号→降级选日期最新 beta + warning；B 空 specs→「没有日期命名的 spec」warning；均无 Traceback；用例结束 rmtree 清理 | 0 | 0 | 无 | ✅ PASS |
| C6 | test_c6_checktext_version_unified | 读 `ship-it/scripts/check_text.py` 断言 docstring 与 argparse description 版本标识均为 5.1.0 且一致 | 0 | 0 | 无 | ✅ PASS |
| C7 | test_c7_skill_md_under_350 | `len(SKILL.md.splitlines())` ≤ 350（实测 340） | 0 | 0 | 无 | ✅ PASS |
| C8 | test_c8_no_rule_lost | 从 spec 附录运行时解析关键词清单（66 个）+ 去空格子串匹配 SKILL.md，全部命中（无规则丢失） | 0 | 0 | 无 | ✅ PASS |
| C9 | test_c9_machine_checks_pass | `check_text.py --root .`=0；`check_docs.py --root .`=0；`check_docs.py --root . --spec <v5.1.0 spec>`=0（三项均过） | 0 | 0 | 无 | ✅ PASS |
| C10 | test_c10_changelog_has_v5_1_0 | 读两份 CHANGELOG：`ship-it/CHANGELOG.md` 顶部节=`## 5.1.0`；根 `CHANGELOG.md` 顶部索引行=`v5.1.0` | 0 | 0 | 无 | ✅ PASS |

### 2.1 C8 匹配方法说明（透明、统一、契约意图派生）

- spec 附录「C8 规则关键词清单」共 5 类 66 个关键词（铁律/反偷懒/反越权/关键原则/常见坑表对策），由测试运行时从 spec 附录解析，**不在测试中硬编码**（测试从契约派生）。
- spec 关键词以紧凑形式书写（如 `spec先于实现`、`执行者≠裁定者`、`9步不跳步`），SKILL.md 正文有自然空格（如 `spec 先于实现`、`执行者 ≠ 裁定者`、`9 步不跳步`）。纯字面子串 grep 会因空格差异产生 16 个「假未命中」（已确认均属空格差异，非规则丢失）。
- 为避免「空格差异」被误判为「规则丢失」，对关键词与 SKILL.md 各自**去掉空格/制表符/全角空格（保留换行以防跨行伪匹配）**后做子串包含判定；该方法对所有关键词统一适用，非逐条调参。
- 结果：66 个关键词去空格判定全部命中 ⇒ C8 PASS。其中 `>50KB guard` 命中于 SKILL.md 流程总览表 Step 3 闸门列「…六项复查；>50KB guard 通过」。

### 2.2 C5 降级用例说明

- 子情形 A（所有 spec 文件名无版本号）：fixture 含 `docs/specs/2026-01-01-alpha.md`、`2026-02-01-beta.md`，`check_docs` 降级选取日期最新的 beta，并输出降级 warning（`降级`/`无文件名版本号`），无 Traceback。
- 子情形 B（docs/specs 为空）：`check_docs` 输出「没有日期命名的 spec」warning，spec 为空，无 Traceback。
- 两 fixture 均建于 `tmp/` 下（mkdtemp 唯一名），用例 `finally` 以 `shutil.rmtree(ignore_errors=True)` 清理；已核查 `tmp/` 无 `c5_*` 残留。

---

## 3. 只读边界确认

- 本会话仅写 `docs/reviews/2026-11-24-tester-start.md`、`docs/reviews/2026-11-24-test-report.md`、`tests/test_v5_1_0_self_consistency.py`（验收测试资产）。
- `git status --porcelain` 证实：`CHANGELOG.md`、`ship-it/CHANGELOG.md`、`ship-it/SKILL.md`、`ship-it/scripts/check_docs.py`、`ship-it/scripts/check_text.py` 的改动为开发侧 v5.1.0 实现，**非本测试员写入**（测试员仅读取做断言）。本测试员新增文件仅上述两份（`tmp/pytest-v510.log` 被 .gitignore 忽略）。
- 未审代码、未审契约；未派发子代理（本会话 subagent 深度已达上限）。

---

## 4. 给主脑的核销建议

- C1–C10 全部 PASS，建议 Step 5 将 spec §9 核销表 10 行「结果」由「待测」回填为 ✅，用例文件列指向 `tests/test_v5_1_0_self_consistency.py`，测试报告列指向本文件。
- 用例名与 spec §9 核销表完全一致（test_c1_version_consistency … test_c10_changelog_has_v5_1_0），满足「用例名在用例文件中出现」「报告里同名 ±2 行内有 PASS」。

---

## 5. 测试证据块（check_test_evidence / 核销校验用）

> path 指向 `tests/test_v5_1_0_self_consistency.py`（sha256 稳定）。run_started_at ≥ 文件 mtime（2026-11-24T12:21:31+08:00），run_finished_at ≥ run_started_at。运行窗口内测试文件 sha256 不变（pre==post）。

- path: tests/test_v5_1_0_self_consistency.py
- pre_sha256: 352e95be5552ea7655ea80ed38d67166f64ed9bd81eb30e45de7403a830567b4
- post_sha256: 352e95be5552ea7655ea80ed38d67166f64ed9bd81eb30e45de7403a830567b4
- run_started_at: 2026-11-24T12:21:45+08:00
- run_finished_at: 2026-11-24T12:21:52+08:00

---

## 6. 报告路径

- 本报告：`docs/reviews/2026-11-24-test-report.md`
- 开工记录：`docs/reviews/2026-11-24-tester-start.md`
- 用例文件：`tests/test_v5_1_0_self_consistency.py`
- 原始 pytest 日志：`tmp/pytest-v510.log`（gitignored，Step 9 清理）
