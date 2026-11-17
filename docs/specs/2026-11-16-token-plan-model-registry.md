# 2026-11-16 Token Plan 模型注册表与成本感知分配 — spec 契约

> **本文件是需求的唯一事实来源（single source of truth）。**
> 用法：复制为 `docs/specs/<YYYY-MM-DD>-<英文短名>.md`，在 Step 2 填写完毕、**用户确认 = 签约** 后才进入编码。
> 编码、测试、验收、PR 全部从本文件派生；需求变更先改本文件，再改代码（spec-first）。
> 相关：skill `ship-it` 的 Step 2。

---

## 1. 背景与目标（what & why）

ship-it 团队模式按「角色能力要求表」给角色智能体分配模型，模型信息一律来自项目 runbook 的「模型能力清单」+「角色分配」表（skill 正文不写死模型名）。本仓库目前**没有 `docs/deploy-runbook.md`**，团队模式首次组队需从零拉取/核实/探针。同时，现有分配流程只考虑**能力**（图像输入、大上下文、定位），**不考虑成本**——在 Token Plan 订阅（Credits 动态计费 + 限时折扣）下，可能把最贵旗舰分给所有角色，浪费额度。

本次把已实测核实的 DSH 宿主 Token Plan（bailian-tpp）模型分析落地为本仓库 runbook，并给 skill 流程补一条**通用成本/折扣感知分配原则**（不写死任何模型名），让"能力满足前提下按性价比分配"成为永久流程规则。改完：本仓库组队直接读 runbook 分配；任何项目用 ship-it 组队都会按性价比排序候选模型。

需求来源：用户原话「把这次分析的模型推荐内容给到 D:\Project\Ship-it 这个项目中建议分配角色智能体的时候使用……严格按照这个流程更新代码」。模型分析来自本会话前几轮对 bailian-tpp 的实测探针 + 官方文档核实。

### 需求澄清记录（Step 1 产出，签约时展示给用户确认）

- **原始需求**：把 Token Plan 模型推荐分析给到 Ship-it 项目，用于分配角色智能体；先拉最新 Git（已最新，0 behind）；先分析再严格按 ship-it 流程更新代码。
- **优化后需求**：在 ship-it 源码仓库 (1) 新建项目 runbook，记录 bailian-tpp 15 个文本模型的能力清单（上下文/图像输入/图片上限/定位）、成本感知的角色分配表、价位与折扣信息（含 qwen4-max-preview 2026-11-25 到期回退）；(2) 给 team-mode.md 模型发现/分配流程增加通用「成本/折扣感知」原则与价格变动复核触发，注册表模板增加可选成本列；(3) 同步 SKILL.md/README 团队模式表述为「能力+性价比驱动」；(4) 版本 4.2.0→4.3.0，两处 CHANGELOG 同步；(5) 建立安全审查日志。全程 skill 正文零模型名。（注：「角色分配表」机制已于 v4.5.0 被运行时自适应派发取代——runbook 不再维护角色→模型分配表，派发默认宿主路由优先、仅硬能力不满足或用户显式要求时动态挑选，详见 `2026-11-17-runtime-model-dispatch.md`。历史条款不改写。）
- **优化说明**：明确改动对象=本仓库、规范基准=ship-it runbook 约定、模型数据来源=DSH 宿主 bailian-tpp（已实测）；把"给建议"具体化为 runbook 数据 + 流程规则两层；识别出角色分配表约束 agent 行为→不可免流程，走完整 spec。
- **用户问答**：
  - 问「改动范围 A 只建 runbook / B runbook+升级 skill 流程」→ 用户选 **B**（升级 team-mode.md 通用成本原则，版本升 4.3.0）。
  - 问「时效促销价怎么放」→ 用户选 **完整放入+标注到期回退**（能力清单/角色分配为 durable 配置，促销折扣标日期与回退）。
  - 首轮用户表示未理解 A/B 区别→主脑用具体例子二次解释后用户选 B。
  - **签约后外部变化（Step 4 遇阻即停）**：DSH 宿主 cordis.patch.yml 于 2026-11-16 19:11 被精简为 7 个模型（签约时 15），C7「清单=宿主配置15」FAIL，且审查员拟分配 deepseek-v4-pro-0813 不在宿主 7 个内。问用户调和方案→选 **A**：runbook 保留完整 15 模型目录并标注哪 7 个 DSH 已配置/哪 8 个可用未配置；角色分配只用已配置 7 个（审查员改 glm-5.3）；C7 改为「宿主已配置 ⊆ 清单 + 来源标注准确」。据此修订 C1/C2/C7。

## 2. 方案自审（怎么做）

- **复用盘点**（实际查过）：
  - `ship-it/references/team-mode.md`：已有「角色能力要求表」「模型发现流程（5 步）」「注册表模板」「复核触发」「失败降级」——成本感知原则**扩展**这些既有节，不新建机制。
  - `ship-it/references/project-adaptation.md`：已定义 runbook 应含「环境值/部署/回退/验证/回滚卡/核心功能清单/安全审查周期」——新 runbook 复用此结构。
  - `ship-it/references/spec-template.md`：本 spec 复用其 9 节结构。
  - `ship-it/scripts/check_spec.py`：stdlib-only，本次**不改**，用作核销机器校验。
  - `CHANGELOG.md`（仓库分发记录）+ `ship-it/CHANGELOG.md`（skill 版本）+ `SKILL.md` frontmatter `version: 4.2.0`：版本三处来源已定位。
  - 仓库**无** docs/deploy-runbook.md、无 _TEMPLATE.md、无根 CLAUDE.md/AGENTS.md、无 security-review-log.md、无 .github/workflows、无 package.json/requirements.txt（零第三方运行时依赖）。
- **决策**：**B 扩展**（team-mode/SKILL/README 既有节加成本维度，向后兼容）+ **C 新建**（runbook/security-log/spec 三个新文件）。
  - 新建 runbook 的复用成本 vs 新建成本：复用=把模型数据塞进 team-mode.md 正文→**违反 skill「正文不写死模型名」硬规则**，且污染可分发 skill；新建=runbook 是 skill 指定的模型数据唯一落点，零规则冲突。故新建 runbook 成本远低于复用。
  - 新建 security-log：skill 周期审查强制要求记入 docs/security-review-log.md，仓库尚无→必须新建。
- **执行形态判断**：**主脑单干**。理由：(a) 改动是文档+流程规则，非可并行的前后端代码模块；(b) 模型分析数据全在主脑上下文，派发需大量上下文转移；(c) never-ask 权限模式下子代理写操作可能被自动拒绝（反越权红线 #6），派写任务必白跑；(d) 文件作用域高度耦合（runbook/team-mode/SKILL/CHANGELOG 互相引用），并行易踩。用户可否决。
- **影响面**：
  - 新增文件：`docs/deploy-runbook.md`、`docs/security-review-log.md`、`docs/specs/2026-11-16-token-plan-model-registry.md`（本文件）。
  - 修改文件：`ship-it/references/team-mode.md`（成本原则+复核触发+模板可选列）、`ship-it/SKILL.md`（frontmatter version + 团队模式 bullet）、`ship-it/CHANGELOG.md`（4.3.0 节）、`CHANGELOG.md`（版本索引行）、`README.md`（团队模式 bullet）。
  - 调用方：team-mode.md 被 SKILL.md 引用；runbook 被模型发现流程读取；**无代码调用方**（check_spec.py 不改）。
  - 接口/表/缓存/端口：无变更。
- **兼容性**：team-mode 改动为**追加原则**，不删改既有流程；注册表模板新增列为**可选**，旧 runbook 无该列仍兼容；版本 minor 递增，无破坏性变更。
- **成本预算**：无（本次纯文档编辑+本地 stdlib 校验，不调用 LLM/付费 API；模型探针已在前几轮分析完成，本轮不新增付费调用）。
- **安全增量**：自上次审查无新增依赖、无新外部输入面（纯 Markdown + 既有 stdlib 脚本）。仓库零第三方运行时依赖，npm audit/OSV 不适用；check_spec.py 仅读 spec 无 eval/exec/网络；install/build 脚本仅 junction+git pull+zip，无凭据处理。仓库从未建审查日志→本次建立并记录该结论。新增文件不含凭据（模型 ID/公开价位/环境变量名，无 key 值）。
- **测试策略**：
  - 契约派生用例（Python stdlib，置 `tmp/`，Step 9 清理）：解析 runbook markdown 表校验 C1/C2/C7；grep 校验 C3（凭据/到期标注）/C4/C5（模型名零出现+成本关键词）；版本一致性校验 C6；security-log 存在校验 C8。每条款≥1 用例，名带条款号。
  - 回归（触及核心功能=skill 流程文档本身→核心功能回归，只读）：① SKILL.md frontmatter 可解析且 version=4.3.0；② check_spec.py 对既有两份历史 spec 跑 --stage spec 仍正常退出；③ references 交叉引用文件均存在；④ 本 spec --stage verify 退出码 0。
  - 核心功能清单（首次接入，主脑提议，签约确认生效）：① SKILL.md 可加载（frontmatter 合法）② check_spec.py 正确校验 spec ③ references 交叉引用完整 ④ install/update/build 脚本语法可用。
  - 无 UI/浏览器路径，无坐标断言需求（纯文档）。

## 3. 技术蓝图（按涉及领域填，不涉及写"无变更"）

- **前端**：无变更（本仓库无前端代码；runbook/team-mode 为 Markdown 文档）。
- **后端**：无变更（无接口/服务；check_spec.py 不改）。
- **数据库**：无变更。
- **环境依赖**：无新增依赖/服务/端口/环境变量。runbook 记录既有 DSH 宿主 bailian-tpp 路由（baseURL/apiKeyEnv 名，不含 key 值）作为环境值；新增 docs/security-review-log.md 为流程产物。版本来源沿用 SKILL.md frontmatter + 两处 CHANGELOG。

## 4. 非目标（out of scope）

- 不做：在 SKILL.md / team-mode.md / 任何 skill 正文或代码里写死具体模型名或模型特有数值（skill 硬规则）。
- 不做：修改 check_spec.py 校验逻辑。
- 不做：新建根 CLAUDE.md/AGENTS.md 或 docs/specs/_TEMPLATE.md（项目适配其余项，本次不展开）。
- 不做：改动 DSH 宿主 ~/.dsh 配置（模型路由已在前几轮配好，本次只读取核实）。
- 不做：新增可永久入库的测试脚本（用例置 tmp/，Step 9 清理）。
- 不做：调用付费 API 重跑探针（沿用前几轮已实测结果）。
- 不做：合并 PR / 部署（PR 创建即停，合并按钮属用户）。

## 5. 契约条款（C1 / C2 / …）

### C1 runbook 模型能力清单完整且列齐

- **前置条件**：docs/deploy-runbook.md 存在；Token Plan 可用文本模型目录含 15 个 ID（经 /models 端点 + 本会话分析核实）。
- **后置条件**：runbook「模型能力清单」表恰好覆盖该 15 个模型 ID（auto, qwen4-max, qwen4-max-preview, qwen3.8-max, qwen3.8-flash, qwen3.7-max, qwen3.7-plus, qwen3.6-flash, deepseek-v4.1-flash, deepseek-v4.1-flash-1017, deepseek-v4-pro-0813, deepseek-v4-pro, deepseek-v4-flash-0731, glm-5.3, glm-5.2），每行含「上下文大小」「图像输入」「备注」三列且非空，并含「DSH 已配置」标记列（取值 ✅ 或 ⬜）；图像输入列取值仅为 ✅ 或 ❌。
- **失败行为**：缺模型/缺列/图像列或已配置列出现非法值→校验脚本报 FAIL 并列出缺失项，不得静默通过。
- **不变式**：清单模型 ID 集合 = Token Plan 可用文本目录（15，无遗漏、无臆造）；图像输入列与实测探针结论一致（✅ 集 = auto, qwen4-max, qwen4-max-preview, qwen3.8-max, qwen3.8-flash, qwen3.7-plus, qwen3.6-flash, deepseek-v4.1-flash, deepseek-v4.1-flash-1017）；已配置标记与宿主实际一致（由 C7 核）。

### C2 角色分配表覆盖六角色且测试员满足图像硬要求 🔒

- **前置条件**：runbook 含「角色分配」表；team-mode 角色能力要求表定义六个可分配角色（需求澄清员/后端开发/前端开发/代码审查员/测试员/改动说明员），主脑=会话模型固定不分配。
- **后置条件**：角色分配表为上述六个角色各指定一个模型，且每个模型 ID 都属于 C1 清单**且标记为 DSH 当前已配置（✅）**；测试员所分配模型的「图像输入」列 = ✅ 且已配置。
- **失败行为**：任一角色缺分配/分配了清单外模型/分配了未配置（⬜）模型/测试员模型图像列=❌→校验 FAIL；测试员无图像模型满足时按 team-mode 既有降级（主脑核验）并在 runbook 注明，不得静默分配 ❌ 模型。
- **不变式**：测试员图像输入硬要求不可被成本因素覆盖（成本是能力满足后的软排序因子）🔒。

### C3 时效价位标注到期回退且全仓库新增文件零凭据 🔒

- **前置条件**：runbook 含价位/折扣信息；qwen4-max-preview 预览期 2026-11-11 至 2026-11-25。
- **后置条件**：runbook 中 qwen4-max-preview 的折扣条目显式标注「2026-11-25 到期」及回退模型（qwen4-max 或 qwen3.8-max）；本次新增/修改的所有文件不含 API key 值（无 sk- 前缀密钥串、无 token 值）。
- **失败行为**：折扣无到期标注/无回退→校验 FAIL；任一文件命中 sk- 密钥串→校验 FAIL 且不得提交（凭据纪律）。
- **不变式**：能力清单与角色分配为 durable 配置，促销价为带日期的时效备注；凭据永不入库 🔒。

### C4 team-mode 成本感知原则就位且全文零模型名 🔒

- **前置条件**：team-mode.md 现有「模型发现流程」「角色能力要求表」「注册表模板」「复核触发」节；当前全文零模型名（qwen/deepseek-v/glm-5/kimi-k 匹配数=0）。
- **后置条件**：team-mode.md 新增通用成本/折扣感知分配原则（能力满足前提下按性价比排序、高并发/批量角色优先轻快、注意订阅折扣窗口），复核触发新增「价格/折扣变动」项，注册表模板新增可选成本列；改后全文仍零具体模型名。
- **失败行为**：成本原则缺失/复核触发未加价格项/模板未加成本列→校验 FAIL；改后出现任何具体模型名→校验 FAIL（违反 skill 硬规则）。
- **不变式**：skill 正文（SKILL.md/team-mode.md）任何时刻零具体模型名 🔒；成本是软排序因子，不得覆盖硬能力要求。

### C5 SKILL 与 README 团队模式表述同步为能力加性价比

- **前置条件**：SKILL.md 团队模式节有「模型分配能力驱动」bullet；README.md 团队模式节有对应 bullet。
- **后置条件**：两处 bullet 均更新为「能力+性价比驱动」语义（含成本/折扣排序表述），且 SKILL.md 全文零具体模型名；SKILL.md frontmatter 仍合法可解析。
- **失败行为**：任一 bullet 未同步/ SKILL.md 出现模型名/ frontmatter 解析失败→校验 FAIL。
- **不变式**：SKILL.md 与 README 与 team-mode.md 三者对"模型分配驱动因素"表述一致（能力+性价比），无漂移。

### C6 版本 4.3.0 三处一致

- **前置条件**：现版本 4.2.0；版本来源=SKILL.md frontmatter + ship-it/CHANGELOG.md + CHANGELOG.md 版本索引。
- **后置条件**：SKILL.md frontmatter version=4.3.0；ship-it/CHANGELOG.md 顶部含「4.3.0（2026-11-16）」节；CHANGELOG.md 版本索引含 v4.3.0 行（日期 2026-11-16）；三处版本号字符串一致。
- **失败行为**：任一处版本≠4.3.0 或缺条目→校验 FAIL（版本号两处打架是常见坑）。
- **不变式**：本次为 minor 递增（新增成本感知能力，无破坏性变更）；版本唯一真源不被引入第四处。

### C7 清单覆盖宿主已配置子集且来源标注准确

- **前置条件**：DSH 宿主 ~/.dsh/profiles/desktop/cordis.patch.yml 的 llm-pi-ai.providers.bailian-tpp.models 列表可读（当前 7 个）。
- **后置条件**：runbook 清单中标记「DSH 已配置 ✅」的模型集合与宿主配置 models[].id 集合完全相等（7 个）；宿主已配置集合 ⊆ 清单 15 模型集合；已配置模型的上下文大小列与配置 contextWindow 一致（auto=262144，其余=1000000）；清单来源备注区分「Token Plan 可用目录（15）」与「DSH 当前已配置（7）」，不得谎称清单=宿主配置。
- **失败行为**：已配置标记≠宿主配置/宿主模型不在清单/已配置模型上下文不符/来源备注谎称相等→校验 FAIL 并列出差异；配置不可读→按 team-mode 离线回退注明"能力信息可能过期"，不静默通过。
- **不变式**：清单 = Token Plan 可用文本目录（15，较宽），宿主已配置 = 其子集（7）；角色分配只用已配置子集；后续漂移由复核触发处理。

### C8 安全审查日志建立并记录本次增量结论

- **前置条件**：仓库无 docs/security-review-log.md；本次为零依赖纯文档改动。
- **后置条件**：docs/security-review-log.md 存在，含一条 2026-11-16 记录：范围（本次改动文件）、联网核验状态（零第三方依赖，npm audit/OSV 不适用）、P0/P1/P2 清单（均无）、结论（零新增攻击面，无凭据入库）。
- **失败行为**：日志缺失/记录缺范围或结论→校验 FAIL。
- **不变式**：安全审查为周期任务，本次增量结论入 git 可追溯；P0 未清零不开工/不发布（本次 P0=0）。

## 6. 验收标准（用户逐条打勾）

- [ ] A1 打开 docs/deploy-runbook.md 能看到 15 个模型的能力清单表（含上下文/图像输入/备注）+ 六角色分配表 + 价位折扣表（qwen4-max-preview 标注 2026-11-25 到期与回退）。
- [ ] A2 角色分配表中测试员分配的模型图像输入列为 ✅（如 qwen3.8-max），且六个角色都有分配。
- [ ] A3 team-mode.md 出现成本/折扣感知分配原则与价格变动复核触发，且全文搜索 qwen/deepseek-v/glm-5/kimi-k 命中数为 0。
- [ ] A4 SKILL.md frontmatter version=4.3.0，ship-it/CHANGELOG.md 与 CHANGELOG.md 均有 4.3.0（2026-11-16）条目。
- [ ] A5 在仓库根执行 python ship-it/scripts/check_spec.py docs/specs/2026-11-16-token-plan-model-registry.md --stage verify 退出码为 0。
- [ ] A6 全仓库新增/修改文件 grep sk- 密钥串命中数为 0（无凭据入库）。

## 7. 边界与异常

| 场景 | 期望表现 |
|---|---|
| 模型列表变动（新增/移除/改名） | team-mode 既有复核触发：增量联网核实+探针+重分配写回 runbook |
| 价格/折扣变动（促销开始/结束） | 新增复核触发：增量更新清单成本列与角色分配，到期模型按回退切换 |
| qwen4-max-preview 2026-11-25 到期下线 | runbook 回退备注指向 qwen4-max/qwen3.8-max；分配表需更新，不得继续分配已下线模型 |
| DSH 配置滞后于实际路由 | 以实际路由为准（team-mode 既有规则），注册表按实际增量补记 |
| 无图像输入模型满足测试员 | 降级主脑亲自核验截图（team-mode 既有机制），runbook 注明 |
| 离线/拉取模型列表失败 | 用最近注册表并注明"能力信息可能过期"（team-mode 既有回退） |
| 新增文件误含凭据 | C3 校验 FAIL，禁止提交；凭据纪律 |

> 本表即 Step 4 异常路径测试的清单来源：只测这里声明的项。

## 8. 三问完整性检查 + DoR（不过不得开工）

- [x] ① **取值范围**：模型 ID = DSH bailian-tpp.models[].id 枚举（15 个，C1 列明）；上下文 = 正整数（262144 或 1000000）；图像输入 = ✅/❌ 枚举；角色 = 六角色枚举；版本 = SemVer `4\.3\.0`；折扣 = 带日期字符串。均可精确描述。
- [x] ② **状态流转**：模型注册表生命周期 = 拉列表→联网核实→探针→记录清单→分配角色→（复核触发：列表变动/实际路由新模型/能力异常/价格折扣变动）→增量重扫→写回 runbook。触发条件与 guard（硬能力>软能力>成本）明确，可画状态机。
- [x] ③ **生成逻辑**：runbook 清单 = f(DSH 配置模型列表, 联网能力核实, 探针结果)；角色分配 = f(角色能力要求, 清单, 性价比排序)；版本 = bump_minor(4.2.0)=4.3.0；安全日志 = f(本次改动范围, 依赖核验)。每个输出一句话可描述。

**DoR 自检**（Definition of Ready）：需求无歧义 ☑（scope B + promo 完整放入已确认）、技术可行 ☑（纯 Markdown + stdlib 校验）、影响面已盘 ☑（第 2 节）

> 任何一问答不出 = spec 没写完，补齐再进编码。

---

## 9. 核销记录（Step 5 填写，PR 里引用）

| 条款 | 测试用例 | 结果 | 路径真实性 |
|---|---|---|---|
| C1 | `test_c1_registry_complete` | ✅ | 脚本解析清单表 + 探针实测图像集核对 |
| C2 | `test_c2_role_assignment` | ✅ | 脚本解析分配表 + 已配置子集核对 |
| C3 | `test_c3_expiry_and_no_credentials` | ✅ | 脚本 grep 到期/回退 + 凭据正则扫描 |
| C4 | `test_c4_teammode_cost_aware_no_modelnames` | ✅ | 脚本 grep 成本原则 + 模型名零出现 |
| C5 | `test_c5_skill_readme_sync` | ✅ | 脚本 grep 同步表述 + frontmatter 解析 |
| C6 | `test_c6_version_consistency` | ✅ | 脚本三处版本字符串核对 |
| C7 | `test_c7_registry_covers_configured_subset` | ✅ | 脚本读宿主配置 + 子集/上下文/来源核对 |
| C8 | `test_c8_security_log` | ✅ | 脚本核验日志存在与要素 |

- 核销率：8/8；分级回归：核心功能回归 PASS 6 / WARN 0 / FAIL 0（报告：tmp/report.md、tmp/report.json）
- 契约派生用例：tmp/test_contract.py（Python stdlib，8 条款用例 + 6 回归项，退出码 0）；Step 9 清理
- 影响面（来自第 2 节）：新增 runbook/security-log/spec；修改 team-mode/SKILL/两处 CHANGELOG/README；无代码调用方/接口/表/缓存变更
- Step 4 遇阻记录：宿主配置签约后 15→7，C7 一度 FAIL；经用户选 A 调和（spec-first 修订 C1/C2/C7 + runbook 加「DSH 已配置」列 + 审查员改 glm-5.3），重跑 8/8 PASS
