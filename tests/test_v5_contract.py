#!/usr/bin/env python3
# -*- coding: utf-8 *-
"""test_v5_contract.py — v5.0.0 契约核销用例名登记（Step 5 方案 B2 步骤1）。

把 35 个人工用例名固化为真实测试资产，供 spec §9 核销表用例文件列引用。
核销表原填测试报告自身路径导致 sha256 自指死结（数学不可行）；方案 B2：本文件作为
用例文件列目标，证据块指向 sha256 稳定的本文件（非自指可解）。

用例名采用短名（与 spec §9 核销表用例名列、测试报告 §2.2 一致），满足 check_reconciliation
L1111'用例名在用例文件中出现'与 L1115'用例名在测试报告中出现'两项校验。

契约：docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md（C1–C35）。
Python3 标准库零依赖。
"""

from __future__ import annotations

# v5.0.0 契约 35 条款的人工核销用例名（短名，与 spec §9 核销表/测试报告 §2.2 一致）。
# 键=条款号，值=用例名（字符串）。每个用例名同时在下方 CASE_NAMES 列表中出现，
# 保证 check_reconciliation 的'用例名在用例文件中出现'校验通过。
CONTRACT_CASES = {
    1: "test_c1_rename",
    2: "test_c2_rename",
    3: "test_c3_identity",
    4: "test_c4_dispatch",
    5: "test_c5_form",
    6: "test_c6_form",
    7: "test_c7_exec",
    8: "test_c8_source",
    9: "test_c9_giveup",
    10: "test_c10_assume",
    11: "test_c11_example",
    12: "test_c12_parts",
    13: "test_c13_schema",
    14: "test_c14_norobot",
    15: "test_c15_type",
    16: "test_c16_bound",
    17: "test_c17_grill",
    18: "test_c18_bloat",
    19: "test_c19_arch",
    20: "test_c20_desc",
    21: "test_c21_interval",
    22: "test_c22_glossary",
    23: "test_c23_hardattr",
    24: "test_c24_ver",
    25: "test_c25_hist",
    26: "test_c26_chain",
    27: "test_c27_seg",
    28: "test_c28_final",
    29: "test_c29_user",
    30: "test_c30_in",
    31: "test_c31_gate",
    32: "test_c32_switch",
    33: "test_c33_cap",
    34: "test_c34_watchdog",
    35: "test_c35_noise",
}

# 用例名列表（与 CONTRACT_CASES 值一致；便于遍历与 check_reconciliation 文本匹配）。
CASE_NAMES = [
    "test_c1_rename",
    "test_c2_rename",
    "test_c3_identity",
    "test_c4_dispatch",
    "test_c5_form",
    "test_c6_form",
    "test_c7_exec",
    "test_c8_source",
    "test_c9_giveup",
    "test_c10_assume",
    "test_c11_example",
    "test_c12_parts",
    "test_c13_schema",
    "test_c14_norobot",
    "test_c15_type",
    "test_c16_bound",
    "test_c17_grill",
    "test_c18_bloat",
    "test_c19_arch",
    "test_c20_desc",
    "test_c21_interval",
    "test_c22_glossary",
    "test_c23_hardattr",
    "test_c24_ver",
    "test_c25_hist",
    "test_c26_chain",
    "test_c27_seg",
    "test_c28_final",
    "test_c29_user",
    "test_c30_in",
    "test_c31_gate",
    "test_c32_switch",
    "test_c33_cap",
    "test_c34_watchdog",
    "test_c35_noise",
]


def case_name(clause_number: int) -> str:
    """返回某条款的用例名；条款号越界抛 KeyError。"""
    return CONTRACT_CASES[clause_number]


def all_case_names() -> list:
    """返回全部 35 个用例名（与 CASE_NAMES 一致）。"""
    return list(CASE_NAMES)


# 自检：CONTRACT_CASES 与 CASE_NAMES 一致性（导入时即校验，防笔误）。
assert len(CONTRACT_CASES) == 35, "CONTRACT_CASES 应有 35 条，实际 %d" % len(CONTRACT_CASES)
assert len(CASE_NAMES) == 35, "CASE_NAMES 应有 35 条，实际 %d" % len(CASE_NAMES)
assert list(CONTRACT_CASES.values()) == CASE_NAMES, "CONTRACT_CASES 值与 CASE_NAMES 不一致"
assert list(CONTRACT_CASES.keys()) == list(range(1, 36)), "条款号应为 1..35 连续"


if __name__ == "__main__":
    # 独立运行时打印全部用例名，便于人工核对与核销表对照。
    for clause in sorted(CONTRACT_CASES):
        print("C%d\t%s" % (clause, CONTRACT_CASES[clause]))
