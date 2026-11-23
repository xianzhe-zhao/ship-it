# 2026-11-19 测试报告（v4.7.0 契约闸门 C1–C18 / A19）

> 唯一契约：`docs/specs/2026-11-19-contract-gates-and-concision.md`（spec_revision 5，sign_hash §§1–8 = `5d99c28a…`；A1–A19 复选框 `[ ]`/`[x]` 归一化为 `[ ]`）。
> 测试从契约派生；本报告由 runner 生成，记录每个测试文件的 SHA-256 与运行窗口。

## 运行命令与结果

- `python -m unittest tests.test_process_gates -v` → 19 tests OK（0 FAIL / 0 ERROR），07:41:31–08:03:44。
- `$env:SHIP_IT_VERIFY="1"; python -m unittest tests.test_reviewer_judge_contract -v` → 28 tests OK（0 skip / 0 FAIL），08:03:58–08:04:05。
- `python -m unittest tests.test_c10_skip -v` → 3 tests OK（C10 行为级：sample skip → runner exit 2），08:04:05–08:04:08。
- `python -m unittest tests.test_a19_accept_hash -v` → 3 tests OK（A19 行为级：A [ ]/[x] hash 相同、填 acceptance 后 accept PASS、§§1–8 文本改一行 FAIL），07:41:31–07:42:18。
- 测试文件冻结：运行窗口内 pre_sha256 == post_sha256；无运行中改测试文件。

## 测试文件证据

### tests/test_process_gates.py
- path: tests/test_process_gates.py
- pre_sha256: 61CCB152A5CBBF88980B8166F4828A419036CC3136F4DDC5459953430CCADED9
- post_sha256: 61CCB152A5CBBF88980B8166F4828A419036CC3136F4DDC5459953430CCADED9
- run_started_at: 2026-11-20T07:41:31+08:00
- run_finished_at: 2026-11-20T08:03:44+08:00

### tests/test_reviewer_judge_contract.py
- path: tests/test_reviewer_judge_contract.py
- pre_sha256: 8C3C9B5CC676AB68395C87DE126B5781C98A485E5BC1F9E99D84DB55FC0E0A33
- post_sha256: 8C3C9B5CC676AB68395C87DE126B5781C98A485E5BC1F9E99D84DB55FC0E0A33
- run_started_at: 2026-11-20T08:03:58+08:00
- run_finished_at: 2026-11-20T08:04:05+08:00

### tests/test_c10_skip.py
- path: tests/test_c10_skip.py
- pre_sha256: C79CE91D89F786805C63AC7FD989D183110DAC861C8CB0B0492B2D41A659CE44
- post_sha256: C79CE91D89F786805C63AC7FD989D183110DAC861C8CB0B0492B2D41A659CE44
- run_started_at: 2026-11-20T08:04:05+08:00
- run_finished_at: 2026-11-20T08:04:08+08:00

### tests/test_a19_accept_hash.py
- path: tests/test_a19_accept_hash.py
- pre_sha256: 09B286A2A16181FF9430F376242ECE4419EDCA4271F31E71CADF4429110F81A6
- post_sha256: 09B286A2A16181FF9430F376242ECE4419EDCA4271F31E71CADF4429110F81A6
- run_started_at: 2026-11-20T07:41:31+08:00
- run_finished_at: 2026-11-20T07:42:18+08:00

## 用例结果（C1–C18 + A19）

- test_c1_sign_exact_word: PASS
- test_c2_accept_exact_word: PASS
- test_c3_sign_accept_block: PASS
- test_c4_git_check_spec_first: PASS
- test_c5_roles_gate: PASS
- test_c6_reconciliation_truth: PASS
- test_c7_guard_large_write: PASS
- test_c8_entry_inventory: PASS
- test_c9_p_c_number_isolation: PASS
- test_c10_skip_must_exit_2: PASS（行为级：sample skip → runner exit 2；无 skip → 0；FAIL → 1）
- test_c10_skip_semantics: PASS（文档断言，保留）
- test_c11_concise_style: PASS
- test_c12_version_compat: PASS
- test_c13_path_and_secret_safety: PASS
- test_c14_auditor_start_gate: PASS
- test_c15_role_start_report: PASS
- test_c16_contract_change_pause: PASS
- test_c17_failure_attempts: PASS
- test_c18_docs_consistency: PASS
- test_a19_sign_hash_scope: PASS（真实 spec --print-sign-hash == front matter sign_hash；§9 填 ✅ 后 hash 不变且 verify PASS；§§1–8 改动 FAIL；§9-only 改动 PASS）
- test_a19_acceptance_marks_hash_stable: PASS（A [ ] 与 A [x] 的 sign hash 相同，归一化为 [ ]）
- test_a19_fill_acceptance_then_accept_pass: PASS（填 A/acceptance 后 --stage accept PASS）
- test_a19_sections_1_8_change_fails: PASS（§§1–8 文本改一行 → hash 变、--stage spec FAIL）

## 旧套回归（核心回归基线）

- `SHIP_IT_VERIFY=1` 后 28 tests OK、0 skip、exit 0（C10：无 SKIP 才允许退出码 0）。
- test_c11_version_and_sync: PASS（版本 4.7.0 三处一致）
- test_c14_reviewer_patrol: PASS（旧断言已按 C18 旧口径改为“间隔 1 分钟”）
- test_c5_main_decision_set: PASS（旧断言已按 C17 旧口径改为“主脑不得自做”）
- test_spec_verify_exit_zero: PASS（SHIP_IT_VERIFY=1，check_spec --stage verify 退出码 0）

- 核销率: 18/18（C1–C18 每条至少一个用例；C10 行为级用例见 test_c10_skip.py；A19 由 test_a19_sign_hash_scope + test_a19_accept_hash 覆盖）
