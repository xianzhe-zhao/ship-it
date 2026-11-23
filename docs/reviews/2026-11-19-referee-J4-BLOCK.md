# 2026-11-19 裁判员 J4 报告（BLOCK）— 验收 readiness

角色：referee（裁判员 J4）
审查者：referee-j1f
会话标识：referee-j1f / dsh-7a42e66b-3e7b
spec_revision：4
spec_hash：fd8ef0149b6b4143fd6847f47cbd14e23fcdb6420313f8271242ea23a84428bf
未参与编码声明：是
未参与 spec 编写声明：是
结论：BLOCK（验收勾选与 sign_hash 书面定义互斥）
汇总来源：test-report F10F7C84…、referee-J1/J3、security、auditor、patrol、failure-log。

## 已通过
三门禁 PASS（check_spec verify / check_roles verify / check_docs）；脚本/报告/测试文件 hash 一致；§9 18/18；签约块完整；验收块为空。

## BLOCK
A1–A19 在 §6 ⊂ §§1–8；按书面定义勾选 `[x]` 会改变 sign_hash（实测 406f9386… ≠ fd8ef014…）；代码层归一化未写入 spec（check_spec.py:118-138），A19 又要求“§§1–8 改动 → FAIL”，两者互斥。
最小处置：按用户选 A，在 C1/C3/§3/A19 补“A 复选框 `[ ]`/`[x]` 归一化为 `[ ]` 后参与哈希；验收勾选不改 sign_hash；A19 的 §§1–8 改动不含 A 复选框状态”；改 spec → 新 hash → 暂停/重签 → 刷新报告/测试 → 重跑门禁 → 再验收。
