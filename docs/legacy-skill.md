# 独立黄金分析 Skill（兼容功能）

本仓库保留上游的 `.claude/skills/gold-analysis/`，可在 Agent 中单独触发黄金分析报告。以下是独立 Skill 的安装和手动核验方法，适用于保留的报告功能。双模型六账户操盘、持续监控与网页部署请使用[主 README](../README.md)。

独立 Skill 中的银行换算、三轴规则和浏览器脚本，与当前自主账户的执行方式不同：自主账户按京东直取报价成交，买卖和保护由模型决定，常驻监控不启动 Chromium。

## 🚀 快速开始

### 通用前置依赖

- **Python 3.9+**：用于运行 `.claude/skills/gold-analysis/scripts/` 下的实时行情/银行报价/金友圈抓取脚本
- **Playwright + Chromium**（可选，但强烈推荐）：京东金融银行积存金页面与金友圈帖子需要它

```bash
pip install -r requirements.txt
python -m playwright install chromium   # Linux 首次安装可加 --with-deps 补系统库
```

> 没有 Playwright 也能跑：脚本会自动回退到 `latestPrice` API 兜底，并在报告中明确标注降级。

- **浏览器串行**：金友圈抓取和银行报价两个脚本都会启动 Chromium，请依次运行、不要同时开（低配机器并发会超时）。
- **网络代理**：境外数据源（CNBC 现货金、汇率 API）默认走本机 Clash `http://127.0.0.1:7890`。代理地址不同可设 `GOLD_TRADING_HTTP_PROXY=http://host:port`，不需要代理则设 `GOLD_TRADING_HTTP_PROXY=`（空）直连。

---

### 安装：四种 Agent 工具适配

本仓库将符合 [Anthropic Skills 规范](https://docs.claude.com/en/docs/claude-code/skills) 的**黄金分析技能**放在 **`.claude/skills/gold-analysis/`**（内含 `SKILL.md`、`references/`、`scripts/`、`assets/`）。你也可以在 `.claude/skills/` 下按同样结构并列其他技能目录。克隆到 Agent 的 skills 目录后，请用下文的完整相对路径触发。请按你使用的 Agent 选择对应安装方式。

<details>
<summary><b>方式 A：Cursor IDE</b></summary>

Cursor 把全局 skills 放在 `~/.cursor/skills/`；项目级则放在仓库内 `.cursor/skills/` 或 `.agents/skills/`。

```bash
# 全局安装（任何项目都能 @触发）
git clone https://github.com/blue-green-red/Trade-Accumulated-Gold-CN.git \
  ~/.cursor/skills/Trade-Accumulated-Gold-CN

# 或：项目内安装（仅当前项目可见）
git clone https://github.com/blue-green-red/Trade-Accumulated-Gold-CN.git \
  ./.agents/skills/Trade-Accumulated-Gold-CN
```

在 Cursor Chat 内 `@` 触发（技能入口在 **`.claude/skills/gold-analysis/`**）：

```
@Trade-Accumulated-Gold-CN/.claude/skills/gold-analysis/SKILL.md 当前积存金点位分析
@Trade-Accumulated-Gold-CN/.claude/skills/gold-analysis/SKILL.md 现在能买吗？
```

若你直接把本仓库当作打开的工作区根目录，也可用相对路径：`@.claude/skills/gold-analysis/SKILL.md`。

</details>

<details>
<summary><b>方式 B：Claude Code（Anthropic 官方 CLI）</b></summary>

Claude Code 的 skills 默认存放路径为 `~/.claude/skills/`。

```bash
# 全局安装
git clone https://github.com/blue-green-red/Trade-Accumulated-Gold-CN.git \
  ~/.claude/skills/Trade-Accumulated-Gold-CN
```

本仓库的技能入口为 **`~/.claude/skills/Trade-Accumulated-Gold-CN/.claude/skills/gold-analysis/SKILL.md`**（克隆后的**仓库根**下没有 `SKILL.md`，入口在上面的嵌套目录里）。若工具只认「每个技能文件夹根上就有一个 `SKILL.md`」这一种布局，可将本仓库里的 **`gold-analysis` 整个目录**单独复制/符号链接到 `~/.claude/skills/gold-analysis`（或与官方文档一致的任意技能目录名），使 **`~/.claude/skills/gold-analysis/SKILL.md`** 成立；其余 `scripts/`、`references/` 随之同级即可。也可查阅当前 Claude Code 版本是否支持递归发现子目录中的 `SKILL.md`。

启动 `claude` 后，在已正确识别技能路径的前提下，无需 `@` 也可能在你提问「帮我分析积存金现在能不能买」时被自动选中调用。如需强制触发可显式说：

```
请使用 Trade-Accumulated-Gold-CN 这个 skill 帮我分析当前金价
```

</details>

<details>
<summary><b>方式 C：OpenClaw / ClawHub</b></summary>

OpenClaw 的 skills 路径与 Claude Code 类似，但前缀是 `~/.openclaw/`，并支持工作区级目录：

| 作用域 | 路径 |
|--------|------|
| 全局 skills | `~/.openclaw/skills/` |
| 工作区共享 | `~/.openclaw/workspace/skills/` |
| 当前 Agent 私有 | `~/.openclaw/workspace/agent/skills/` |

```bash
# 推荐安装到全局（所有 agent 共享）
git clone https://github.com/blue-green-red/Trade-Accumulated-Gold-CN.git \
  ~/.openclaw/skills/Trade-Accumulated-Gold-CN
```

技能文件实际位于 **`…/Trade-Accumulated-Gold-CN/.claude/skills/gold-analysis/`**（与方式 B 相同嵌套结构）。若 OpenClaw 只扫描克隆目录第一层，请将该 **`gold-analysis`** 文件夹按工具说明单独登记，或复制/链接到其期望的技能根目录。

ClawHub 启动后会在「Skills」面板看到本技能，点击或在对话中提及即可调用。

</details>

<details>
<summary><b>方式 D：Gemini CLI（Google 官方）</b></summary>

Gemini CLI 在 v0.x 起原生支持 Anthropic Skills 规范，目录约定为 `~/.gemini/skills/`（用户级）或 `./.gemini/skills/`（工作区级），并提供专门的 `gemini skills install` 命令。

```bash
# 方式 1：用官方命令（推荐）。本仓库 SKILL 不在 Git 根目录，必须指定 --path：
gemini skills install https://github.com/blue-green-red/Trade-Accumulated-Gold-CN.git \
  --path .claude/skills/gold-analysis
# 仅当前项目：
gemini skills install https://github.com/blue-green-red/Trade-Accumulated-Gold-CN.git \
  --scope workspace --path .claude/skills/gold-analysis

# 方式 2：手动 git clone 全仓库后，在 Gemini 侧用 link 指向技能目录（示例）：
# git clone https://github.com/blue-green-red/Trade-Accumulated-Gold-CN.git \
#   ~/.gemini/skills/Trade-Accumulated-Gold-CN
# gemini skills link ~/.gemini/skills/Trade-Accumulated-Gold-CN/.claude/skills/gold-analysis
```

安装完成后，在会话里用 **`/skills list`** 确认已发现该技能；模型会根据 **`SKILL.md` 头部 `description` 自动决定是否调用**（安装后的磁盘路径以 `gemini skills list` 显示为准）。

</details>

---

### 触发示例

无论哪种 agent，安装完成后都可以这样触发：

```
当前积存金点位分析
现在能不能买入积存金？
帮我分析黄金行情，重点看 30min/1H 信号
```

> AI 会自动执行 4 个阶段：消息面+金友圈共识 → 实时行情+技术分析 → 三轴决策+积存金换算 → 落盘报告，全程约 30-90 秒。

---

### 独立脚本：手动核验

不想跑完整工作流，只想看一下当前银行报价或博主观点？两个脚本都能独立执行：

```bash
# 下面两个 Chromium 脚本请依次运行，不要同时跑
# XAUUSD 现货价 + USD/CNY 汇率 + 理论换算价（任一源失败输出 null，不用估计值补位；不开浏览器）
python "./.claude/skills/gold-analysis/scripts/live_market_data.py"

# 浙商 / 民生积存金报价（Playwright 优先，失败自动 fallback 到 JD API）
python "./.claude/skills/gold-analysis/scripts/fetch_bank_quotes.py"

# 京东金融金友圈 [@黄金小小彬] 最新一条观点
python "./.claude/skills/gold-analysis/scripts/fetch_jd_personal_latest_post.py"
```

三者都输出**人类可读摘要 + 完整 JSON**，方便接入下游分析。

**没有 Playwright 又想读银行页面？** 在 Cursor 里可以让 Agent 走 `cursor-ide-browser` MCP（`browser_navigate` → `browser_lock` → `browser_snapshot` → `browser_unlock`）；其他 Agent 则会按 `.claude/skills/gold-analysis/SKILL.md` 阶段 2 的降级流程自动切换到搜索/SGE/理论换算兜底，并在报告中明确标注数据来源等级。

---


## 上游来源

原项目：[PlevanTem/Trade-Accumulated-Gold-CN](https://github.com/PlevanTem/Trade-Accumulated-Gold-CN)。原作者交流信息：微信 `lelouchdbf`；[原作者赞助页面](https://www.buymeacoffee.com/bufan666)。这些信息属于上游作者。

Skill 指令与参考文档：

- [SKILL.md](../.claude/skills/gold-analysis/SKILL.md)
- [技术分析参考](../.claude/skills/gold-analysis/references/technical-analysis.md)
- [积存金参考](../.claude/skills/gold-analysis/references/accumulation-gold.md)
- [报告模板](../.claude/skills/gold-analysis/references/report-template.md)

沿用上游声明的 MIT License。
