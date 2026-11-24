# 2026-11-23 裁判员 J1 补充复审（v5.0.0 spec rev4 · C33 单条）

角色：referee（裁判员）
审查者：judge
会话标识：judge / 父会话 session-0af8bef5-2481-45c2-b896-64b58b99bcf2
spec_revision：4
spec_hash：b12e95368b093da9da386b26228d64bac678ecfe605dcb1fc3eb5a1cc4962cac（hash_scope: sections_1_8）
未参与编码声明：是（未改代码/测试/spec）
未参与 spec 编写声明：是
结论：DEVIATION（C33 条款本体合规；三问未覆盖 C33/A29 需补；附 C13 违规事实作为 C33 有效性的反面印证）
汇总来源：本裁判员直读 spec rev4 C33/A29/三问节 + list_agents 实况 + team-mode.md C13 规则；无子代理报告（叶子会话）。

## 非最终裁定声明
本裁判单为审计意见，不是最终裁定。裁判员不是最终裁定者；PASS 不替代用户验收与 check_spec.py 机器校验。裁判单交监察员汇总，不直接报主脑。

## 测试/代码边界声明
未执行测试、未审代码；测试归测试员，代码审查+安全检查归代码安全员。J1 只审契约合规，不审技术方案优劣/代码质量。

## 后台可见性
完整（直读仓库文件 + list_agents 实况，非后台审查）。

## 审查范围
主脑同意对 rev4 新增 C33 条款补 J1 合规复审。审查四项：①C33 四要素；②A29 可逐条打勾；③越权暗示；④三问覆盖 C33。另按主脑指示记录一处 C13 违规事实作为 C33 有效性的反面印证。

## 一、C33 单条合规审查

C33 全文位于 `docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:398-403`：「### C33 主脑派发前必查可用智能体容量」。

### 1. 四要素是否齐全 — ✓ 通过

| 要素 | 位置 | 内容 | 判定 |
|---|---|---|---|
| 前置条件 | :400 | 主脑派发任何 subagent/teammate 前 | ✓ |
| 后置条件 | :401 | 派发前必须调用 list_agents 查看运行中智能体数量与并发上限，确认空闲容量再派发；不得凭经验判断；容量不足排队等待或等已有角色 inactive 后再派 | ✓ |
| 失败行为 | :402 | 主脑未查 list_agents 即派发导致超并发上限或派发失败 → 监察员巡视判定违规，报主脑纠正；裁判员 J2/J3 审计 | ✓ |
| 不变式 | :403 | 把「派发前检查容量」从经验判断变为机器可查的硬约束；与监察员 watchdog 巡检互补 | ✓ |

四要素俱全，无缺漏。

### 2. A29 验收项是否可逐条打勾 — ✓ 通过

`docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:437`：「- [ ] A29 主脑派发前已查 list_agents 容量，未凭经验判断；无超并发或派发失败。」

- 格式合规：`- [ ]` 待勾选。
- 可观察结果：三项均可机器核验——①派发前是否调用了 list_agents（派发记录/日志可查）；②是否凭经验判断（无 list_agents 调用记录即违规）；③有无超并发或派发失败（list_agents 显示 running>limit 或派发报错）。
- 与 C33 后置/失败行为一一对应，可逐条打勾。

### 3. 是否有越权暗示 — ✓ 无

对 C33(:398-403) 与 A29(:437) 做越权/自判词汇扫描：
- 「自判通过/自判 PASS/代合并/gh pr merge/代点合并/AI 可自选/可自选/默认单干/可不问用户/可省略验收/代验收/代勾」均 0 命中。
- 「凭经验判断」2 命中（:401 后置条件「不得凭经验判断」、:437 A29「未凭经验判断」），均在反越权语境（禁止凭经验），非越权暗示。
- C33 失败行为(:402) 判定主体为「监察员巡视判定 + 裁判员 J2/J3 审计」，非主脑自判，符合「执行者≠裁定者」（全局 AGENTS.md:44、ins_ca589bdb）。
- 无 AI 自判通过/代合并 PR/代验收/代勾等越权暗示。

### 4. 三问是否覆盖 C33 — ⚠️ DEVIATION（未覆盖）

`docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:458-460` 三问节：
- **三问①（:458）**：列举止于 C32（「C32 由裁判员 J2/J3 人工判定」），**未提及 C33**。兜底句「每条均有机器校验、半机器或人工判定」未单独说明 C33 的判定方式（C33 应为「半机器：list_agents 调用记录可查 + 监察员/裁判员审派发合规」）。
- **三问②（:459）**：声明「A1-A28 每条对应一个可观察结果」，**未覆盖 A29**。A29 对应 C33，可观察结果明确（list_agents 调用记录/超并发/派发失败），但三问②的范围数字仍是 A1-A28，遗漏 A29。
- **三问③（:460）**：8 类边界场景（改名误伤/G3 误报/词典缺失/脚本字符串同步/触发词丢失/远端.gz/大文件写保护/测试同步）未含「派发超并发/未查容量」这一 C33 相关边界，但三问③本就是边界与异常覆盖，C33 属新增流程约束，未列入既有边界尚可理解，不强制要求；唯三问①②必须补 C33/A29。

**结论**：C33 条款本体（四要素/A29/越权）合规，但三问①②未随 C33 新增而同步更新范围，与 rev3 修正三问时的同类疏忽同构（当时漏 A23-A28，现已漏 A29）。属 DEVIATION，需补。

## 二、C13 违规事实记录（C33 有效性的反面印证）

主脑指示记录：主脑在派发审查任务时，未唤醒已有的 monitor/judge（inactive 可唤醒），而是派了新的 monitor-audit/judge-audit，违反 C13 角色复用规则。根因是派发前未查 list_agents（正是 C33 要防的）。

### 证据（list_agents 实况，2026-11-23 15:02 取样）

```
running: 4, limit: 8
agents:
  lead         running     root agent
  judge        running     裁判员J1签约审查
  monitor      running     监察员开工准备
  security    running     代码安全员开工就位
  dev-doc      inactive    文档开发改名身份形态
  dev-script   inactive    脚本开发建词典校验
  dev-doc2     inactive    文档开发SKILL其余条款
  dev-script2  inactive    脚本开发校验扩展
  monitor-audit  inactive  监察员专项审查越权异常
  judge-audit    inactive  裁判员J2流程审计
  tester       running     测试员Step4验收测试
```

### C13 规则依据

`ship-it/references/team-mode.md` + SKILL.md「角色复用（C13）」：**默认 `send_message` 唤醒现有角色；新开仅 `new_missing`/`new_overflow`/`new_independent`/`new_replace` 且附 reason；`role_dispatch` 记录 source。**

### 违规判定

- 现有 `monitor`（running）与 `judge`（running）均在，且即便它们处于 inactive 也可用 `send_message` 唤醒复用。
- 主脑却新开了 `monitor-audit`（监察员专项审查越权异常）与 `judge-audit`（裁判员J2流程审计），未附 `new_missing`/`new_overflow`/`new_independent`/`new_replace` 任一 reason，未见 `role_dispatch.source` 记录。
- 该新开不符合 C13 任一新开情形：monitor/judge 既非缺失（new_missing）、非溢出（new_overflow，running 4 < limit 8）、非独立任务（new_independent，监察员/裁判员职责本就含此类审查）、非替换（new_replace）。
- **根因**：主脑派发前未调用 list_agents 查看现有角色，凭经验/惯性新开，正是 C33 后置条件(:401)「不得凭经验判断」所要防的情形，也是 C33 失败行为(:402)「未查 list_agents 即派发」的典型表现。

### 反面印证意义

此违规恰好证明 C33 的现实必要性：在 C33 尚未实施（仅签约、未编码落地）的阶段，主脑已发生 C33 要防的错误。C33 一旦落地为机器校验（list_agents 调用记录可查），此类违规将被硬约束拦下。本违规事实可作为 C33 有效性的反面印证，亦提示 C13 与 C33 互补——C13 管「该不该新开」，C33 管「派发前有没有查容量/现有角色」。

### 处置建议（供主脑/监察员，非擅自行动）

1. 主脑后续派发前应先 `list_agents`，对可唤醒的 inactive 角色优先 `send_message` 复用，新开务必附 C13 reason 并记 `role_dispatch.source`。
2. 监察员巡视可将此次 C13 违规记入 patrol（派发异常项），报主脑纠正。
3. C33 落地为机器校验后，应在 check_roles 或派发记录校验中检测「派发前 N 分钟内有 list_agents 调用」「新开角色附 C13 reason」两项。

## 三、综合结论与可执行修正建议

### 综合：DEVIATION

- C33 条款本体合规（四要素✓ / A29 可打勾✓ / 无越权✓）。
- 三问①②未覆盖 C33/A29（DEVIATION，需补）。
- C13 违规事实成立，作为 C33 有效性的反面印证记录在案。

### 可执行修正建议

1. `docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:458` 三问①列举末尾补「；C33 由 list_agents 调用记录可查 + 监察员/裁判员审派发合规（半机器）」。或将兜底句明确指向含 C33。
2. `docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:459` 三问②将「A1-A28」改为「A1-A29」，并补一句「A29 对应 C33 派发前查容量」。
3. （可选）`:460` 三问③边界场景补一类「派发超并发/未查容量」。
4. C13 违规处置见上文「处置建议」，由主脑/监察员跟进。

## 备注

- 本补充复审独立成文（`docs/reviews/2026-11-23-referee-J1-supplement.md`），不改动原 J1 裁判单（`docs/reviews/2026-11-23-referee-J1.md` 基于 rev2 的历史记录），便于追溯。
- 原 J1 裁判单结论 DEVIATION（rev2 三问②A1-A22/A1-A28、三问①列举不全）已在 rev3 修正并经我核实；rev4 新增 C33 又引入同类三问覆盖缺口，故本补充复审再次 DEVIATION。
- 证据口径：以上证据均为 `path:line` 或命令实况，≥3 条，符合 team-mode.md:195 证据要求。
---

# 补充复审二：C34 单条 J1 合规审查（v5.0.0 spec rev7）

> 监察员派发（主脑指示）：rev7 新增 C34（团队模式行为机器校验+watchdog_daemon.py），与 C33 同样新增，补 J1 合规审查。审查时点 2026-11-23 16:31+。

角色：referee（裁判员）
审查者：judge
会话标识：judge / 父会话 session-0af8bef5-2481-45c2-b896-64b58b99bcf2
spec_revision：7
spec_hash：a6e74d6564a3c2d47bae1fa0d0bf5da80ba7b6ac891ff5ca4b62c5f3f1ed0113（hash_scope: sections_1_8；已独立实证 check_spec --print-sign-hash EXIT=0）
未参与编码声明：是（未改代码/测试/spec）
未参与 spec 编写声明：是
结论：DEVIATION（C34 条款本体合规；三问未覆盖 C34/A30 需补）
汇总来源：本裁判员直读 spec rev7 C34/A30/三问节；无子代理报告（叶子会话）。

## 非最终裁定声明
本节为审计意见，不是最终裁定。裁判员不是最终裁定者；PASS 不替代用户验收与 check_spec.py 机器校验。裁判单交监察员汇总，不直接报主脑。

## 测试/代码边界声明
未执行测试、未审代码；测试归测试员，代码审查+安全检查归代码安全员。J1 只审契约合规，不审技术方案优劣/代码质量。

## 后台可见性
完整（直读仓库文件，非后台审查）。

## C34 全文

位于 `docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:408-416`：「### C34 团队模式行为机器校验（监察员常驻 + 派发前查含监察员 running）」。

## 1. 四要素是否齐全 — ✓ 通过

| 要素 | 位置 | 内容摘要 | 判定 |
|---|---|---|---|
| 前置条件 | :410 | 团队模式启用；check_roles.py 存在 | ✓ |
| 后置条件 | :411-413 | 新增 watchdog_daemon.py + check_roles.py 两项校验：①监察员常驻校验（patrol log last_active_at 与当前时间差，超阈值 FAIL）②派发前查 list_agents 含监察员 running 校验 | ✓ |
| 失败行为 | :414 | 监察员 inactive 超阈值，或主脑派发前未查 list_agents/未确认监察员 running → check_roles.py FAIL | ✓ |
| 不变式 | :415 | 只校验能机器化的两项；信息流主脑不直接对接下游属行为约束，由 C33 三查 + 监察员巡视 + 裁判员 J2/J3 审计保障；本条是 C5 + C33 的机器闸门落地 | ✓ |

四要素俱全。另 :416 watchdog_daemon.py 说明（独立常驻后台程序，每 N 秒机械巡视，只做机械检查、分析判断归监察员 subagent）属后置条件的实现补充，附于后置条件下，结构合理，非独立第五要素。

## 2. A30 验收项是否可逐条打勾 — ✓ 通过

`docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:451`：「- [ ] A30 check_roles.py 含监察员常驻校验（inactive 超阈值 FAIL）+ 派发前查 list_agents 含监察员 running 校验；团队模式期间监察员保持 running。」

- 格式合规：`- [ ]` 待勾选。
- 可观察结果：三项均可机器核验——①check_roles.py 是否含监察员常驻校验（脚本内容/退出码可查）；②是否含派发前查 list_agents 含监察员 running 校验（脚本内容可查）；③团队模式期间监察员是否保持 running（list_agents/patrol log 可查）。
- 与 C34 后置两项 + 失败行为一一对应，可逐条打勾。

## 3. 是否有越权暗示 — ✓ 无

对 C34(:408-416) 与 A30(:451) 做越权/自判词汇扫描：
- 「自判通过/自判 PASS/代合并/gh pr merge/代点合并/AI 可自选/可自选/默认单干/可不问用户/可省略验收/代验收/代勾」在 C34/A30 范围内均 0 命中。
- 「凭经验判断」全文 2 命中但在 C29/A29（反越权语境），C34/A30 范围内 0 命中。
- C34 失败行为(:414) 判定主体为「check_roles.py 机器校验」（非主脑自判），符合「执行者≠裁定者」（全局 AGENTS.md:44、ins_ca589bdb）。
- C34 后置(:411) 明确「daemon 机械巡视，监察员分析判断，主脑只决策」——三层职责分离清晰，主脑不兼裁定，无越权暗示。
- 无 AI 自判通过/代合并 PR/代验收/代勾等越权暗示。

## 4. 三问是否覆盖 C34 — ⚠️ DEVIATION（未覆盖）

`docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:472-474` 三问节：
- **三问①（:472）**：列举止于 C32（「C32 由裁判员 J2/J3 人工判定」），**未提及 C33、C34**。兜底句「每条均有机器校验、半机器或人工判定」未单独说明 C34 的判定方式（C34 应为「机器校验：check_roles.py + watchdog_daemon.py」）。
- **三问②（:473）**：声明「A1-A28 每条对应一个可观察结果」，**未覆盖 A29、A30**。A30 对应 C34，可观察结果明确（check_roles.py 校验项/监察员 running 状态），但三问②范围数字仍是 A1-A28，遗漏 A29/A30。
- **三问③（:474）**：8 类边界场景未含「监察员 inactive 超阈值/daemon 故障」这一 C34 相关边界，但三问③本就是边界与异常覆盖，C34 属新增机器校验，未列入既有边界尚可理解，不强制要求；唯三问①②必须补 C34/A30。

**结论**：C34 条款本体（四要素/A30/越权）合规，但三问①②未随 C34 新增而同步更新范围，与 C33 supplement 发现的三问覆盖缺口同构（彼时漏 A29，今又漏 A30；三问①列举自 rev3 起一直止于 C32，C33/C34 均未补入）。属 DEVIATION，需补。

## 综合结论与可执行修正建议

### 综合：DEVIATION

- C34 条款本体合规（四要素✓ / A30 可打勾✓ / 无越权✓）。
- 三问①②未覆盖 C34/A30（DEVIATION，需补）。

### 可执行修正建议

1. `docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:472` 三问①列举末尾补「；C33 由 list_agents 调用记录 + 监察员/裁判员审派发合规（半机器）；C34 由 check_roles.py + watchdog_daemon.py 机器校验」。或将兜底句明确指向含 C33/C34。
2. `docs/specs/2026-11-23-v5.0.0-role-clarity-consistency.md:473` 三问②将「A1-A28」改为「A1-A30」，并补一句「A29 对应 C33 派发前三查、A30 对应 C34 团队模式行为机器校验」。
3. （可选）`:474` 三问③边界场景补一类「监察员 inactive 超阈值/watchdog_daemon 故障」。

## 备注（C34 补充）

- 本节追加于同一 supplement 文件（`docs/reviews/2026-11-23-referee-J1-supplement.md`），承接 C33 复审，便于追溯 C33/C34 两条新增条款的 J1 合规审查全貌。
- C33 与 C34 的三问覆盖缺口同构（均因新增条款未同步三问①②范围），建议主脑一次性补齐 C33+C34 的三问覆盖，避免逐条补审反复触发同类 DEVIATION。
- 证据口径：以上证据均为 `path:line`，≥3 条，符合 team-mode.md:195 证据要求。

