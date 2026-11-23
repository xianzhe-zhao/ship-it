# deploy-runbook — ship-it 源码仓库

> 本文件只放「本项目才知道的事」：环境值、模型能力清单（运行时派发参考）与默认路由、部署/回退/验证、核心功能清单、安全审查周期、服务红线。**不复述通用 9 步流程**（流程见全局 skill `ship-it`）。
> 模型信息一律落在本文件（skill 正文不写死模型名）；同机新项目可直接复制「模型能力清单」节约定，不重复拉取。

## 系统形态与部署通道

- **系统形态**：单系统。本仓库是 ship-it skill 的**源码仓库**，无独立 test/prod 服务器。
- **部署通道**：手动/脚本（真源 junction 模式）。`install.ps1`/`install.sh` 给 `ship-it/` 在 `~/.agents/skills/` 建 junction/symlink；`update.ps1`/`update.sh` 执行 `git pull`；`build.ps1`/`build.sh` 打包 `.skill` 到 `dist/`（不入库）。
- **生效时机**：改 `ship-it/` 下文件存盘即生效（DSH/Codex 实时重扫 `~/.agents/skills`）；skill 正文变更需**下一轮对话**重新加载才被模型读到。无 CI/CD 自动发布（仓库无 `.github/workflows`）。
- **版本来源（唯一真源）**：`ship-it/SKILL.md` frontmatter `version` + `ship-it/CHANGELOG.md`（skill 版本）+ `CHANGELOG.md`（仓库分发记录）。三处必须一致，**当前 v4.7.0**。
- **凭据纪律**：本文件及全仓库**不写任何密钥值**。办公环境 `aipro` 的凭据环境变量名为 `AIPRO_API_KEY`（值见 `~/.dsh/.credentials.yaml`，不入库）；家用环境 Token Plan 用 `BAILIAN_TPP_API_KEY`。

## 核心功能清单（分级回归依据，只读）

1. `ship-it/SKILL.md` 可加载：frontmatter 合法、`version` 可解析。
2. `ship-it/scripts/check_spec.py` 正确校验 spec：`--stage draft|spec|verify|accept` 四阶段退出码符合预期；旧 spec 按 legacy 放行。
3. `ship-it/scripts/check_roles.py` 正确校验审查报告与开工/暂停闸门：`--stage start|pause|sign|verify|accept`；缺报告/缺 start artifact/start 晚于实现/缺 pause 记录/身份重复/越界/密钥模式 → 非零退出。
4. `ship-it/scripts/check_docs.py` 正确体检全文：`--root .`；旧口径/过期计数/重复/超长/跨文件矛盾 → 非零退出；allowlist 内不报。
5. `ship-it/scripts/guard_large_write.py` 正确保护大文件：`prepare|check|restore`；缩水/乱码/尾标丢失 → `check` 非零退出，`restore` 可恢复。
6. `ship-it/references/` 交叉引用完整：SKILL.md 引用的 reference 文件（含 `rule-style.md`）均存在。
7. `install`/`update`/`build` 脚本语法可用（PowerShell/Bash 解析无错）。

> 触及上述任一项 → 核心功能回归；否则轻量冒烟。回归只读、不改业务数据、不发付费请求。

## 安全审查周期

- 周期：**每月一次**（本仓库零第三方运行时依赖、纯 Markdown + Python 标准库脚本，低危）。
- 日志：`docs/security-review-log.md`（入 git）。
- 增量检查：每次变更 Step 2 前查「有无新增依赖/新外部输入面」；P0 未清零不开工/不发布。

---

## 环境识别（决定用哪套模型配置，v4.4.0+）

| 环境 | 识别依据 | 配置真源 | 备注 |
|---|---|---|---|
| **办公环境** | `USERDOMAIN=CORP`、存在公司 HTTP 代理（`HTTP_PROXY=http://109.2.0.41:9090`）、`COMPUTERNAME=XIANZHE-ZHAO01` | `~/.dsh/profiles/desktop/cordis.patch.yml` | 2026-11-17 实测 |
| **家用环境** | 无 CORP 域、无公司代理（实测：`USERDOMAIN=SENCER`、`COMPUTERNAME=SENCER`、无代理） | `~/.dsh/profiles/desktop/cordis.patch.yml`（2026-11-17 实测：`C:\Users\ASUS\.dsh\profiles\desktop\cordis.patch.yml`） | 已配置子集 2026-11-17 在本机实测（会话 `dsh-b6f0b86e-6954`），详见家用节 |

> **识别顺序**：先看 `USERDOMAIN` 与代理环境变量；两者都不匹配 → 记「未知环境」，**只允许用会话默认模型**，并提示用户补充该环境配置，不得套用其他环境的配置。
> **会话策略固化（重要）**：DSH 的子代理白名单 `allowedModels` 在**会话创建时**写入会话事件流（`subagent/model-selection-policy`）并持久固化，改宿主配置只对**新开会话**生效。
> 报错口径：`has no configured model` = 模型池里没有该 ID（改 ID）；`not allowed for this Session` 表示会话白名单未放行（**新开会话**，不要反复改配置）。
> 模型列表查询工具：`list_subagent_models`（传 provider + model 验证单条路由）。旧版文档所称 `~/.dsh/settings.yaml` 在新版 DSH 可能不存在。

---

## 模型能力清单 · 办公环境（provider: `aipro`，实测 2026-11-17）

> 来源：`~/.dsh/profiles/desktop/cordis.patch.yml` 实读 + `list_subagent_models` 探针。
> provider `aipro` 为本地网关（`baseURL: http://127.0.0.1:15721/v1`），当前模型池仅 3 个模型。
> 成本列沿用 Token Plan 目录口径，仅作相对贵贱排序参考；`aipro` 网关的**实际计费口径未核实**（未核实即标注，不臆断）。

| 模型 ID | 上下文大小 | 图像输入 | 成本档位/折扣 | 备注（来自宿主配置） | 可派发（实测） |
|---|---|---|---|---|---|
| `DeepSeek-V4.1-Flash-1017` | 1048576 | ✅ `[text, image]` | 轻快档 1/4，夜间 5 折（Token Plan 口径） | 宿主默认模型（`agent-default-model`）；思考档 low/high/xhigh/max；1M 上下文，适合主脑与长上下文角色 | ✅ 已放行（2026-11-17 实测，会话 `dsh-1812d807-63a2`） |
| `GLM-5.2-NVFP4` | 524288 | ❌ `[text]` | GLM 档 8/28（Token Plan 口径） | **纯文本**，不可承担读图角色（测试员截图认证）；思考档 off/low/medium/high/xhigh，可关思考 | ✅ 已放行（2026-11-17 实测，会话 `dsh-1812d807-63a2`） |
| `QWEN3.8-27B-FP8-256K` | 262144 | ✅ `[text, image]` | 待核（宿主未标注） | 256K 上下文；思考档 low/medium；轻快，适合前端/说明员等中等任务 | ✅ 已放行（2026-11-17 实测，会话 `dsh-1812d807-63a2`） |

> 「可派发」列口径：必须由 `list_subagent_models` **实测放行**才可写 ✅，并注明验证会话与日期。未实测一律写 ⚠️ 或「未验证」。
> **2026-11-17 缺陷记录（已闭环）**：`allowedModels` 原配置为 `glm-5.2` / `qwen3.8-27b`（错误别名，模型池真实 ID 为 `GLM-5.2-NVFP4` / `QWEN3.8-27B-FP8-256K`），导致 GLM/Qwen 子代理全部派发失败。用户于当日改为三个真实 ID 后，**新会话 `dsh-1812d807-63a2` 实测三条路由全部放行**，验证了「改配置只对新会话生效」这一会话策略固化机制。
>
> **实测记录（C8 证据，2026-11-17 11:07，会话 `dsh-1812d807-63a2`）**：
>
> | 路由 | 返回模型 | 思考档 | 结果 |
> |---|---|---|---|
> | `aipro/GLM-5.2-NVFP4` | GLM-5.2-512K | off/low/medium/high/xhigh | ✅ 放行 |
> | `aipro/QWEN3.8-27B-FP8-256K` | QWEN3.8-27B-256K | low/medium | ✅ 放行 |
> | `aipro/DeepSeek-V4.1-Flash-1017` | DeepSeek-V4.1-Flash-1017-1M | low/high/xhigh/max | ✅ 放行 |
>
> 三次 `list_subagent_models(provider=aipro, model=<ID>)` 均返回模型信息，未出现 `has no configured model` / `not allowed for this Session`。

### 默认路由 · 办公环境

> 宿主 `agent-default-model` = `DeepSeek-V4.1-Flash-1017`（1M 图文）。v4.5.0+ 派发默认宿主路由优先，**不维护角色分配表**；测试员图像硬能力由默认模型满足（✅ 图文），一般无需动态挑选；硬能力不满足或用户显式要求时查本会话放行集合动态选（见 skill team-mode「派发时模型决策」；`GLM-5.2-NVFP4` 纯文本，不得用于读图角色）。
> 三条路由已于 **2026-11-17 在会话 `dsh-1812d807-63a2` 实测放行**；换环境或改过 `allowedModels` 后仍受「会话策略固化」约束：**须新开会话重测**，未重测前按「不可派发」处理。

---

## 模型能力清单 · 家用环境（provider: `bailian-tpp` / Token Plan；目录记录于 2026-11-16，已配置子集 2026-11-17 本机实测）

> 来源：Token Plan 可用文本模型目录 15 个（经 /models 端点 + 探针实测：64×64/128×128 PNG 图像输入、思考档位、function calling、多轮回传 + 官方文档核实）；DSH 宿主 `cordis.patch.yml` 当前配置其中 7 个。
> ✅ **已配置子集本机实测（2026-11-17，家用机 SENCER，会话 `dsh-b6f0b86e-6954`）**：7 个已配置 ID 经 `list_subagent_models` 全部确认为真实 ID（5 条放行 + 2 条会话固化受限，见下方实测记录）；⬜ 8 个未配置模型仍未验证、视为疑似别名，不得用于派发。
> ⚠️ **会话策略固化**：`qwen4-max-preview` / `qwen3.6-flash` 当前配置白名单已含，但本会话创建早于配置变更，报 `not allowed for this Session`——**非配置错误，新开会话应放行**，不反复改配置。

| 模型 ID | 上下文大小 | 图像输入 | 单次请求图片上限 | 成本档位/折扣（可选） | 备注（擅长定位，联网核实） | DSH 已配置 |
|---|---|---|---|---|---|---|
| auto | 262144 | ✅ | 未知 | 随命中模型浮动 | 平台智能路由，按请求匹配底层模型兼顾效果与成本；思考不可关 | ✅ |
| qwen4-max | 1000000 | ✅ | 未知 | 旗舰档（≥Max），无折扣 | 新一代旗舰多模态：文本/图片/视频理解+深度思考，编程/办公/前端/复杂 Agent；思考与输出共享 393216 预算 | ⬜ |
| qwen4-max-preview | 1000000 | ✅ | 未知 | **预览期 2 折，夜间再 4 折=0.8 折**（2026-11-11~11-25） | qwen4-max 预览版，能力同上；**2026-11-25 24:00 到期下线**，回退 qwen4-max / qwen3.8-max | ✅ |
| qwen3.8-max | 1000000 | ✅ | 未知 | 旗舰档 12/36，夜间 4 折 | 2.4T MoE 旗舰，端到端代码/网页/建模，强推理+多工具调度 | ✅ |
| qwen3.8-flash | 1000000 | ✅ | 未知 | 轻快档 0.8/2.7，夜间 4 折 | 高并发低延迟多模态，流水线批量理解+结构化输出 | ✅ |
| qwen3.7-max | 1000000 | ❌ | 未知 | 旗舰档 12/36，无折扣 | 生产级全栈文本 Agent，函数调用/结构化输出/上下文缓存/批量推理 | ⬜ |
| qwen3.7-plus | 1000000 | ✅ | 未知 | Plus 中档（未列目录价），无折扣 | 多模态 Agent 核心引擎，GUI 操作/OCR/文档理解/代码生成 | ✅ |
| qwen3.6-flash | 1000000 | ✅ | 未知 | Flash 低价档（未列目录价），无折扣 | 高性价比多模态，长上下文代码执行/数学推理/视频图像空间理解 | ✅ |
| deepseek-v4.1-flash | 1000000 | ✅ | 未知 | 轻快档 1/4，夜间 5 折 | 图文输入轻量旗舰，视觉 Agent 毫秒级响应 | ⬜ |
| deepseek-v4.1-flash-1017 | 1000000 | ✅ | 未知 | 轻快档 1/4，夜间 5 折 | v4.1-flash 快照版，能力同上 | ⬜ |
| deepseek-v4-pro-0813 | 1000000 | ❌ | 未知 | Pro 档 4.5/13.5（低阶梯），夜间 5 折 | 1.6T/49B 最强纯文本推理，科研/法律/金融长文档 | ⬜ |
| deepseek-v4-pro | 1000000 | ❌ | 未知 | Pro 别名 12/24（wiki 口径），未列夜间折扣 | v4-pro 稳定快照别名，能力同 0813 无版本漂移；pro 任务优先用 0813（更便宜+夜间 5 折） | ⬜ |
| deepseek-v4-flash-0731 | 1000000 | ❌ | 未知 | 轻量档 1.5/4.5，夜间 5 折 | 284B/13B 低成本高并发，RAG/客服/批量 | ⬜ |
| glm-5.3 | 1000000 | ❌ | 未知 | GLM 档 8/28，无折扣 | 漏洞挖掘/端到端工程交付，强制思考 low/high/max 三档（关思考会 400） | ✅ |
| glm-5.2 | 1000000 | ❌ | 未知 | GLM 档 8/28，无折扣 | 企业级 Agent 默认长程任务，可关思考 high/max；与 5.3 同价但 5.3 更强 | ⬜ |

> **实测记录（2026-11-17，会话 `dsh-b6f0b86e-6954`，家用机 SENCER；C8 证据）**：
>
> | 路由 | 结果 |
> |---|---|
> | `bailian-tpp/qwen3.8-max` | ✅ 放行 |
> | `bailian-tpp/qwen3.8-flash` | ✅ 放行 |
> | `bailian-tpp/qwen3.7-plus` | ✅ 放行 |
> | `bailian-tpp/glm-5.3` | ✅ 放行 |
> | `bailian-tpp/auto` | ✅ 放行 |
> | `bailian-tpp/qwen4-max-preview` | ⚠️ 会话固化受限（当前白名单已含，新会话应放行） |
> | `bailian-tpp/qwen3.6-flash` | ⚠️ 会话固化受限（同上） |
> | `deepseek-account/deepseek-v4-pro` | ✅ 放行（DeepSeek Account provider，不在 Token Plan 目录内） |
> | `deepseek-account/deepseek-flash` | ✅ 放行（返回模型为 DeepSeek-V4.1-Flash） |
>
> 5 条 `list_subagent_models(provider=bailian-tpp, model=<ID>)` 返回模型信息；2 条受限报 `not allowed for this Session`（会话级，非模型池缺失）。deepseek-account 两条为本次实测补记（此前 runbook 未记录，命中复核触发）。

> 成本档位数字为**按量计费目录价（元/百万 token，输入/输出）**，仅作相对贵贱排序代理；Token Plan 实际按 **Credits 动态计费**（无固定 token 换算，由模型档位/token 量/思考模式/工具调用决定），真实消耗以控制台订阅页用量详情为准。
> 另有 `decision-model-preview`（限时免费，0 Credits）为**决策模型**（分类/打分，非通用聊天），不在本 15 模型能力清单内；高频分诊可单独接入。

### 默认路由 · 家用环境

> 宿主 `agent-default-model` = `bailian-tpp/qwen4-max-preview`（1M 图文；**2026-11-25 到期下线**，届时宿主配置回退，回退模型见价位折扣节）。v4.5.0+ 派发默认宿主路由优先，**不维护角色分配表**；测试员图像硬能力由默认模型满足（✅ 图文）；硬能力不满足或用户显式要求（如省钱）时查本会话放行集合动态选（见 skill team-mode「派发时模型决策」；性价比参考：轻快任务 qwen3.8-flash 夜间 4 折、审查 glm-5.3、读图 qwen3.8-max）。
> ⚠️ 本会话（`dsh-b6f0b86e-6954`）qwen4-max-preview / qwen3.6-flash 会话固化受限：子代理显式指定这两条路由会被拒，动态挑选应选其他放行模型（如 qwen3.8-max / qwen3.8-flash），或新开会话；默认路由派发以宿主路由为准，若被拒按 skill「派发时模型决策」自动回退。

### 价位与折扣（时效信息，含到期回退）

- **夜间折扣窗口**：每晚 22:00–次日 08:00。
  - 4 折：qwen3.8-max、qwen3.8-flash。
  - 5 折：deepseek-v4-pro-0813、deepseek-v4-flash-0731、deepseek-v4.1-flash、deepseek-v4.1-flash-1017。
- **qwen4-max-preview 预览促销**：2026-11-11 10:00 ~ **2026-11-25 24:00**（UTC+8），Credits 消耗低至标准费率 **2 折**；夜间 22:00–08:00 再享 4 折 = 标准费率 **8%（0.8 折）**。同等 Credits 白天跑 5 倍用量、夜间跑 12.5 倍用量。
  - **到期回退**：预览结束即下线。届时宿主默认路由与动态挑选候选从 qwen4-max-preview 切到 **qwen4-max**（稳定 ID，标准费率）或 **qwen3.8-max**（夜间 4 折更省），并删除/更新本清单 preview 行。运行时派发不得继续使用已下线模型（自动回退）。
- **decision-model-preview**：限时免费（0 Credits），决策接口非聊天。
- 来源：[Token Plan 产品动态](https://www.alibabacloud.com/help/zh/model-studio/token-plan-product-updates)（2026-11-13）、[个人版概述](https://help.aliyun.com/zh/model-studio/token-plan-personal-overview)。折扣以控制台最新为准。

### 场景选型建议

| 场景 | 首选 | 说明 |
|---|---|---|
| 日常主力·复杂编码·Agent 编排（11-25 前） | qwen4-max-preview | 旗舰能力+2 折，夜间 0.8 折最划算；简单任务调低思考档省 Credits |
| 主力（11-25 后） | qwen4-max / qwen3.8-max | qwen3.8-max 夜间 4 折更省；预算紧回 qwen3.8-flash |
| 高并发·批量·简单任务·成本敏感 | qwen3.8-flash | 夜间 4 折全场最低；要读图换 deepseek-v4.1-flash（夜 5 折） |
| 读图·截图分析·OCR·UI 评审 | qwen4-max-preview / qwen3.8-max | qwen3.7-plus、qwen3.6-flash、deepseek-v4.1-flash 也支持图片；纯文本模型勿发图 |
| 深度推理·长文档·科研/法律/金融 | deepseek-v4-pro-0813 | 1M+393K 输出+夜间 5 折；或 qwen4-max-preview |
| 代码审计·漏洞挖掘·工程交付 | glm-5.3 | 强制思考 low/high/max，1M |
| 纯文本结构化输出·工具编排 | qwen3.7-max | 函数调用/结构化输出稳，1M |
| 要关思考提速/省钱 | glm-5.2 / qwen3.8-flash / deepseek-v4.1-flash | enable_thinking 可关；glm-5.3 与 auto 关不了（400） |
| 高频分诊·分类·打分 | decision-model-preview | 限时免费，决策接口非聊天 |
| 懒得选·简单问答 | auto | 平台路由，成本随命中模型浮动，思考不可关 |

> 场景首选含部分当前未配置（⬜）模型（如 deepseek-v4-pro-0813、qwen3.7-max、glm-5.2）：要用先在宿主配置，或改用已配置替代（深度推理→qwen4-max-preview / glm-5.3；结构化输出→qwen3.8-max）。
> 省钱要点：重活压给预览期 qwen4-max-preview（尤其夜间）；可延后任务排夜间（须 DSH 内交互式，个人版条款禁外挂批量脚本）；简单任务调低思考档（思考 token 也扣 Credits，qwen4 起思考与输出共享预算）；用上下文缓存（命中输入大幅降价）；deepseek pro 用 0813 不用无后缀别名；GLM 同价选 5.3。

---

## 部署 / 回退 / 验证（手动/脚本通道）

```powershell
# 安装/更新（真源 junction，改 ship-it/ 即生效）
.\install.ps1            # 已存在跳过；-Force 覆盖
.\update.ps1             # git pull
# 打包 .skill（不入库）
.\build.ps1              # 输出 dist\
# 核销/验收机器校验
python ship-it\scripts\check_spec.py docs\specs\<文件> --stage verify
python ship-it\scripts\check_roles.py --date <YYYY-MM-DD> --stage start
python ship-it\scripts\check_roles.py --date <YYYY-MM-DD> --stage verify
python ship-it\scripts\check_roles.py --date <YYYY-MM-DD> --stage pause --spec docs\specs\<文件>
python ship-it\scripts\check_spec.py docs\specs\<文件> --stage accept --git-check --base <ref>
python ship-it\scripts\check_roles.py --date <YYYY-MM-DD> --stage accept
python ship-it\scripts\check_docs.py --root .
# 大文件写保护
python ship-it\scripts\guard_large_write.py prepare <file> --manifest <manifest.json>
python ship-it\scripts\guard_large_write.py check <file> --manifest <manifest.json>
# 核心回归（现有契约测试；Step 5 回填后加 SHIP_IT_VERIFY=1）
python -m unittest tests.test_reviewer_judge_contract -v
python -m py_compile ship-it\scripts\check_spec.py ship-it\scripts\check_roles.py ship-it\scripts\check_docs.py ship-it\scripts\guard_large_write.py
```

- **验证**：改 skill 正文后，下一轮对话让模型重读 `SKILL.md` 报 version 自证；`Get-Content ~/.agents/skills/ship-it/SKILL.md -TotalCount 5 | Select-String version` 查生效版本。
- **回退**：`git revert <commit>` 或恢复文件；junction 真源模式改回即生效，无需重装。

### 回滚卡

| 项 | 记录 |
|---|---|
| 当前版本 | SKILL.md frontmatter version（见三处真源） |
| 上次可用产物 | 上一个 git commit / Release tag |
| 回滚触发条件 | frontmatter 解析失败 / check_spec.py 异常 / references 引用断裂 / 正文误写模型名 |
| 回滚动作 | `git revert` 推回 main；junction 真源改回即生效 |

## 服务红线

- 禁止凭据（key 值/token）入库；只写环境变量名或「见 ~/.dsh/.credentials.yaml」。
- 禁止在 SKILL.md / team-mode.md / 任何 skill 正文或代码写死具体模型名（模型信息只在本 runbook）。
- 禁止 AI 合并 PR（PR 创建即停，合并按钮属用户）。
- 测试只读、不发付费请求、不写业务数据；一次性脚本置 `tmp/`（已 gitignore），收尾清理。
- 代码安全员/审查员/裁判员只读：不得改代码/spec/任务树；审查员只可直发 `continue`/`retry_same`；裁判员 BLOCK 由主脑整改，PASS 不替代用户验收与 `check_spec.py`。
- 审查员写权限仅 7 类记录（`docs/reviews/<date>-` 下 patrol/pause/auditor/failure-log/referee-start/security-start/auditor-start），其他文件不得写；start 文件由该角色本人写，主脑不得代写。
- 审查报告落 `docs/reviews/` 或 `tmp/`；`tmp/` 报告 Step 9 必删；报告只写证据（`path:line`/命令+退出码），不写凭据值。

## 监督规则源（裁判员用，v4.6.0+）

> 裁判员按优先级读取；不存在则记录「未找到」，不得编造。

1. 用户本轮明确指令 / spec §1「用户约束」与「冲突与裁定」。
2. 项目规则：本仓库根**无** `AGENTS.md` / `CLAUDE.md`；`.agents/` 无规则文件；以本 runbook 的「系统形态与部署通道」「核心功能清单」「服务红线」为准。
3. 全局：`~/.dsh/AGENTS.md`。
4. skill 正文：`ship-it/SKILL.md`、`ship-it/references/team-mode.md`。
5. spec 契约：`docs/specs/<本次>.md`（C 条款 / A 验收 / §7 边界 / §9 核销）。
6. 任务树 / 共享看板快照（子代理无 timeline 工具时由主脑把快照写入 prompt）。
7. agent 目录：本机 `~/.dsh` 下**无** `agents/`；`~/.agents/skills/` 是 skill 目录而非 agent 预设；按宿主实际存在路径读取，不存在记「未找到」。
8. 禁止读取主脑会话日志 / `.jsonl.zstd` / 凭据值；后台不可见时写「后台可见性：降级」。
9. C14 审查员开工闸门：第一个写任务前派发并落盘 patrol log（首轮早于首个实现提交、轮次 ≥3、间隔 ≤5 分钟或事件触发并记 trigger）；审查员只读但可写 7 类记录；`check_roles.py --stage start` 退出码 0 才开工；主脑不得代写或内联替代。
10. C15 角色 start/report 双闸门：三份 start artifact（referee/security/auditor）由本人写，字段 role/reviewer/session/started_at/spec_revision/spec_hash/未参与编码声明/未参与 spec 编写声明；started_at 早于首个实现提交；三类身份互异。
11. C16 契约变更暂停：用户改契约 → spec 置 status: paused；审查员向活跃子代理发暂停/结束令（主脑只下达意图）；pause 记录先于 spec 编辑；`check_roles.py --stage pause --spec` 退出码 0；重新签约后恢复。
12. C17 失败分类与三次尝试：dispatch_failed 1 次后换新子智能体；execution_failed 3 次后换新子智能体；主脑不得自做；仍失败报用户；failure log 记 attempt。
13. C18 全文一致性：`check_docs.py --root .` 退出码 0；旧口径/过期计数/重复/超长/跨文件矛盾清零。
14. 裁判边界：不执行测试、不审代码；测试执行归测试员；代码审查+安全检查归代码安全员；J2 只审流程/文档/自检；J3/J4 在测试+审查/安全通过后根据测试员报告与代码安全员结论审契约。
15. 安全审查库：`references/security-kb.md`；OSV/GHSA/NVD/KEV/EPSS/EOL + SonarQube 可选 + Semgrep/Trivy/gitleaks；记录来源+日期，不凭记忆说最新。
16. 信息流：用户 ↔ 主脑 ↔ 审查员 ↔（代码安全员/裁判员/开发/测试员）；主脑不直接等裁判员；主脑只接收审查员汇总。
17. 角色边界：代码安全员代码审查（正确性/质量/注释/重复功能）+ 安全检查；测试员只做验收测试；前端 design.md（无则先问/用户经验总结），后端+数据库标准；形态 1–3 测试员必执行。
18. 图像/测试环境：审查员图像优先，图片交主脑决定临时识图子智能体；测试员用实际可控 Win/mac 工具，浏览器真实操作+截图，Playwright 提前适配。
19. 契约互审：需求模糊/跳过澄清员时主脑+审查员+裁判员至少 1 轮互审；审查员汇总前对每个子代理报告至少反问 1 个问题；主脑可反向质疑，未解决不呈现。
20. 审查员生命周期：签约到 PR/Step 9 不得结束；inactive 不是结束；主脑必须唤醒；下游无任务才可结束；换新审查员是角色替换，不是结束角色。
21. v4.7.0 契约闸门总览：签约只认严格“签约”、验收只认严格“验收”；`check_spec.py` 四阶段（draft/spec/verify/accept）；`check_roles.py` 五阶段（start/pause/sign/verify/accept）与报告 C5 字段；`check_docs.py` 全文一致性；`guard_large_write.py` 大文件基线校验；入口清单逐条跳转；SKIP 必须退出码 2。

## 复核触发（增量，不为每个需求重复拉取）

- 模型列表变动（新增/移除/改名）→ 对新模型联网核实能力 + 探针 → 更新能力清单写回本文件（运行时派发自动适应，无需人工改分配表）。
- 会话实际路由出现本清单未记录的模型名（配置滞后以实际为准）→ 同上。
- 能力异常（如图像输入突然报错）→ 探针实测复核。
- **价格/折扣变动（促销开始/结束、模型到期下线）→ 增量更新成本列；到期模型注明回退，运行时派发不得使用已下线模型。**
- **宿主默认路由变动（`agent-default-model` / 会话模型切换）→ 更新本文件各环境「默认路由」记录。**
- **切换环境（办公 ↔ 家用）→ 按「环境识别」节重新判定，改用对应环境节，禁止跨环境套用配置。**
- **改过 `allowedModels` 等宿主配置 → 必须新开会话后重测路由**；当前会话受策略固化影响，改配置不会即时生效。
