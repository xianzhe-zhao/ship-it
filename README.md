# ship-it

把"用户提需求 → 改完代码 → 发布上线"固化成可核销的 9 步契约流程的 AI agent skill。spec 是唯一事实来源，代码与测试从契约派生，验收按条款打勾，发布带回滚。每步有产出物和闸门，不跳步——尤其不在用户验收通过前动生产。

支持 DSH / Claude Code / Codex 等 Agent Skills 目录约定的工具。

## 9 步流程

| 步骤 | 做什么 | 闸门 |
|---|---|---|
| 1 需求澄清与提示词优化 | 联网搜索 + 向用户提问 + 主脑优化，输出优化后需求 + 澄清记录（每次做、分轻重） | 需求无歧义、技术可行 |
| 2 方案自审 + 技术蓝图 + spec 契约 | 复用/扩展/新建三选一 + 影响面 + 入口清单 + 技术蓝图 + 落盘 spec | 三问全过；用户消息**严格等于“签约”**；`check_spec --stage spec` 退出码 0 |
| 3 编码 + 自检 | 语法/测试/门禁 + UI 坐标断言 + 一致性复查六项 + 大文件写保护 | 监察员已派发且 `check_roles --stage start` 退出码 0；构建通过；>50KB 写入 guard 通过 |
| 4 测试两支柱 + 部署测试系统 | 支柱 1 核心没修坏（分级回归）+ 支柱 2 新功能达标（每条条款一个用例）+ 入口逐条跳转 | 核心没修坏；每条 C 条款有用例；SKIP 退出码 2 |
| 5 契约核销表 | 5 列核销 + 测试报告 + `check_spec.py` / `check_roles.py` / `check_docs.py` 机器校验 | 三个退出码均 0 |
| 6 用户验收 | 用户按验收清单逐条打勾 | 用户消息**严格等于“验收”**；`check_spec --stage accept` 退出码 0 |
| 7 版本号 + PR | SemVer 递增 + PR 四块说明（版本/契约/测试/影响面+回滚） | `check_roles --stage accept` 退出码 0；PR 创建即停 |
| 8 合并后发布正式系统 | 回滚预案 + 端到端验证（合并前不碰生产） | 生产健康 200 + 产物可达 |
| 9 清理 + 记录 | 删垃圾/测试残留 + 写 CHANGELOG | 无残留 |

## 核心机制

- **严格签约/验收（v4.7.0+）**：签约只认用户消息 `strip()` 后**严格等于“签约”**两个字；验收只认**严格等于“验收”**两个字；继续/同意/可以/没问题/发吧都不算。`sign_hash` 绑定 spec 正文，spec 改动即失效回 draft 重签；`accept_commit` 绑定验收时 HEAD，之后改代码即撤销验收。
- **spec-first**：需求变更先改 spec 再改代码，禁止绕过 spec 打补丁；PR 附 spec 路径可逐条审计；spec 首次提交必须 docs-only，实现提交不得更早。
- **契约条款 C1..Cn**：每条可验证、一条一句、不写实现、失败行为必写；受保护规则 🔒 标记防"同源共错"；流程规则用 P1..Pn，不占 C 编号。
- **两支柱测试**：测试从契约派生不从代码派生（代码改了测试跟着改 = 测试失效）；测试报告落 `docs/reviews/<date>-test-report.md`。
- **监察员开工与独立报告（v4.7.0+）**：`check_roles.py` 按 start/pause/sign/verify/accept 校验；开工前落盘 patrol log 与三份 start artifact（referee/security/auditor），报告固定节含角色/审查者/会话标识/未参与编码声明/未参与 spec 编写声明/结论/证据/`spec_revision`/`spec_hash`/`汇总来源`；三类角色身份两两不同；监察员只读但可写 7 类审查记录，是唯一汇总接口；单会话至少 1 名只读 subagent，不得自检替代。
- **暂停闸门（v4.7.0+）**：改契约先置 `status: paused`，pause 记录早于 spec 编辑，监察员发暂停令，重新签约才恢复。
- **失败分类（v4.7.0+）**：未启动（派发失败）1 次换新子智能体；已启动无产出（执行失败）3 次换新；主脑不得自做；仍失败报用户。
- **文档体检（v4.7.0+）**：`check_docs.py` 退出码 0；旧口径/过期计数/重复/超长/矛盾清零。
- **文本质量与闸门（v4.7.1+）**：`check_text.py` 校验 ship-it/复盘/上传 skill 行数与禁词；C6 首写标记、C7 暂停前 spec 快照、C8 按 `hash_scope` 校验历史 hash、C10 `pre_commit_check.py` + CI 留证。
- **核销真实性**：5 列（条款/用例名/用例文件/结果/路径真实性）+ `- 测试报告：` footer；用例名必须在用例文件与报告里出现；虚构用例名/文件不存在/缺 PASS 即 FAIL。
- **大文件写保护**：>50KB 文本整体重写先 `guard_large_write.py prepare`，写后 `check`，失败 `restore`；按写前基线校验，不写死项目行数。
- **入口清单**：Step 2 从实际架构扫描产出，Step 4/6 逐条跳转验收；不硬编码固定入口；无 UI 变更写“入口清单：无 UI 变更”。
- **文本简洁**：结论前置、一条一句、硬禁用词见 `references/rule-style.md`；每条规则有判定方式。
- **mini-spec 快速通道**：单文件、不改接口、不动表/权限/外部输入的小改动用 4 行 mini-spec，避免流程税；资格不可自判。
- **周期安全审查**：默认每月一次（高危每周），不按次执行；每次变更只做增量检查；P0 未清零不开工/不发布。
- **禁止自证**：agent 不可自判合规，关键节点（mini-spec 资格 / 纯文档免流程资格 / 核销✅ / 能力声明）必须机器可查或用户确认——执行者 ≠ 裁定者。

## 团队模式（大变更启用）

多文件 / 全栈 / 用户点名时，主脑拆角色派子代理执行同样的 9 步：

- **主脑**：spec 唯一 owner、唯一对用户交付、唯一子代理派发者；只派活/决策/回复用户，不亲自开发/测试/审代码。
- **角色**：需求分析师 / 后端开发（后端+数据库标准）/ 前端开发（`design.md`，无则先问）/ 代码安全员（代码审查+安全检查，团队模式必执行）/ 监察员（异常与偷懒审查）（主脑唯一汇总接口）/ 裁判员（测试+审查/安全通过后审契约，**不执行测试、不审代码**）/ 测试员（只做验收测试）；**改动说明员已删除**，Step 6 五项报告由主脑汇总团队产出后起草。
- **监督角色**：监察员是唯一汇总接口，间隔 1 分钟巡视所有成员；发现 inactive 未完成/主脑 idle 有剩余任务/running 无进展即催办或上报；可直发 `continue`/`retry_same`；换模型、换范围、新派发交主脑；主脑不轮询，5 分钟无消息主动唤醒；宿主无定时则事件触发并声明降级。
- **独立审查（v4.7.0+）**：至少 1 名只读 subagent 独立出报告；不得自检替代；派不出声明「无独立审查」且不得自判 PASS。
- **角色按需启用矩阵**：形态 0 单干 / 1 小改 / 2 中改 / 3 大改高风险；代码安全员/监察员/裁判员/测试员团队模式必须执行（主脑单干例外且自测）；前后端只派相关侧；深度安全审计/方案评审/发布验证为可选专项。
- **执行中需求变更**：先置 `status: paused` + pause 记录（早于 spec 编辑）+ 监察员发暂停令 → 改 spec → 用户重新签约 → 受影响闸门重跑；暂停期间不跑旧契约。
- **目标驱动编排**（可选）：签约时问用户是否启用「目标 + 任务树」；启用则建目标、按 Step 1–9 分组建树（叶子可检查、节点 ≤40）、派发带任务标识、Step 5 核销加「目标树」行、验收后关目标。
- 详情见 `ship-it/references/team-mode.md`。

## 文件结构

```
ship-it/
├── SKILL.md                      # 铁律 + 9 步流程 + 关键原则 + 常见坑 + 反偷懒/反越权红线
├── scripts/
│   ├── check_spec.py             # spec 机器校验（--stage draft|spec|verify|accept）
│   ├── check_roles.py            # 审查报告/开工/暂停闸门（--stage start|pause|sign|verify|accept）
│   ├── check_docs.py             # 全文一致性与去废话（--root .）
│   ├── check_text.py             # 文本质量（行数/禁词/重复/矛盾/互引）
│   ├── spec_hash.py              # hash_scope（full_body/sections_1_8/a_normalized）
│   ├── pre_commit_check.py       # C10 pre-commit 闸门（check/install-hooks）
│   ├── install-hooks.py          # 安装 pre-commit hook
│   └── guard_large_write.py      # >50KB 文本写保护（prepare|check|restore）
└── references/
    ├── rule-style.md             # 文本铁律 + 硬禁用词（C11 判定源）
    ├── spec-template.md          # spec 模板（front matter 签约/验收块 + 入口清单 + P 规则 + 5 列核销）
    ├── team-mode.md              # 团队模式角色卡 + 最小可行独立审查 + 报告阶段表 + 裁判单 C5 + 派发协议 + 目标驱动编排
    ├── security-review.md        # 周期安全审查 playbook
    ├── security-kb.md            # 代码安全员安全审查库：数据源 + 工具矩阵 + 报告模板
    ├── self-check.md             # 编码自检：坐标断言 + 六项复查
    └── project-adaptation.md     # 首次接入项目：两层落地 + 核心功能清单
```

## 安装

### 方式一：git clone（推荐，可一键更新）

```sh
# 1) 克隆（Windows / macOS / Linux 相同）
git clone https://github.com/xianzhe-zhao/ship-it.git
cd ship-it

# 2) 安装（按系统二选一）
.\install.ps1            # Windows PowerShell；已存在时跳过，-Force 覆盖
./install.sh             # macOS / Linux；已存在时跳过，--force 覆盖
```

`install` 脚本给 `ship-it/` 在 `~/.agents/skills/` 建 **junction / symlink**——真源留在仓库，改完即生效，不会产生第二份副本。

> 已存在的**真实目录**不会被删（脚本报错让你先移走），避免误删用户数据。
> DSH / Codex 会实时重扫 `~/.agents/skills`，**无需重启**。
> Claude Code 不读 `~/.agents/skills`，需再建一个链接（见下节）。

### 方式二：下载 .skill 文件（不想碰 git）

从 [Releases](https://github.com/xianzhe-zhao/ship-it/releases) 下载 `ship-it.skill`，解压到 `~/.agents/skills/ship-it/` 即可。这种方式**无法一键更新**，每次升级需重新下载。

## 更新

### git clone 安装的（推荐）

```powershell
# Windows
.\update.ps1
```
```sh
# macOS / Linux
./update.sh
```

脚本执行 `git pull`，拉取最新版本。DSH / Codex 会自动重扫 `~/.agents/skills`，无需重启。

### 手动

```sh
git pull
```

## 跨工具适配

| 工具 | 全局目录 | 项目级目录 | 是否原生读 `~/.agents/skills` |
| --- | --- | --- | --- |
| **DSH** | `~/.agents/skills/<name>/`（推荐）<br>`~/.dsh/skills/<name>/`（DSH 专属，可选） | `<project>/.agents/skills/<name>/`（推荐）<br>`<project>/.dsh/skills/<name>/` | ✅ 原生 |
| **Codex** | `~/.agents/skills/<name>/`（推荐）<br>`~/.codex/skills/<name>/` | `<project>/.agents/skills/<name>/` | ✅ 原生 |
| **Claude Code** | `~/.claude/skills/<name>/` | `<project>/.claude/skills/<name>/` | ❌ 只读自己的目录 |

### 跨工具共享（装一次，所有工具可用）

**结论：`~/.agents/skills/` 是唯一真源，但 Claude Code 必须额外给一个链接** —— 不是所有 agent 都能统一到一个目录。

```sh
# 真源
~/.agents/skills/ship-it/          # 目录本体（或指向你仓库的 symlink）

# 只有 Claude Code 需要这一步
ln -s ~/.agents/skills/ship-it ~/.claude/skills/ship-it
```

```powershell
# Windows：junction（无需管理员权限）
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\ship-it" `
  -Target "$env:USERPROFILE\.agents\skills\ship-it"
```

**实测依据（2026-10-30，本机版本：DSH 桌面端 / codex-cli 0.161.0 / claude-code 2.1.293）**：

| 工具 | 结论 | 证据 |
| --- | --- | --- |
| DSH | ✅ 原生扫描 `~/.agents/skills`、`<repo>/.agents/skills` | 源码 `packages/skill/skill-filesystem/src/index.ts`：`roots()` 里 `join(agentsHome,'skills')`（rank 500，`agentsHome = $DSH_AGENTS_HOME ?? ~/.agents`）与 `join(projectRoot,'.agents/skills')`（rank 200，项目根 = 向上找 `.git`）；新建探针目录后 DSH 技能列表即时出现 |
| Codex | ✅ 原生扫描 `~/.agents/skills` | 源码 `codex-rs/exec-server/src/discoverV2/capability_locations.rs`：`skill_roots = [codex_home/skills, user_home/.agents/skills, system_skills_root]`，常量 `AGENTS_SKILLS_SUFFIX = ".agents/skills"` |
| Claude Code | ❌ 不扫描，只做「迁移导入」 | `claude.exe` 中的实现：遍历 `[~/.cursor/skills, ~/.agents/skills]` 后写入 `skillsOut`（即 `~/.claude/skills`），项目级写死 `sourceLabel: ".agents/skills"`；且 `.agents` 若为符号链接会**直接跳过**（"Is (or is under) a symlink — skipping project-scope read for safety"） |

- DSH / Codex：**无需任何链接**，把 skill 放进 `~/.agents/skills/` 即可（DSH 还支持项目级 `./.agents/skills/`，随仓库分发）
- Claude Code：必须放/链接到 `~/.claude/skills/`（项目级同理 `./.claude/skills/`）。**不要指望它的自动导入** —— 那是拷贝到 `.claude/skills` 的一次性迁移，且会跳过 symlink
- 因此最省心的统一布局是 **1 个真源 + 1 个 Claude 链接**，不需要再给 `.dsh` / `.codex` 建目录

## 在项目里使用 ship-it

**默认两层，不要给项目再造一份流程 skill**（完整理由与检查清单见 `ship-it/references/project-adaptation.md`）：

1. 装好全局 skill 后，直接提需求即自动启用；
2. 项目 `CLAUDE.md` / `AGENTS.md` 写约定与红线：声明"执行 ship-it Step 1–9"、PR 必带内容、版本号来源、禁止事项；
3. 新建 `docs/deploy-runbook.md` 存项目具体值：环境与端口、部署脚本与手动回退、部署后验证、只读回归、回滚卡、服务红线；
4. 把 `ship-it/references/spec-template.md` 复制到 `docs/specs/_TEMPLATE.md`，标注来源，模板级改动回灌；
5. 契约核销阶段跑 `python scripts/check_spec.py docs/specs/<文件> --stage verify`（非零退出 = 核销不合格）。

## 改了 skill 之后，怎么让 agent 立刻用上

**结论：不需要"通知"，DSH 会实时重扫；但要让模型重读正文，得等下一轮对话。**

| 情形 | 你要做什么 | 生效时机 |
|---|---|---|
| 只改 `SKILL.md` 正文（条款、命令、阈值） | 存盘即可 | **下一轮对话里调用该 skill 时**读到新内容（DSH 每次 `get` 都重新解析文件，不缓存正文）；同一轮里已加载的旧内容不会自动替换 |
| 改了 `description` 或触发词 | 存盘即可 | 立即：技能目录（模型每轮看到的清单）会刷新，触发行为随之变化 |
| 新增/删除 skill 目录 | 存盘即可 | 立即：目录增删会触发 watcher，新 skill 出现在清单里 |
| 重命名目录 或 改 `name:` | 还要重建链接 | 目录名变了，`~/.agents/skills` / `~/.claude/skills` 里的 junction 会指向空 |
| 推到 GitHub，在另一台机器用 | `git pull` + 该机器上已有 junction | 拉取后存盘即生效，不用重新装 |

**怎么确认 agent 真的用上新版**（一句话问它，或自己查）：

```powershell
# 看当前生效的版本号（frontmatter 里的 version）
Get-Content "$env:USERPROFILE\.agents\skills\ship-it\SKILL.md" -TotalCount 5 | Select-String 'version'
```

> 给 agent 的提示语（改完新版本后想立刻生效）：
> 「skill 已更新到 vX.Y.Z，重新读一遍 `.agents/skills/ship-it/SKILL.md`，报一下你看到的 version 和 Step 1 的要点，然后按新版继续。」
> 这样它会重新加载正文并自证版本，而不是沿用上下文里缓存的旧规则。

## 构建 .skill 打包文件

`.skill` 文件是构建产物，不入库。从源码构建：

```powershell
.\build.ps1        # Windows，输出到 dist\
```
```sh
./build.sh         # macOS / Linux，输出到 dist/
```

`.skill` 是 zip 格式，解压即得 skill 目录，可直接发给同事安装。

## 更新记录

见 [`CHANGELOG.md`](CHANGELOG.md) 与 [`ship-it/CHANGELOG.md`](ship-it/CHANGELOG.md)。

## 作者与商用说明

你好，我是 **xianzhe.zhao**。我在互联网公司做了 **8 年 IT 技术岗**，后来转做 **AI 产品架构师**。ship-it 是我把日常开发发布流程反复打磨后沉淀下来的框架，希望它能帮你少踩坑、把交付做得更稳。

- **MIT 协议，免费使用**：可自由使用、修改、分发与商用。
- **商用请注明出处**：如果它在你的产品/服务/团队里发挥了作用，方便的话请注明「ship-it / xianzhe.zhao」，并邮件告诉我一声：**971554652@qq.com**。这只是一个友好的请求，不是 MIT 之外的额外许可限制。
- 如果你愿意分享使用场景或改进意见，我也很欢迎。

## 许可证

MIT（© xianzhe.zhao），见 [LICENSE](LICENSE)。

