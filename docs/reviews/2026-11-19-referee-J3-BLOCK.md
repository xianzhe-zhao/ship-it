# 2026-11-19 裁判员 J3 报告（BLOCK）— 契约核销与证据真实性

角色：referee（裁判员 J3）
审查者：referee-j1f
会话标识：referee-j1f / dsh-7a42e66b-3e7b
spec_revision：4
spec_hash：fd8ef0149b6b4143fd6847f47cbd14e23fcdb6420313f8271242ea23a84428bf
未参与编码声明：是
未参与 spec 编写声明：是
结论：BLOCK（1 项 C10；其余核销与证据核验全部通过）
汇总来源：docs/reviews/2026-11-19-test-report.md（SHA ACDF028D…）、referee-J1.md、auditor-patrol.md。

## 已核验通过
1. §9 5 列表头、C1–C18 全 ✅、核销率 18/18、footer 报告路径。
2. 18 个用例名均在 tests/test_process_gates.py；报告同名 ±2 行 PASS。
3. test_process_gates.py pre=post=908EC9D4…；test_reviewer_judge_contract.py pre=post=8C3C9B5C…。
4. 运行窗口 16:02:42–16:26:28 / 16:02:33–16:02:40；文件 mtime 早于 run_started。
5. §§1–8 独立复算 fd8ef014…；check_spec --stage verify PASS。
6. 报告 SHA ACDF028D… 与 spec §9 一致。

## BLOCK：C10 核销与在案证据矛盾
7. C10 要求 SKIP 退出码 2；旧套 28 tests OK（1 skip）exit 0，skip 来源 test_reviewer_judge_contract.py:440（@unittest.skipUnless(SHIP_IT_VERIFY=1)）。按 C10 即 FAIL，而 §9 C10 仍标 ✅。
8. 判定依据：C10 前置为“测试脚本支持 SKIP”，无“仅限验收脚本”例外；C11 冲突取严。
9. 最小处置：①SHIP_IT_VERIFY=1 重跑旧套（预期 28 tests、0 skip）；②补行为级 C10 用例；③更新报告 SHA 与 §9 C10 行，再交 J3 复核。

## 附带观察
10. check_roles --stage verify FAIL 4：缺 referee-J3/security/auditor/failure-log；补齐后重跑。
11. C3 731 / C5 640 字符仅 WARN（C11 硬限 800）。
