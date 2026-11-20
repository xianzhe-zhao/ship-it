# 2026-11-20 测试报告（v4.7.1 rev4 / C1–C12）

- spec：`docs/specs/2026-11-20-skill-concision.md`（spec_revision 4，sign_hash `84ec58d8817ce900e74286350c31c89b40bfed7826202ea823b8a0814210b8e2`）
- 命令：`SHIP_IT_VERIFY=1 python tests/run_suite.py`（全量含 @slow；4 分块并行）
- run_started_at：2026-11-20T12:57:54+08:00
- run_finished_at：2026-11-20T13:00:59+08:00
- 结果：tests=65 failures=0 errors=0 skipped=0；budget PASS；耗时 184.475s（上限 300s）
- 环境：Windows / Python 3.11.9；测试从契约派生；C9 速度门禁 PASS。

## 用例结果（C1–C12）

- test_c1_transport_boundary：PASS（C1，tests/test_text_quality.py）
- test_c2_remote_write_boundary：PASS（C2，tests/test_text_quality.py）
- test_c3_text_quality：PASS（C3，tests/test_text_quality.py）
- test_c4_check_text：PASS（C4，tests/test_text_quality.py）
- test_c5_gates：PASS（C5，tests/test_text_quality.py）
- test_c6_first_write_marker：PASS（C6，tests/test_process_gates.py）
- test_c7_pause_pre_change：PASS（C7，tests/test_process_gates.py）
- test_c8_git_check_revisions：PASS（C8，tests/test_process_gates.py）
- test_c9_test_speed：PASS（C9，tests/test_process_gates.py）
- test_c10_commit_order：PASS（C10，tests/test_process_gates.py）
- test_c11_reviewer_liveness：PASS（C11，tests/test_process_gates.py）
- test_c12_reviewer_sole_aggregation：PASS（C12，tests/test_process_gates.py）

## 验收项对应（A11/A12）

- A11：test_c11_reviewer_liveness：PASS（patrol 末轮 last_active_at 阈值正/负例）
- A12：test_c12_reviewer_sole_aggregation：PASS（汇总来源路径存在/不存在/叶子会话）

## 测试文件证据（C6）

### tests/test_process_gates.py
- path: tests/test_process_gates.py
- pre_sha256: 3bef8c4416d635f1ef74f11549ef428874f050e8f0e7d14877c93eba77c6efcd
- post_sha256: 3bef8c4416d635f1ef74f11549ef428874f050e8f0e7d14877c93eba77c6efcd
- run_started_at: 2026-11-20T12:57:54+08:00
- run_finished_at: 2026-11-20T13:00:59+08:00

### tests/test_text_quality.py
- path: tests/test_text_quality.py
- pre_sha256: 1242f8b012e3eff0abcf6a66ec50514a18f1d3635fac33723276b58b2fe79c76
- post_sha256: 1242f8b012e3eff0abcf6a66ec50514a18f1d3635fac33723276b58b2fe79c76
- run_started_at: 2026-11-20T12:57:54+08:00
- run_finished_at: 2026-11-20T13:00:59+08:00

### tests/test_reviewer_judge_contract.py
- path: tests/test_reviewer_judge_contract.py
- pre_sha256: 1d584382b73f1f15014e845717b63388e4fa62f17fceeb0f52e6c615fd5b5545
- post_sha256: 1d584382b73f1f15014e845717b63388e4fa62f17fceeb0f52e6c615fd5b5545
- run_started_at: 2026-11-20T12:57:54+08:00
- run_finished_at: 2026-11-20T13:00:59+08:00

### tests/test_c10_skip.py
- path: tests/test_c10_skip.py
- pre_sha256: c79ce91d89f786805c63ac7fd989d183110dac861c8cb0b0492b2d41a659ce44
- post_sha256: c79ce91d89f786805c63ac7fd989d183110dac861c8cb0b0492b2d41a659ce44
- run_started_at: 2026-11-20T12:57:54+08:00
- run_finished_at: 2026-11-20T13:00:59+08:00

### tests/test_a19_accept_hash.py
- path: tests/test_a19_accept_hash.py
- pre_sha256: a7a4b91cfb765117e112078e7bbf45f0397fea7fe3066c50a308cf3e66d8634d
- post_sha256: a7a4b91cfb765117e112078e7bbf45f0397fea7fe3066c50a308cf3e66d8634d
- run_started_at: 2026-11-20T12:57:54+08:00
- run_finished_at: 2026-11-20T13:00:59+08:00

## 核销率

- 核销率: 12/12（C1–C12 每条至少一个用例；全部 PASS）
- 分级回归：test_process_gates 26、test_text_quality 5、test_reviewer_judge_contract 28、test_c10_skip 3、test_a19_accept_hash 3，合计 65 tests / 0 failures / 0 errors / 0 skipped。
- 速度：全量 184.475s < 300s；`--fast` 模式 56 tests。
