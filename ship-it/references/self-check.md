# 编码后自检（Step 2.2 / 2.3 展开）

> Step 2 里"验证无异常"跑完之后的两个必做项。返回：`SKILL.md` 的 Step 2。

## 2.2 UI 视觉自测（**坐标断言，不是属性断言**）

凡涉及 CSS / 布局 / 定位 / 浮层 / 动画的改动，必做；纯后端/逻辑跳过。

- 用 Playwright 量**实际渲染坐标**（`getBoundingClientRect`），**不只看 `getComputedStyle`**；
- 断言必须是**数值**："文字距容器底部 ≤ 10px"、"面板底部 < 选区顶部（不遮挡）"、"折叠前后导航高度 45.2 ±1px"；
- 动画类改动**逐帧采样**，别只看终态；
- 无 Playwright 时至少用 DevTools 手量并把数值记进 PR。

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    pg.goto("http://localhost:5173/#/dashboard")   # 换成目标页
    pg.wait_for_timeout(1500)
    for i in range(6):                              # 动画逐帧采样
        h = pg.evaluate("document.querySelector('.nav').getBoundingClientRect().height")
        print(f"frame{i}: navH={h:.1f}")
        pg.wait_for_timeout(50)
    lh = pg.evaluate("document.querySelector('.nav__label').getBoundingClientRect().height")
    assert lh < 30, f"标签疑似换行，高度 {lh}"       # 断言自己改
    b.close()
```

**两个真实翻车（别重犯）**：

| 现象 | 根因 | 闸门 |
|---|---|---|
| `vertical-align: middle` 测得 PASS，用户一眼看出文字下方还空 25px | 只断言"属性生效"，没量文字距底部多少 px（`<p>` 的 16px margin 把 bottom 对齐顶开了） | 本条：坐标数值断言 |
| API 设选区测"菜单向上弹" PASS，用户鼠标拖选时根本不弹 | 测试走 API 捷径，与用户真实路径不同 | Step 3.3 路径真实性核销 |

## 2.3 一致性复查六项（防"改了 A 漏了 B"）

| # | 项 | 判据 |
|---|---|---|
| 1 | **注释语言** | 与项目约定一致（多数中文项目要求注释中文；bat/vbs 必须纯 ASCII）。`grep` 扫改过的文件里纯英文注释行，改掉。典型漏网：复制粘贴的英文注释、`// --- xxx ---` 分节注释 |
| 2 | **变量声明风格** | 是否混用 `var`/`const`/`let`？与同目录其他文件一致吗？ |
| 3 | **全局引用扫描** | 改的路径/URL/模型名/环境变量/接口前缀，`grep -rn "<旧值>" .` 全搜一遍（典型漏网：接口前缀迁移只改主文件，漏了脚本与文档） |
| 4 | **文档清单同步** | 新增/删除/重命名文件后，README / CLAUDE.md / 结构文档的文件清单、命令表、表清单是否同步 |
| 5 | **死代码** | 未使用的参数/import/变量、注释掉的代码块、不可达分支 —— 删干净 |
| 6 | **错误提示准确性** | 错误文案里建议的命令/路径/端口是否真实可执行（如提示 `node sync.js` 却漏了 `scripts/` 前缀） |

> 数据：一次代码审查 24 个问题里 17 个 LOW 的根因都是"改完没复查"。六项成本 5 分钟。

**只在发现问题时汇报**：六项全过，汇报里一句"复查通过，无问题"即可；发现问题才逐条列出问题与修复情况，不要逐条复述"第 N 项已检查"。
