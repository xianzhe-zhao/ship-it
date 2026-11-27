# 测试报告 — 2026-11-27

## 测试环境

- 系统：Windows 11
- Python：3.14
- 测试框架：pytest
- 测试命令：`python -m pytest tests/test_process_gates.py -v`

## 测试结果

### 总体统计

- 总测试数：121
- 通过：117
- 失败：0
- 错误：0
- 跳过：4

### 跳过原因

4 个测试因环境限制跳过（非本次修复引入）：
- test_c11_concise_style：需要 git-push-firewall skill（本机未安装）
- test_c12_version_compat：需要 git-push-firewall skill（本机未安装）
- test_c18_docs_consistency：需要 git-push-firewall skill（本机未安装）
- test_c10_skip：需要 git-push-firewall skill（本机未安装）

### 本次修复验证

| 条款 | 测试用例 | 结果 | 说明 |
|---|---|---|---|
| C1 测试路径对齐 | test_c1_path_alignment | ✅ PASS | 所有测试路径从 `docs/specs/` 改为 `ship-it/docs/specs/` |
| C2 版本动态读取 | test_c2_version_dynamic | ✅ PASS | 测试从 SKILL.md frontmatter 动态读版本 |
| C3 run_suite 返回码 | test_c3_run_suite_return_code | ✅ PASS | 有 FAIL/ERROR 返回 1，纯 SKIP 返回 2 |
| C4 local_check 编码 | test_c4_local_check_encoding | ✅ PASS | 加 `errors="replace"` 参数 |
| C5 check_docs 转义 | test_c5_check_docs_escape | ✅ PASS | docstring 改为 raw string |
| C6 测试残留清理 | test_c6_test_cleanup | ✅ PASS | 用 try/finally 清理 outside.md |
| C7 方案分析产出物 | test_c7_analysis_deliverable | ✅ PASS | HTML 文件存在且包含决策树结构标记 |
| C8 可视化修复报告 | test_c8_visual_report | ✅ PASS | HTML 文件存在且包含 before/after 对比、逻辑流程图 |

### 本地闸门验证

```
[PASS] 1. check_spec --git-check
[PASS] 2. check_text --allow-missing-git-push
[PASS] 3. check_docs --root .
[PASS] 4. tests.run_suite (exit=2, 有 SKIP 但无 FAIL/ERROR)
```

## 结论

所有 8 个条款（C1-C8）全部通过核销，测试通过率 100%（排除环境限制的 4 个跳过测试）。
