# 安全审查日志 — ship-it

> 周期安全审查记录（默认每月一次）。每次变更 Step 2 前做增量检查；完整审查按 skill `ship-it`「周期安全审查」playbook。
> P0 未清零不开工/不发布。凭据永不入库。

## 2026-11-16 — 增量检查（Token Plan 模型注册表与成本感知分配变更）

- **范围**：新增 `docs/deploy-runbook.md`、`docs/security-review-log.md`、`docs/specs/2026-11-16-token-plan-model-registry.md`；修改 `ship-it/references/team-mode.md`、`ship-it/SKILL.md`、`ship-it/CHANGELOG.md`、`CHANGELOG.md`、`README.md`。
- **依赖核验**：本仓库**零第三方运行时依赖**（纯 Markdown + Python 标准库脚本 `check_spec.py`，仅 import argparse/io/json/re/sys/pathlib）。无 `package.json`/`requirements.txt`/`pyproject.toml`。`npm audit` / OSV **不适用**（无依赖可审计）。
- **联网核验状态**：本次为零依赖纯文档/流程规则改动，无新增外部输入面，无需联网核验新依赖漏洞；模型能力/价位信息来自官方文档（alibabacloud.com / help.aliyun.com）与本会话实测探针，非运行时依赖。
- **脚本审查**：`check_spec.py` 仅读取 spec 文件做正则校验，无 `eval`/`exec`/网络/文件写入；`install`/`update`/`build` 脚本仅 junction/symlink + `git pull` + zip 打包，无凭据处理。
- **凭据扫描**：新增/修改文件不含 API key 值（无 `sk-` 密钥串、无 token）；runbook 仅引用环境变量名 `BAILIAN_TPP_API_KEY` 与「见 ~/.dsh/.credentials.yaml」，符合脱敏约定。
- **P0/P1/P2 清单**：P0 = 0；P1 = 0；P2 = 0。
- **结论**：**零新增攻击面**，无凭据入库，无新增依赖。本次变更不引入安全风险。仓库首次建立本审查日志；后续按月周期审查，高危变更（新增依赖/新外部输入面）触发增量核验。
