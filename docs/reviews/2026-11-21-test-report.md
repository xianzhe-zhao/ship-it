# 2026-11-21 测试报告（v4.7.2 rev17 / C1–C14）

- spec：`docs/specs/2026-11-21-v4.7.2-fixes.md`（spec_revision 17，sign_hash `b2347f41506b7e646870884c448d170a36617c8e54c471f7f8ff61537a898e2d`）
- 命令：`SHIP_IT_VERIFY=1 python tests/run_suite.py`（全量含 @slow；4 分块并行）
- run_started_at：2026-11-23T11:29:56+08:00
- run_finished_at：2026-11-23T11:34:43+08:00
- 结果：tests=79 failures=0 errors=0 skipped=0；budget PASS；耗时 286.384s（上限 300s）
- 测试文件冻结：全部测试文件 mtime 早于 run_started_at（运行后未改动）；pre_sha256 = post_sha256。
- 环境：Windows / Python 3.11.9；C9 速度门禁 PASS（<300s）。

## 用例结果（C1–C14）

- test_c1_out_root：PASS（C1，tests/test_process_gates.py）
- test_c2_failure_log_secret：PASS（C2，tests/test_process_gates.py）
- test_c3_hook_root：PASS（C3，tests/test_process_gates.py）
- test_c4_check_text_root：PASS（C4，tests/test_process_gates.py）
- test_c5_ci_pin：PASS（C5，tests/test_process_gates.py）
- test_c6_default_base：PASS（C6，tests/test_process_gates.py）
- test_c7_guard_restore：PASS（C7，tests/test_process_gates.py）
- test_c8_reviewer_dispatch：PASS（C8，tests/test_process_gates.py）
- test_c9_cleanup：PASS（C9，tests/test_process_gates.py）
- test_c10_version：PASS（C10，tests/test_process_gates.py）
- test_c11_gates：PASS（C11，tests/test_text_quality.py）
- test_c12_reviewer_mandatory：PASS（C12，tests/test_process_gates.py）
- test_c13_role_reuse：PASS（C13，tests/test_process_gates.py）
- test_c14_lead_quiet：PASS（C14，tests/test_process_gates.py）

## 验收项对应（A12/A13/A14）

- A12：test_c12_reviewer_mandatory：PASS（reviewer_dispatch_at 仅顺序、非 reviewer 四角色、auditor 豁免；heartbeat_effective_at 之后轮次 <=60s、暂停段剔除/跨暂停跳过、末轮新鲜度、汇总五角色）
- A13：test_c13_role_reuse：PASS（source 枚举、new_* 附理由、reuse 放行）
- A14：test_c14_lead_quiet：PASS（SKILL/team-mode 文档断言：提醒各一次、不重复催促、心跳可能用户可见、仅活跃期、间隙暂停、被动响应）

## 测试文件证据（C6）

### tests/test_process_gates.py
- path: tests/test_process_gates.py
- pre_sha256: 5434c267171e14865ba338e2ce8ab7ae923a71f945369e3dac61d17ead9ef29d
- post_sha256: 5434c267171e14865ba338e2ce8ab7ae923a71f945369e3dac61d17ead9ef29d
- run_started_at: 2026-11-23T11:29:56+08:00
- run_finished_at: 2026-11-23T11:34:43+08:00

### tests/test_text_quality.py
- path: tests/test_text_quality.py
- pre_sha256: c3ee6a2d032bfd4b4670bfa5e6a7ae572df12131ad1611cc34a80d6c67b754dc
- post_sha256: c3ee6a2d032bfd4b4670bfa5e6a7ae572df12131ad1611cc34a80d6c67b754dc
- run_started_at: 2026-11-23T11:29:56+08:00
- run_finished_at: 2026-11-23T11:34:43+08:00

### tests/test_reviewer_judge_contract.py
- path: tests/test_reviewer_judge_contract.py
- pre_sha256: bc3be90a4123db0719c757b14e6b4c1db383fe0c7bef0cb3888359c2ee2470e4
- post_sha256: bc3be90a4123db0719c757b14e6b4c1db383fe0c7bef0cb3888359c2ee2470e4
- run_started_at: 2026-11-23T11:29:56+08:00
- run_finished_at: 2026-11-23T11:34:43+08:00

### tests/test_c10_skip.py
- path: tests/test_c10_skip.py
- pre_sha256: c79ce91d89f786805c63ac7fd989d183110dac861c8cb0b0492b2d41a659ce44
- post_sha256: c79ce91d89f786805c63ac7fd989d183110dac861c8cb0b0492b2d41a659ce44
- run_started_at: 2026-11-23T11:29:56+08:00
- run_finished_at: 2026-11-23T11:34:43+08:00

### tests/test_a19_accept_hash.py
- path: tests/test_a19_accept_hash.py
- pre_sha256: a7a4b91cfb765117e112078e7bbf45f0397fea7fe3066c50a308cf3e66d8634d
- post_sha256: a7a4b91cfb765117e112078e7bbf45f0397fea7fe3066c50a308cf3e66d8634d
- run_started_at: 2026-11-23T11:29:56+08:00
- run_finished_at: 2026-11-23T11:34:43+08:00

## 核销率

- 核销率: 14/14（C1–C14 每条至少一个用例；全部 PASS）
- 分级回归：test_process_gates 39、test_text_quality 6、test_reviewer_judge_contract 28、test_c10_skip 3、test_a19_accept_hash 3，合计 79 tests / 0 failures / 0 errors / 0 skipped。
- 速度：全量 286.384s < 300s；`--fast` 模式 69 tests。
