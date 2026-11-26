#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_v5_2_0_features.py — v5.2.0 十四条优化落地验证（Step 4 支柱 2）。

用法：
    python test_v5_2_0_features.py [--root <ship-it 仓库根>]

退出码：0 = 全部 14 条 C 已落地；1 = 有缺失。
原理：用断言验证 14 条 C 条款对应的文档/脚本内容已存在（grep 关键短语 + 脚本行为）。
      这是 spec §9 核销表的用例载体——ship-it 仓库惯例是 check_*.py 脚本即测试，
      不建 tests/ 目录。
编码：UTF-8；Python 3.8+ 标准库。
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def read(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def contains(text, needle):
    return needle in text


def check(label, condition, evidence=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] %s%s" % (status, label, (" — " + evidence) if evidence else ""))
    return condition


def main():
    ap = argparse.ArgumentParser(description="v5.2.0 特性验证")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent), help="ship-it 仓库根")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    results = []

    skill = read(root / "SKILL.md")
    tmpl = read(root / "references" / "spec-template.md")
    team = read(root / "references" / "team-mode.md")
    gloss = read(root / "references" / "role-glossary.md")

    # C1：5 条变更轨道 + 步骤序列表
    c1 = check("C1 5 轨道表",
               all(tmpl.count(x) >= 1 for x in ["feature", "bug", "refactor", "perf", "framework"]) and
               "步骤序列" in tmpl and "关键差异点" in tmpl,
               "spec-template 含 5 轨道 + 步骤序列 + 差异点")
    results.append(("C1", c1))

    # C2：性能工程师角色（咨询顾问模式）
    c2a = check("C2 性能工程师角色词典", "性能工程师" in gloss, "role-glossary 含性能工程师")
    c2b = check("C2 性能工程师角色卡", "性能工程师" in team and "咨询顾问模式" in team, "team-mode 含角色卡+咨询顾问")
    c2c = check("C2 性能调优专项", "性能调优专项" in team, "team-mode 形态3含性能调优专项")
    results.append(("C2", c2a and c2b and c2c))

    # C3：feature 轨道前端演示页
    c3 = check("C3 前端演示字段", "前端演示" in tmpl and "preview.html" in tmpl, "spec-template 含前端演示+preview.html")
    results.append(("C3", c3))

    # C4：bug 轨道复现契约
    c4 = check("C4 复现契约节", "复现契约" in tmpl and "复现步骤" in tmpl and "当前现象" in tmpl and "期望现象" in tmpl and "严重度" in tmpl,
               "spec-template 含复现契约四要素")
    results.append(("C4", c4))

    # C5：check_writes_before_sign.py 事前拦截
    cws = root / "scripts" / "check_writes_before_sign.py"
    c5a = check("C5 脚本存在", cws.is_file(), str(cws))
    c5_ok = False
    if c5a:
        # 行为测试：用当前 spec（已 signed）应退出 0
        spec = root / "docs" / "specs" / "2026-11-25-v5.2.0-tracks-roles-degradation.md"
        if spec.is_file():
            proc = subprocess.run(
                [sys.executable, str(cws), str(spec), "--root", str(root)],
                capture_output=True, text=True, timeout=30,
            )
            c5_ok = (proc.returncode == 0)
            check("C5 signed 状态放行(exit=0)", c5_ok, "returncode=%d" % proc.returncode)
        else:
            check("C5 spec 存在", False, str(spec))
    results.append(("C5", c5a and c5_ok))

    # C6：ast-grep/LSP 影响面分析
    c6 = check("C6 ast-grep/LSP 降级", "ast-grep" in skill and "LSP references" in skill and "降级为" in skill,
               "SKILL.md 含 ast-grep/LSP + 降级")
    results.append(("C6", c6))

    # C7：代码安全员升级咨询顾问模式
    c7a = check("C7 代码安全员出方案", "出有依据修复方案" in team or "有依据" in team, "team-mode 含出有依据方案")
    c7b = check("C7 P0 不对称约束", "P0" in team and "不得驳回" in team, "team-mode 含 P0 不得驳回")
    results.append(("C7", c7a and c7b))

    # C8：中途变更三分流 + 冻结 + backlog
    c8a = check("C8 三分流", "中途变更三分流" in skill or "三分流" in skill, "SKILL.md 含三分流")
    c8b = check("C8 冻结已通过", "冻结已通过" in skill, "SKILL.md 含冻结已通过")
    c8c = check("C8 backlog", "backlog" in skill, "SKILL.md 含 backlog")
    results.append(("C8", c8a and c8b and c8c))

    # C9：criterion amendments（条款版本号 + 修订台账）
    c9a = check("C9 spec-template revision", "revision:" in tmpl or "revision：" in tmpl, "spec-template 含 revision")
    c9b = check("C9 spec-template 修订台账", "修订台账" in tmpl, "spec-template 含修订台账")
    # check_spec.py 含 C9 校验逻辑
    cspec = read(root / "scripts" / "check_spec.py")
    c9c = check("C9 check_spec C9 校验", "C9" in cspec and "修订台账" in cspec, "check_spec.py 含 C9 校验")
    results.append(("C9", c9a and c9b and c9c))

    # C10：Step 1 歧义度自评
    c10 = check("C10 四零件清晰度自评", "四零件清晰度自评" in tmpl and "高/中/低" in tmpl,
                "spec-template 含四零件清晰度")
    results.append(("C10", c10))

    # C11：核销 ai/human 双模
    c11 = check("C11 ai/human 验收方式", "验收方式" in tmpl and "ai" in tmpl and "human" in tmpl,
                "spec-template 含验收方式 ai/human")
    results.append(("C11", c11))

    # C12：modified_files 局部 Git 校验
    c12a = check("C12 变更文件清单字段", "变更涉及的文件清单" in tmpl, "spec-template 含文件清单字段")
    c12b = check("C12 局部 Git 校验", "局部 Git 校验" in skill, "SKILL.md 含局部 Git 校验")
    results.append(("C12", c12a and c12b))

    # C13：graceful degradation 系统化
    c13 = check("C13 降级声明", "降级声明" in tmpl and "可选能力缺失须显式降级声明" in skill,
                "spec-template + SKILL.md 含降级声明")
    results.append(("C13", c13))

    # C14：leaf-guard 叶子代理工具隔离
    c14a = check("C14 leaf-guard SKILL", "leaf-guard" in skill and "tools.restrict" in skill, "SKILL.md 含 leaf-guard")
    c14b = check("C14 leaf-guard team-mode", "leaf-guard" in team or "tools.restrict" in team, "team-mode 含 leaf-guard")
    results.append(("C14", c14a and c14b))

    # C15：验收前文档质量检查（机器 + 裁判员 J2）
    cspec_txt = read(root / "scripts" / "check_text.py")
    c15a = check("C15 check_text 含文档质量检查", "check_doc_quality" in cspec_txt, "check_text.py 含 check_doc_quality")
    c15b = check("C15 废话词检查", "FLUFF_WORDS" in cspec_txt or "废话词" in cspec_txt, "check_text.py 含废话词检查")
    c15c = check("C15 跨文件术语分歧检查", "TERM_PAIRS" in cspec_txt or "术语分歧" in cspec_txt, "check_text.py 含跨文件术语分歧检查")
    c15d = check("C15 前后矛盾检查", "count_patterns" in cspec_txt or "前后矛盾" in cspec_txt, "check_text.py 含前后矛盾检查")
    results.append(("C15", c15a and c15b and c15c and c15d))

    # C16：C8 冻结已通过的机器闸门
    cspec_txt2 = read(root / "scripts" / "check_spec.py")
    c16a = check("C16 check_spec 含解冻校验", "C16" in cspec_txt2 and "解冻" in cspec_txt2, "check_spec.py 含 C16 解冻校验")
    c16b = check("C16 spec-template 解冻字段", "解冻" in tmpl, "spec-template 含解冻记录字段")
    results.append(("C16", c16a and c16b))

    # C17：条款-实现一致性——用例名：C17 交叉检查（条款关键词 vs 实现关键词交叉检查）
    # 通用检查：条款正文提到的检查项，实现里要有对应代码
    def cross_check(clause_id, clause_keywords, impl_file, impl_keywords):
        ok = all(k in impl_file for k in impl_keywords)
        check("C17 交叉 " + clause_id + " " + "+".join(clause_keywords), ok, "实现含 " + "+".join(impl_keywords))
        return ok
    cti = read(root / "scripts" / "check_text.py")
    csi = read(root / "scripts" / "check_spec.py")
    c17a = cross_check("C15", ["废话词","跨文件","前后矛盾"], cti, ["FLUFF_WORDS","TERM_PAIRS","count_patterns"])
    c17b = cross_check("C9", ["revision","台账"], csi, ["revision","修订台账"])
    c17c = cross_check("C16", ["解冻"], csi, ["解冻"])
    results.append(("C17", c17a and c17b and c17c))



    # 汇总
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print("\n汇总：%d/%d 条 C 通过" % (passed, total))
    failed = [cid for cid, ok in results if not ok]
    if failed:
        print("失败条款：%s" % "、".join(failed), file=sys.stderr)
        sys.exit(1)
    print("结果：PASS（%d/%d）" % (passed, total))
    sys.exit(0)


if __name__ == "__main__":
    main()