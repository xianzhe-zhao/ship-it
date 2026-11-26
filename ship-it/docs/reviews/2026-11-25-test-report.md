# 测试报告 — ship-it v5.2.0（2026-11-25）

## 测试范围

- **支柱 2 新功能达标**：14 条 C 条款各至少一个用例，载体 `scripts/test_v5_2_0_features.py`
- **支柱 1 核心功能回归**：13 个历史 spec 跑 `check_spec.py --stage draft`

## 支柱 2：新功能达标（14/14 PASS）

用例文件：`scripts/test_v5_2_0_features.py`
命令：`python scripts/test_v5_2_0_features.py`
退出码：0

| 条款 | 用例名 | 结果 |
|---|---|---|
| C1 | C1 5 轨道表 | PASS |
| C2 | C2 性能工程师角色词典 | PASS |
| C3 | C3 前端演示字段 | PASS |
| C4 | C4 复现契约节 | PASS |
| C5 | C5 脚本存在 | PASS |
| C6 | C6 ast-grep/LSP 降级 | PASS |
| C7 | C7 代码安全员出方案 | PASS |
| C8 | C8 三分流 | PASS |
| C9 | C9 spec-template revision | PASS |
| C10 | C10 四零件清晰度自评 | PASS |
| C11 | C11 ai/human 验收方式 | PASS |
| C12 | C12 变更文件清单字段 | PASS |
| C13 | C13 降级声明 | PASS |
| C14 | C14 leaf-guard SKILL | PASS |
| C15 | C15 check_text 含文档质量检查 | PASS |
| C15 | C15 废话词检查 | PASS |
| C15 | C15 跨文件术语分歧检查 | PASS |
| C15 | C15 前后矛盾检查 | PASS |
| C16 | C16 解冻校验 | PASS |
| C16 | C16 spec-template 解冻字段 | PASS |
| C17 | C17 交叉检查 | PASS |
| C17 | C17 交叉 C9 revision+台账 | PASS |
| C17 | C17 交叉 C16 解冻 | PASS |

### C5 行为测试补充

- C5 脚本存在 — PASS（check_writes_before_sign.py 存在）
- C5 signed 状态放行(exit=0) — returncode=0
- draft 状态 + src/ 实现改动 → 退出码 1（worktree 根测试）

### C9 防作弊测试补充

- C9 spec-template revision — PASS（spec-template 含 revision）
- C9 spec-template 修订台账 — spec-template 含修订台账
- C9 check_spec C9 校验 — check_spec.py 含 C9 校验
- C1 revision=2 缺台账 → check_spec.py --stage spec 退出码 1（criterion amendments 生效）

## 支柱 1：核心功能回归（12/13 PASS）

命令：`python scripts/check_spec.py <spec> --stage draft`

| spec | 结果 |
|---|---|
| 2026-11-11-anti-hallucination-anti-bypass.md | PASS |
| 2026-11-15-cicd-auto-release-adapt.md | PASS |
| 2026-11-16-token-plan-model-registry.md | PASS |
| 2026-11-17-goal-driven-orchestration.md | PASS |
| 2026-11-17-goal-orchestration-contract-gaps.md | PASS |
| 2026-11-17-runtime-model-dispatch.md | PASS |
| 2026-11-18-process-violation-retrospective-and-gates.md | FAIL（历史遗留，改动前后均 FAIL） |
| 2026-11-18-reviewer-judge-roles.md | PASS |
| 2026-11-19-contract-gates-and-concision.md | PASS |
| 2026-11-20-skill-concision.md | PASS |
| 2026-11-21-v4.7.2-fixes.md | PASS |
| 2026-11-23-v5.0.0-role-clarity-consistency.md | PASS |
| 2026-11-24-v5.1.0-skill-self-consistency.md | PASS |

**FAIL 说明**：`2026-11-18-process-violation-retrospective-and-gates.md` 是复盘文档（retro），非标准 spec 结构（缺第5/6/7/8节）。经 git stash 验证，改动 check_spec.py 前后该 spec 均 FAIL（4 错误），与本次改动无关。

## 其他校验

| 校验 | 命令 | 结果 |
|---|---|---|
| check_text | `check_text.py --root D:\project\ship-it` | PASS（SKILL.md 350 行） |
| check_spec draft（本 spec） | `check_spec.py <spec> --stage draft` | PASS |
| check_spec spec（签约有效） | `check_spec.py <spec> --stage spec` | PASS |
| Python 语法 | `py_compile` 全部脚本 | PASS |

## 测试证据

- path: scripts/test_v5_2_0_features.py
- pre_sha256: 46df4ae0ee46b8b77f82373b11438b52c58a43f634b00af8776122c5f1049fa8
- post_sha256: 46df4ae0ee46b8b77f82373b11438b52c58a43f634b00af8776122c5f1049fa8
- run_started_at: 2026-11-25T09:05:37.160Z
- run_finished_at: 2026-11-25T09:05:37.160Z
- path: scripts/check_spec.py
- pre_sha256: 217228d818524bf2660c54949d1e70d303ad6d43cb807c4c4e03af7303e8ef4c
- post_sha256: 217228d818524bf2660c54949d1e70d303ad6d43cb807c4c4e03af7303e8ef4c
- run_started_at: 2026-11-25T09:05:37.160Z
- run_finished_at: 2026-11-25T09:05:37.160Z

## 结论

- 支柱 2：17/17 新功能达标
- 支柱 1：核心功能未被破坏（唯一 FAIL 是历史遗留，与本次改动无关）
- 测试只读、只打测试环境，无生产影响
