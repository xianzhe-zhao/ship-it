# 代码安全员安全审查库（security-kb）

> 本文件是团队模式「代码安全员」的**安全审查知识库**：数据源、工具矩阵、严重度规则、更新机制、报告模板与降级口径。
> 它不是实时漏洞数据库，也不内置 SonarQube 服务；它规定**查什么、用什么查、怎么记证据、查不到怎么办**。
> 凭据（token/密钥）只从环境变量读取，**禁止写入本文件、脚本、commit 或报告**。

## 1. 什么时候用

- 团队模式 Step 4：测试员做验收测试；代码安全员做代码审查 + 安全检查；
- 周期安全审查（`references/security-review.md`）的增量核验；
- 新增依赖、升级版本、新增外部输入面、权限/鉴权/加密/反序列化相关改动。

## 2. 数据源（按优先级）

| 优先级 | 数据源 | 用途 | 访问方式 | 备注 |
|---|---|---|---|---|
| 1 | **OSV**（osv.dev） | 按 ecosystem/package/version 查已知漏洞（GHSA/PyPA/RustSec/Go 等） | `https://api.osv.dev/v1/query` | 无需 key；记录查询日期 |
| 2 | **GitHub Advisory Database** | GHSA/CVE 详情、影响版本、修复版本 | `https://github.com/advisories` / API | 与 OSV 交叉核对 |
| 3 | **NVD**（nvd.nist.gov） | CVE/CVSS/CPE 官方口径 | NVD API / 网页 | API key 可选；限流时降级 |
| 4 | **CISA KEV** | 已知被利用漏洞目录 | `https://www.cisa.gov/known-exploited-vulnerabilities-catalog` | **命中 KEV 优先 P0/P1** |
| 5 | **EPSS**（FIRST） | 漏洞被利用概率 | `https://api.first.org/data/v1/epss` | 辅助排序，不单独定级 |
| 6 | **endoflife.date** | 语言/框架/数据库 EOL 与支持周期 | `https://endoflife.date/api/<product>.json` | 版本过期 → 至少 P2 |
| 7 | 厂商公告 | 补丁/安全公告 | 各厂商 security advisory | 以官方原文为准 |
| 8 | OWASP Top 10 / CWE Top 25 / SANS 25 | 手工审查清单 | 本地知识库 | 用于人工覆盖，不替代漏洞查询 |

> **最新性口径**：任何“最新/已修复/无漏洞”结论必须附**来源 URL + 查询日期 + 查询的包/版本**；**单次查询结论超过 7 天未复核**标「可能过期」；无网络标「未联网核验」，不得声称最新。

## 3. 工具矩阵（按技术栈选装，不强制全装）

| 类别 | 工具 | 典型命令/入口 | 适用 |
|---|---|---|---|
| SAST | **SonarQube / SonarScanner**（可选） | `sonar-scanner`；API `/api/issues/search`、`/api/measures/component` | 多语言；需要服务地址+token |
| SAST | **Semgrep** | `semgrep --config auto --metrics off --json`（保密仓库建议关 metrics） | 多语言、规则可定制 |
| SAST | **CodeQL** | `codeql database create/analyze` | 多语言、深度查询 |
| SAST | **Bandit** | `bandit -r . -f json` | Python |
| SAST | **ESLint security plugins** | `eslint --plugin security` | JS/TS |
| SCA | **npm audit** | `npm audit --json` | Node.js |
| SCA | **pip-audit** | `pip-audit -f json` | Python |
| SCA | **OSV-Scanner** | `osv-scanner --lockfile=<file>` | 多生态锁文件 |
| SCA | **Trivy** | `trivy fs --scanners vuln,secret,misconfig .` | 依赖/容器/IaC/密钥 |
| SCA | **Grype** | `grype dir:.` | 容器/文件系统 |
| SCA | **OWASP Dependency-Check** | `dependency-check --scan .` | Java/.NET 等 |
| 密钥 | **gitleaks** | `gitleaks detect --no-banner` | Git 历史/工作区 |
| 密钥 | **trufflehog** | `trufflehog filesystem .` | 文件系统 |
| IaC | **Checkov** | `checkov -d .` | Terraform/K8s/CloudFormation |
| IaC | **tfsec / kics** | `tfsec .` / `kics scan -p .` | Terraform/K8s |
| SBOM | **Syft / CycloneDX** | `syft dir:. -o cyclonedx-json` | 依赖清单 |
| DAST | **OWASP ZAP**（可选） | `zap-baseline.py -t <url>` | 有测试环境时 |

### SonarQube 可选适配（不内置服务）

```text
环境变量（只放环境变量，不入库）：
  SONAR_HOST_URL      例如 https://sonar.example.com
  SONAR_TOKEN         用户 token
  SONAR_PROJECT_KEY   项目 key

命令（token 只从环境变量读；禁止写在命令行/历史/报告）：
  # SonarScanner 读取 SONAR_TOKEN 环境变量；不要把 -Dsonar.token=... 写进命令行
  sonar-scanner -Dsonar.host.url="$SONAR_HOST_URL" \
                -Dsonar.projectKey="$SONAR_PROJECT_KEY"

  # API 查询用临时 netrc（权限 600）或从环境变量读 header，避免 token 出现在进程列表
  curl -s --netrc-file "$HOME/.sonar-netrc" \
    "$SONAR_HOST_URL/api/issues/search?componentKeys=$SONAR_PROJECT_KEY&resolved=false"
```

> ⚠️ 不要把 token 直接拼进 `curl -u` / `-H` 命令行（会出现在进程列表/Shell 历史）；用环境变量 + 临时 netrc/凭据文件，文件权限 600，用完删除。**Windows 用 `icacls <file> /inheritance:r /grant:r "%USERNAME%:R"` 收紧 ACL**；报告只写「token 已配置/未配置」，不写值。

- 没有服务/ token → **不运行**，在报告中写「SonarQube 未接入」，改用 Semgrep/CodeQL/语言专用工具；
- 禁止伪造 SonarQube 结果；
- 禁止把 token 写进报告、日志、commit。

## 4. 严重度与优先级

| 级别 | 判定 | 例子 |
|---|---|---|
| **P0** | 已利用/可直接接管/凭据泄露/未授权访问 | KEV 命中且可达；硬编码生产密钥；认证绕过；RCE |
| **P1** | 高概率可利用/有公开 PoC/有修复版本 | 注入、SSRF、路径穿越、反序列化、越权；高危依赖且可达 |
| **P2** | 防御纵深/低可达/中低危/版本将 EOL | 信息泄露、配置加固、缺少安全头、EOL 临近 |
| **P3** | 建议/最佳实践 | 命名、日志脱敏建议 |

排序：**KEV/已利用 > 可达性 > 修复版本可用性 > CVSS/EPSS > 防御纵深**。CVSS 高但不可达可降级；CVSS 中但 KEV 命中必须升级。

## 5. 审查流程（代码安全员）

1. **范围**：读 spec + diff + 依赖清单/SBOM；确认改动面（鉴权/输入/加密/文件/网络/反序列化/依赖）。
2. **依赖与版本**：按锁文件/包清单查 OSV/GHSA/NVD；查 EOL；记录包名+版本+来源+日期。
3. **SAST/SCA**：按技术栈选工具；优先跑 diff 范围；全量扫描按项目约定。
4. **密钥/配置**：gitleaks/trufflehog；检查 `.env`、日志、错误信息、前端 bundle；**只列键名/`path:line`，不复制值**（如 `grep -o '^[A-Z0-9_]*=' .env`），报告不出现密钥原文。
5. **人工审查**：OWASP/CWE 清单覆盖；重点看输入校验、输出编码、鉴权、会话、CSRF、SSRF、文件上传、反序列化、加密、错误处理。
6. **定级**：按第 4 节；每条给证据（文件:行 / 命令+退出码 / 来源 URL+日期）。
7. **报告审查员**：结构化报告；不通过 → 审查员汇总主脑 → 开发修 → 再测试 → 再安全检查。
8. **复核**：修复后重跑对应工具/查询；最多 2 轮；仍不过报主脑/用户。

## 6. 报告模板（给审查员汇总）

```markdown
### 代码安全员报告 S-<n>
- 范围：<diff/模块/依赖清单>
- 工具：<工具名+版本>；<未接入/未运行及原因>
- 数据源：<OSV/GHSA/NVD/KEV/EPSS/endoflife.date + URL + 查询日期>
- 依赖：<包名@版本 → 结果；无漏洞也要写查询日期>
- 发现：
  | ID | 级别 | 类型(CWE/OWASP) | 证据(path:line/命令+退出码) | 来源 | 修复建议 |
- 结论：PASS / FAIL（P0/P1 数）
- 残留风险：<无/说明>
- 声明：只读；未改代码；未存凭据；后台可见性：完整/降级/不可见
```

## 7. 更新机制（保持“最新”）

| 频率 | 动作 |
|---|---|
| 每次依赖变更 | 立即查 OSV/GHSA/NVD + EOL |
| 每周 | 对活跃依赖跑 SCA；复核 KEV/EPSS；检查工具规则更新 |
| 每月 | 全量复核本 KB 数据源/工具/严重度规则；更新本文件「最近复核」日期 |
| 季度 | 评估新工具/新数据源；淘汰失效链接 |

> 本文件**末尾**记录「最近复核：YYYY-MM-DD」；**30 天 = KB 文件整体复核周期**（7 天 = 单次漏洞查询结论时效）；超过 30 天未复核，报告必须写「KB 可能过期」。

## 8. 离线/无工具降级

- 无网络：用本地缓存/历史报告，标「未联网核验，可能过期」；不得声称最新。
- 无 SAST/SCA：用人工清单 + 依赖清单核对，标「工具缺失」；P0/P1 仍需人工重点覆盖。
- 无 SonarQube：用 Semgrep/CodeQL/语言工具替代，标「SonarQube 未接入」。
- 无权限扫描测试环境：只做静态审查，标「未做 DAST」。

## 9. 边界

- 只读：不改代码/spec/任务树；不写生产数据；不执行破坏性扫描。
- 不替代测试员（验收测试）与裁判员（契约审核）。
- 不把凭据、token、生产数据写进报告。
- 不凭记忆断言「最新/无漏洞」；必须有来源+日期。
- 不把 SonarQube/工具结果当作唯一依据；人工审查仍必须覆盖。

---

> 相关：`references/security-review.md`（周期安全审查 playbook）、`references/team-mode.md`「代码安全员」。
> 最近复核：2026-11-18（首次建立；数据源/工具矩阵/严重度规则）。
