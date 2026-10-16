<div align="center">

# ⚡ Gold Accumulation Trading AI · 黄金积存金短线交易 AI

**一句话触发分析 · 聚合实时行情与情绪 · 精准换算国内积存金点位 · 辅助短线交易决策**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Data](https://img.shields.io/badge/Data-实时%20Investing.com-green)](https://www.investing.com/currencies/xau-usd)
[![Stars](https://img.shields.io/github/stars/PlevanTem/Trade-Accumulated-Gold-CN?style=social)](https://github.com/PlevanTem/Trade-Accumulated-Gold-CN)
[![L站佬友链接](https://img.shields.io/badge/L%E7%AB%99%E4%BD%AC%E5%8F%8B-linux.do-5865F2)](https://linux.do/)

[快速开始](#-快速开始) · [工作原理](#-工作原理) · [配置指南](#-配置指南) · [示例报告](#-效果展示)

<br>

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-打赏作者-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/bufan666)  
**作者微信**: `lelouchdbf` · 交流 / 定制 / 合作

</div>

> 当前监控默认采用「每模型六个自主账户」：短/中/长各有初始满仓和初始空仓账户，每户10万元，同轮统一决策。旧的概率门槛账户仅保留历史记录。运行细节见文末「六账户自主操盘与分析频率」。


---

## 🤔 你是否有这些困惑？

- 银行 APP 里的积存金价格，**到底该在哪个点位买入？**
- 看了一堆财经政治新闻，**消息到底是利多还是利空？**
- XAUUSD 涨了 $50，**传导到国内积存金，点位怎么选？**
- 刷手机看到金价在波动，**现在能不能入场？**

**这个 AI Skill 专门解决这些问题。** 一句话触发，30秒内快速生成多源验证完整分析报告。

---

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 🔴🟡🟢 **实时情绪判断** | 自动搜集最近1-4小时消息面，判定看好/看跌/中性，每条消息标注来源和影响 |
| 🧭 **三轴决策模型** | **AxisM**(消息) × **AxisL**(价位) × **AxisS**(信号) 综合给出方向；30m/1H 仅作「执行门控」过滤，避免被短线噪音带偏 |
| 🗣️ **金友圈社区共识** | 自动抓取京东金融 [@黄金小小彬] 个人页**最新一条**博主观点汇总，作为多博主共识参考；失败不阻塞主流程 |
| 📐 **精准点位计算** | 基于实时 OHLC 计算 R1/R2/R3 压力位、S1/S2/S3 支撑位、自定义轴心位 P |
| ⏱️ **多时间框架信号** | 直取 Investing.com 30min/1H/5H/日线/周线 5档信号，判断**当前能不能入场** |
| 💱 **积存金精准换算** | XAUUSD → 元/克，三级换算策略（银行实时报价 > SGE > 理论汇率），自动标注溢价并做溢出拦截 |
| 📊 **R:R 风险收益比** | 每笔交易强制计算止损/止盈，R:R ≥ 1.5:1 才推荐入场 |
| 🚨 **经济日历整合** | 自动读取当日已发布数据（ISM、非农、CPI 等），分析对金价的短期影响 |
| 📁 **报告自动归档** | 每次分析自动落盘 `.claude/skills/gold-analysis/assets/YYYY-MM-DD-HHmm-gold-analysis.md`，便于复盘回测 |

---

## 📸 效果展示

<details>

<summary>📄 点击展开报告分析示例</summary>

```
⚡ 黄金积存金实时短线分析
📅 2026-03-03 04:30 北京时间 | 数据时效: 实时（Investing.com 直取）

┌─────────────────────────────────────────┐
│  XAUUSD 现价  $5,336.34  (+1.11%)       │
│  Bid / Ask    $5,336.27 / $5,337.02     │
│  今日区间     $5,261.23 → $5,419.32     │
└─────────────────────────────────────────┘

⏱️ 多时间框架信号
  30分钟  🟢 买入      ← 短线动能转正！
  1小时   🟡 中性
  5小时   🟢 强烈买入
  日线    🟢 强烈买入
  周线    🟢 强烈买入

📐 关键点位（积存金换算）
  R2  $5,420  →  ~1,212 元/克  今日实际高点
  R1  $5,393  →  ~1,206 元/克  盘中阻力区
  ──────────────────────────────
  P   $5,340  →  ~1,194 元/克  轴心 (高+低)÷2
  ▶   $5,336  →  ~1,193 元/克  ← 当前价格
  ──────────────────────────────
  S1  $5,310  →  ~1,187 元/克  反弹起点支撑
  S2  $5,261  →  ~1,177 元/克  今日最低点

⚡ 能否入场？
  30min: 🟢 买入 → ✅ 可以准备入场（等轴心突破确认）

  方案A  轴心突破做多
  ├── 入场: $5,345-5,355  积存金 ≈ 1,196 元/克
  ├── 止损: $5,295        R:R = 1.5:1 ✅
  └── T1:   $5,419        积存金 ≈ 1,212 元/克
  
  方案B  回调低吸（更稳健）
  ├── 等待: 回调至 $5,305-5,315
  ├── 止损: $5,265        R:R = 2.2:1 ✅
  └── T1:   $5,393        积存金 ≈ 1,206 元/克
```

</details>


完整示例报告见 [.claude/skills/gold-analysis/assets/2026-04-19-1759-gold-analysis.md](.claude/skills/gold-analysis/assets/2026-04-19-1759-gold-analysis.md)。

报告结构对应 SKILL 阶段4 的强制落盘要求，包含：
- 顶部速览：**综合倾向（AxisM/L/S 三轴）** + **执行门控（30m/1H）** 两行核心结论
- 金友圈社区共识：3-8 条要点提炼 + 抓取时间戳 + content_id 溯源
- 完整点位表：XAUUSD 与浙商/民生积存金元/克双栏展示
- R:R 风险收益比验证 + 入场/止损/止盈三件套
- 数据来源：每条数据 Markdown 可点击 URL，抓取失败如实标注降级

---

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
git clone https://github.com/PlevanTem/Trade-Accumulated-Gold-CN.git \
  ~/.cursor/skills/Trade-Accumulated-Gold-CN

# 或：项目内安装（仅当前项目可见）
git clone https://github.com/PlevanTem/Trade-Accumulated-Gold-CN.git \
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
git clone https://github.com/PlevanTem/Trade-Accumulated-Gold-CN.git \
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
git clone https://github.com/PlevanTem/Trade-Accumulated-Gold-CN.git \
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
gemini skills install https://github.com/PlevanTem/Trade-Accumulated-Gold-CN.git \
  --path .claude/skills/gold-analysis
# 仅当前项目：
gemini skills install https://github.com/PlevanTem/Trade-Accumulated-Gold-CN.git \
  --scope workspace --path .claude/skills/gold-analysis

# 方式 2：手动 git clone 全仓库后，在 Gemini 侧用 link 指向技能目录（示例）：
# git clone https://github.com/PlevanTem/Trade-Accumulated-Gold-CN.git \
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

## 📡 实时监控程序（monitor/）

> 接下来的开发方向见 [docs/ROADMAP.md](docs/ROADMAP.md)。

基于本 skill 的常驻监控：每分钟取价，触及关键点位、30分钟异动、门控切换、进入低吸区时推送微信；同时运行**多策略模拟盘**，隔一段时间看哪种策略真正赚钱。**不会真实下单。**

| 策略 | 规则 | 交易频率 |
|---|---|---|
| 买入持有 `hold` | 基准：起始日全部买入，一直持有 | 1 次 |
| 中长线趋势 `position` | SMA200 上升趋势中按回撤分三批买；浮盈≥25% 且过热止盈 1/3；跌破 SMA200×97% 清仓 | 每年约 3 次 |
| AI 短线 `short_full` / `short_empty` | 每模型两户，分别初始满仓/空仓；AI 决定动作、数量、委托和保护价，定位数小时至3个交易日 | 价格变化、事件及兜底触发 |
| AI 中线 `medium_full` / `medium_empty` | 每模型两户，定位数日至数周，资金与其他周期独立 | 同轮六账户决策 |
| AI 长线 `long_full` / `long_empty` | 每模型两户，定位数周至数月，资金与其他周期独立 | 同轮六账户决策 |
| 规则短线 `short` | 三轴与门控，单笔10克，扣费后 R:R ≥1.5；T1减半、T2清仓 | 按行情检查 |

旧版 `position_ai` / `short_ai` 概率门槛账户不再参与默认实验；保留历史记录与已有持仓的风控。当前 AI 直接提交操作，概率只用于预测成绩评估。

- **AI 分析与操盘**（`monitor/ai.py`、`monitor/autonomous.py`）：Claude 与 Codex 串行运行，同批共享市场快照与基础提示，各自只接收自己的六账户状态，一次会话统一返回六份决策。Claude 可使用 API 或本机 Claude Code，Codex 使用本机 Codex CLI。模型可按预算补搜遗漏信息，默认最多2次；金十快讯由程序采集、筛选和去重。分析采用0.4%价格变化触发、4小时兜底及事件触发，每模型每天最多120轮；完整调度规则见文末。AI 自主账户按有效京东报价执行，不受旧版概率门槛限制。预测命中率和完整平仓交易胜率分别统计。

- 日线策略各有独立账户（默认本金各 10 万元），每个交易日 09:05 后按京东接口直取的积存金报价成交一次，卖出扣 0.4%
- 每天 9 点、20 点的计划摘要附战绩榜；**每周六 10 点推送模拟盘周报**；随时可用 `--stats` 查看
- 日线策略与回测共用同一份规则（`monitor/strategies.py`），`python3 -m monitor.backtest` 用 2010 年至今日线回测

> 回测（2011–2026，卖出手续费 0.4%）：买入持有 2.95×（最大回撤 44%）、每月定投 2.66×、中长线趋势 1.84×（最大回撤 23%）。趋势择时在 54 组参数下回撤全部更小、收益全部低于买入持有——它买的是「少亏」不是「多赚」。历史不代表未来。

- 技术面来自 TradingView 扫描接口（30m/1H/4H/日线/周线评级 + 指标，无需浏览器），CNBC 交叉核验并判断休市
- 模拟成交与净值估值统一使用京东 `latestPrice` 接口直取报价（通用产品报价，不标为浙商/民生专属盘口）；每轮取价，报价时间与抓取时间超过 120 秒则暂停成交。常驻监控不再启动银行 Chromium；支撑、压力价位按同一份京东报价校准换算。报价暂时失败时，前端保留上次有效报价估值并明确提示暂停成交。历史成交不重写，收益曲线按切换时间保留旧估值口径。
- 规则对照组的点位、轴心、三轴、门控、R:R 全部由 `scripts/gold_calc.py` 代码计算；**R:R 与模拟盘均按卖出手续费 0.4% 计算**
- 数据存 SQLite（`monitor/data/monitor.db`）

**低配机器调度**：两个 AI 在后台串行运行，同一轮使用相同的数据与分析轮次，轮换先后顺序；常驻监控直接读取京东接口、不运行银行 Chromium，行情监控继续运行。前端显示「正在分析 / 排队中」，第二个模型关闭后会跳过。整轮等待时间增加，但不再同时运行两个 AI CLI。

**双 AI 独立操盘**：默认15个账户：Claude、Codex各6个自主账户，每户10万元、每模型60万元；另有买入持有、规则中长线、规则短线三个对照组。短、中、长线各有初始满仓与初始空仓账户，资金不能互转。分批卖出合并到一个完整平仓周期，扣费后盈利才算胜。操盘对比显示收益、胜率、平仓样本、回撤、盈利因子及同起点基准增益；模型开账时间不同或尚未开始时明确提示比较限制。定投类已退出实时运行，历史回测保留。

**模型开关**：在 AI 页单独开启或关闭 Claude / Codex，无需重启；总览显示简短状态，操盘对比显示开启/暂停状态。关闭后停止该模型的分析和新开仓，撤销未成交委托；运行中的 CLI 会被取消，API 已发出请求返回后丢弃结果。已有持仓继续执行保护，历史判断和战绩保留。重新开启后先获取新判断；关闭前或取消运行的判断不会用于新开仓。未开账模型须开启、后端可用且京东报价有效后才初始化，重启不重复初始化。


**旧数据与升级**：新模型账户使用 `claude:策略` / `codex:策略` 独立身份，旧 AI 账户仅保留历史与已有持仓的风控，不再显示在主看板或参与新对比。普通定投、智能定投和两个模型的 AI 定投账户已备份后删除，旧配置也不会重新创建它们。第一次启动监控会自动新增表和字段，迁移不复制旧持仓。部署已有服务时先重启 `gold-monitor` 完成迁移，再重启 `gold-web`。模型开关与数据共存于 SQLite，备份数据库也会保留开关状态。网页行情读取仍只读；只有受登录保护的模型开关接口可以写控制状态。

离线验证（无真实行情抓取、AI 调用或推送）：`python3 -m unittest discover -s tests -v`。安装 Playwright 和 Chromium 后会同时运行桌面与手机网页集成检查。


```bash
cp .env.example .env          # 填 PUSHPLUS_TOKEN 或 SERVERCHAN_SENDKEY
python3 -m monitor --once     # 跑一轮看计划（不推送）
python3 -m monitor --stats    # 各策略模拟盘战绩
python3 -m monitor.backtest   # 历史回测（--trades 列出逐笔）

# 常驻（systemd）
cp deploy/gold-monitor.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now gold-monitor
journalctl -u gold-monitor -f # 看日志

# 网页看板（行情、AI 判断、独立操盘对比与模型开关）
cp deploy/gold-web.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now gold-web
# 默认只监听 127.0.0.1:8080；对外访问见 .env.example 中 GOLD_WEB_* 配置
```

---

## 🔧 工作原理

![workflow](Trade-Accumulated-Gold-CN.png)

```
用户触发
   │
   ▼
┌──────────────────────────────────────────────────────────┐
│  阶段1：消息面 + 金友圈社区共识                          │
│  ├── web_search: 地缘政治 / 美联储 / 央行购金 / DXY      │
│  ├── 京东金融个人页抓取 [@黄金小小彬] 最新观点           │
│  └── → 输出：🟢看好 / 🟡中性 / 🔴看跌 + 共识要点         │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│  阶段2：实时行情 + 技术分析（互斥降级）                  │
│  ├── STEP1: Python 脚本（XAUUSD + 浙商/民生银行报价）   │
│  ├── STEP2: JD latestPrice API 兜底                     │
│  ├── STEP3: 内置浏览器 MCP 直接读银行页面（最终兜底）   │
│  ├── 计算 R1/R2/R3、S1/S2/S3（5维共振法）               │
│  └── 计算轴心 P = (R1 + S1) ÷ 2，盘中再算 (高+低)/2     │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│  阶段3：三轴综合决策 + 积存金换算                        │
│  ├── AxisM(消息) × AxisL(价位) × AxisS(信号) → 偏多/空 │
│  ├── 30m/1H 作为「执行门控」过滤当下能否下单            │
│  ├── 三级换算：银行报价 > SGE Au99.99 > 理论汇率         │
│  └── 强制 R:R ≥ 1.5:1 + 溢价>30元/克 自动拦截           │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│  阶段4：结构化报告 + 自动归档                            │
│  ├── 顶部两行：综合倾向(三轴) + 执行门控(30m/1H)        │
│  ├── 完整点位表：XAUUSD + 积存金元/克 双栏展示           │
│  ├── 数据来源：URL 链接 + 抓取时间，全程可追溯           │
│  └── 落盘 .claude/skills/gold-analysis/assets/YYYY-MM-DD-HHmm-gold-analysis.md │
└──────────────────────────────────────────────────────────┘
```

---

## 💡 设计亮点

### 1. 实时优先，拒绝延时

传统分析工具往往使用小时前甚至天前的数据。本工具将 `WebFetch investing.com/currencies/xau-usd` 作为**第一步必须执行**的动作，单次请求同时获得：
- 实时 Bid/Ask 报价（精确到秒）
- 30min/1H/5H/日线/周线 全套技术信号
- 当日经济日历（已发布数据 vs 预期值）

### 2. 三轴决策 + 短线信号「门控化」

短线交易最容易犯的错误是：**只看 30min 指标定方向**。本工具把决策流程拆成两层：

- **方向层（三轴综合）**：`AxisM(消息+金友圈)` × `AxisL(现价 vs P/R1/S1)` × `AxisS(5H/日线 vs 30m/1H)`，三轴投票得出 **偏多/偏空/震荡**
- **执行层（短线门控）**：30min/1H 只回答「**当下时点是否适合下单**」，不回答方向

| 三轴综合 | 30m/1H 门控 | 行动 |
|----------|------------|------|
| 偏多 | 买入 | ✅ 可分批入场（须 R:R ≥ 1.5:1） |
| 偏多 | 卖出 | ⏳ **中期偏多但短线不追**，等回调至 S1/S2 + 门控转好 |
| 偏空 | 任意 | 🔻 逢高减仓为主，不抄底 |
| 震荡 | 任意 | 🔄 区间操作 / 观望 / 轻仓 |

> 这个设计专门解决 **「30min 红了就追多结果接在山顶」** 的常见亏损模式。

### 3. 积存金换算的 SGE 时间错位警告

上海黄金交易所 15:30 收盘，中国夜盘和美盘期间 SGE 数据已经"过期"。本工具会自动检测时间错位，若 XAUUSD 较 SGE 收盘后波动超过 $20，自动降级为理论换算并标注警告。

### 4. USD/CNY 大幅波动时的特殊处理

当美元指数 DXY 单日波动超过 0.5% 时（如美伊冲突导致美元和黄金同时上涨），工具会专门计算并说明：**国内积存金的实际涨幅可能显著不同于 XAUUSD 涨幅**。例如 2026-03-03：XAUUSD +1.11%，但 USD/CNY 同时涨 +1.37%，导致积存金实际涨幅达 **+2.48%**，远大于国际金价涨幅。

---

## 📁 文件结构

```
Trade-Accumulated-Gold-CN/
├── README.md                               # 本文档
├── Trade-Accumulated-Gold-CN.png          # 工作流程示意图（见「工作原理」）
├── requirements.txt                        # Python 依赖（requests / playwright / yfinance）
├── .env.example                            # 监控程序配置模板（推送 token、调参）
├── monitor/                                # 实时监控 + 模拟盘常驻程序（python3 -m monitor）
├── deploy/                                 # systemd 服务文件（gold-monitor 监控 / gold-web 网页看板）
├── .gitignore                              # 仅保留一份示例报告纳入版本库（见下）
└── .claude/
    └── skills/                             # 可并列多个技能子目录（本仓库默认提供 gold-analysis）
        └── gold-analysis/                  # 黄金积存金分析技能（Anthropic Skills 布局）
            ├── SKILL.md                    # AI Agent 核心指令（入口）
            ├── assets/
            │   └── 2026-04-19-1759-gold-analysis.md   # 示例输出报告（仓库跟踪的这一份）
            ├── references/
            │   ├── technical-analysis.md   # 技术分析指标详解（MA/BOLL/MACD/KDJ/RSI）
            │   ├── accumulation-gold.md    # 积存金产品知识与换算规则详解
            │   └── report-template.md      # 标准报告输出模板（含金友圈结构化呈现格式）
            └── scripts/
                ├── fetch_bank_quotes.py    # 浙商/民生银行积存金报价（Playwright + JD API 兜底）
                ├── fetch_jd_personal_latest_post.py  # 京东金融金友圈[黄金小小彬]最新观点抓取
                ├── live_market_data.py     # XAUUSD 实时价 + USD/CNY 汇率（与 fetch_bank_quotes.py 并行运行）
                ├── net_proxy.py            # 境外数据源共用代理配置（GOLD_TRADING_HTTP_PROXY）
                ├── gold_calc.py            # 确定性计算：换算/手续费/R:R/轴心/三轴/门控/点位
                ├── tv_signals.py           # TradingView 多时间框架信号（Investing.com 不可达时的备选）
                ├── macro_data.py           # 经济日历（硬事件判定）+ 美元指数/美债/离岸人民币
                ├── jin10_flash.py          # 金十数据快讯：抓取并筛出与金价相关条目（重要快讯触发 AI）
                └── ...                     # 其余 test_*.py 为各数据源探活脚本
```

---

## 🛠️ 配置指南

### 自定义银行（默认：浙商 + 民生）

编辑 `.claude/skills/gold-analysis/SKILL.md` 中的 `搜索B` 部分，替换为你使用的银行积存金产品名称：

```
优先搜索: "工商银行积存金 建设银行积存金 今日金价"
```

### 调整交易节奏

`.claude/skills/gold-analysis/SKILL.md` 顶部的核心定位部分可调整：

```markdown
- **交易节奏**: 小时/天级别短线，快进快出    ← 改为"日/周级别"可切换到中线分析
- **收益目标**: 通过多次高胜率操作复利积累    ← 可根据自身目标调整
```

### 调整 R:R 门槛

默认 R:R ≥ 1.5:1，可在 `阶段3` 中修改：

```
R:R = (目标收益) ÷ (止损距离) ≥ 1.5:1    ← 改为 2:1 更保守
```

---

## 🤝 致谢 & Contributing

L站佬友链接：https://linux.do/

1. **京东金融金友圈博主** — 黄金小小斌（博主信息观点每日聚合，方便寻找共识）、兰宫花匠（积存金点位分析方法论）
2. **技术指标优化** — 在 `.claude/skills/gold-analysis/references/technical-analysis.md` 中补充
3. **实战案例** — 分享你用本工具做出的成功/失败交易案例
4. **Bug 反馈** — 如遇到换算错误或点位明显偏差，欢迎提 Issue

---

## ⚠️ 免责声明

本工具及相关分析报告**仅供学习和参考目的**，不构成任何投资建议。黄金市场波动剧烈，积存金交易存在亏损风险。请在充分了解相关风险的前提下，结合自身财务状况和风险承受能力自主决策。

**作者不对任何因使用本工具导致的投资损失承担责任。**

---

## 📄 License

MIT License — 自由使用、修改、分发，保留原始版权声明即可。

---

<div align="center">

**如果这个工具对你有帮助，请给一个 ⭐ Star！**

你的 Star 是持续更新和优化的最大动力 🙏

## Star History

<a href="https://www.star-history.com/?repos=PlevanTem%2FTrade-Accumulated-Gold-CN&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=PlevanTem/Trade-Accumulated-Gold-CN&type=date&theme=dark&legend=top-left&sealed_token=gQGGWEietgIFhpeGR0xkn9wDjPzc-byjquLQ0a1TAWFylvDvkr29qaL28E-VzgKh-KohuDROIq7Fk8j4aJyP5sMnJBCdr2B0RnYsn5_3-Cni-eVSBN4u7_RMMm8EGY-0wjT3vrRuhXeFuyvUwbdDE1GrfaL-KKmq_c9kh0bdyAbC9xkoB9Y-5g7acSeU" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=PlevanTem/Trade-Accumulated-Gold-CN&type=date&legend=top-left&sealed_token=gQGGWEietgIFhpeGR0xkn9wDjPzc-byjquLQ0a1TAWFylvDvkr29qaL28E-VzgKh-KohuDROIq7Fk8j4aJyP5sMnJBCdr2B0RnYsn5_3-Cni-eVSBN4u7_RMMm8EGY-0wjT3vrRuhXeFuyvUwbdDE1GrfaL-KKmq_c9kh0bdyAbC9xkoB9Y-5g7acSeU" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=PlevanTem/Trade-Accumulated-Gold-CN&type=date&legend=top-left&sealed_token=gQGGWEietgIFhpeGR0xkn9wDjPzc-byjquLQ0a1TAWFylvDvkr29qaL28E-VzgKh-KohuDROIq7Fk8j4aJyP5sMnJBCdr2B0RnYsn5_3-Cni-eVSBN4u7_RMMm8EGY-0wjT3vrRuhXeFuyvUwbdDE1GrfaL-KKmq_c9kh0bdyAbC9xkoB9Y-5g7acSeU" />
 </picture>
</a>

</div>


### 监控数据与 AI 输入（2026-10-16）

| 数据 | 获取方式与频率 | 用途 |
|---|---|---|
| 京东通用积存金报价 | 原有匿名 API，每 60 秒；报价与抓取时间均须在 120 秒内 | 模拟成交及估值，失效时暂停成交 |
| XAU/USD、多周期信号、支撑阻力 | 原有 TradingView + CNBC，每 60 秒；程序计算点位 | 方向、技术与风控 |
| USD/CNY | 原有汇率接口，每 15 分钟 | 汇率参考 |
| 美元指数、美债收益率、离岸人民币 | 原有宏观行情接口，每 5 分钟 | 宏观判断 |
| 经济日历 | 平时每 30 分钟；美国重大/重要数据公布前 15 分钟至后 30 分钟，每 1 分钟 | 取得实际值和数据公布触发 |
| 黄金相关快讯 | 原有金十接口，每 120 秒；程序筛选去重 | AI 最多提供 12 条重要及 6 条普通快讯，每条最多 160 字 |
| 京东资金事件、挂单分布 | `gold-analysis-hub` 的结构化接口，仅 AI 分析触发时请求，每个接口缓存 15 分钟 | 最新资金事件、多空各三个挂单密集区，仅供研究参考 |
| 日线历史 | 原有按日缓存 | 日线策略和回测 |

后台不调用 `clawx-market-query` 的自然语言查询：股票、ETF 筛选对当前积存金实验没有必要；不常驻请求重复的机会评分、共振分析、银行报价或 GUI 看板。京东今日必读、专栏等暂不增加，现有快讯已覆盖主要消息需求。

采集、缓存、去重和计算由 Python 完成，不调用大模型。默认 `GOLD_AI_MAX_SEARCHES=2`，两个模型共用同一份精简市场 JSON 和基础提示，各自追加自己的六账户状态，串行独立分析；允许各自按需补搜遗漏的重要消息，不重复搜索程序已提供的数据，保留来源与日期。CLI 搜索次数由提示词约束，API 通过工具参数限制；搜索可能使模型看到不同外部资料，因此对比衡量的是各自完整研究与操盘表现。快讯触发仍由规则判断，不再额外调用 AI 初筛。设为 0 可关闭补搜。京东接口授权/额度遵循供应商规则，不保证免费无限调用。

京东密钥使用忽略提交的 `.env` 中 `CLAWX_JR_API_KEY`；不传入模型子进程或上下文。接口失败缓存 15 分钟；资金事件超过 24 小时、挂单超过 1 小时、宏观缓存超过 1 小时均标记不可用。挂单价格单位未明确，不能视为积存金成交盘口，也不自动换算成国际金价。

AI 页显示最近一次输入时间、快讯条数、上下文字符数、宏观缓存时间及京东接口状态；字符数不等于实际 Token 数。共同上下文按 `ai_input:<run_id>` 存档，京东原始公共响应保存在对应缓存中，便于复核。新数据供下一次正常触发使用，历史判断和账户不重置。

京东参考信息由 [京东金融有钳](https://youqian.jd.com/) 提供。

宏观行情与日历分别记录成功更新时间；单个接口失败保留原数据和原时间，前端分别显示，AI 不使用超过一小时的数据。提高采集频率不提高 AI 分析频率。

行情页按报价、价格走势、经济日历、快讯、宏观指标和京东黄金参考分组，显示独立更新时间与刷新异常。日历支持待公布/已公布/全部筛选（待公布不展示超过半小时的过往日程），快讯支持只看重要。京东资金和挂单只读已有缓存；页面刷新不额外取数或调用模型，过期统计不展示数值。AI 页的共同输入是历史批次记录，与行情页当前数据区分。


### AI 事件与计分时序修复（2026-10-16）

- 每个模型通过 SQLite 保存待处理事件；冷却期间、串行等待期间及分析失败后均保留。新事件合并进入下一批共同输入，分析成功与确认已覆盖事件在同一事务提交；只确认该批输入明确包含的事件。分析中途新增的事件留待下一批，模型关闭期间不调度分析，重新打开后仍先获取新判断。
- 美国重要数据须在取得有效数值型实际值后才加入队列，`0` 是有效值；仍保留原有公布后 10 分钟延迟。各指标按时间、国家、标题去重，同刻部分先公布、其余晚到时可分别补齐；最多补抓最近 24 小时结果。讲话等没有数值的日程不会因时间到达被当作数据结果，相关消息仍由快讯覆盖。
- `ai_views.snapshot_at / started_at / completed_at` 分别记录共同行情快照、各模型启动、完成时刻，判断有效期从行情快照计时。所有模型同批基础输入一致，启动和完成时刻分别记录。共同输入和事件覆盖清单随 `run_id` 存档。
- 新判断的预测成绩从完成之后 5 分钟内首个有效、开市监控现货价格起算；尚在等行情时为待定，超过窗口没有行情则记为缺数据，不回退到分析前价格。跨日周期从该起算行情确定，避免将模型分析期间的走势算成预测收益。起算价格、时刻和口径由成绩单 API 返回，可从原始 ticks 复核；旧判断仍使用原有口径，历史交易不重写。操盘收益继续按实际京东模拟成交记录计算。
- AI 页面显示行情快照/开始/完成时间及待覆盖事件数，不额外调用大模型。


### 六账户自主操盘与分析频率（2026-10-16）

默认 `GOLD_AI_TRADING_MODE=six_account`。每个模型各有下列六个独立模拟账户，每户本金10万元、合计60万元；两个模型共12个自主账户，另保留买入持有、趋势、短线三个规则对照。

| 周期 | 满仓起点 | 空仓起点 | 计划定位 |
|---|---|---|---|
| 短线 | short_full | short_empty | 数小时至3交易日 |
| 中线 | medium_full | medium_empty | 数日至数周 |
| 长线 | long_full | long_empty | 数周至数月 |

模型开启、后端可用且京东报价有效时，同一批初始化其六个账户，满仓起点一次性买满，空仓起点保留现金。尚未开账且关闭的模型暂不初始化，首次开启后按当时有效价格开账；已经开账的模型重新开启时沿用原账户。因此对比时应同时检查模型的开账时间。重启不会重复初始化。所有操作均为本地模拟，不接京东实盘交易。

每轮只抓取一份共同市场输入（含缓存日线5/20/60日趋势，标明期货代理口径），各模型只收到自己的六个账户：现金、黄金、成本、盈亏、版本、保护价、最新委托及最近成交。同一会话统一返回六份结构化决策。CLI 后端一次调用完成，API 后端通过结构化提交工具返回六份决策；服务端搜索暂停时可在原会话续接，不按账户分别调用模型。

AI 直接选择买、卖、持有、等待、撤单，以及金额/克数、市价/限价、止损、止盈、有效期和失效理由。概率保留作预测成绩评估，不再作为六账户买卖门槛。账户资金不能互转，不能借款、做空或超卖。新买入须有止损，默认成本价下12%为最宽硬止损触发线；AI 可以设得更紧，跳价时仍按实际有效京东报价成交。可主动撤销止盈目标，硬止损持续保留。委托最长24小时，到期只撤销未成交委托，持仓保护不随委托期限消失。

执行器每分钟检查有效京东报价、持仓保护和条件委托。成交、计划状态、账户版本、完整平仓周期与权益在同一事务更新。过期输入（默认15分钟）、账户版本变化、开关代际变化或不合法数量都会拒绝并记录原因；某账户拒绝不会阻止其他合法账户。拒绝与风控成交可合并触发后续分析。关闭模型撤销其未成交委托、停止新分析与新开仓，已有持仓继续保护。

| 分析来源 | 当前默认规则 |
|---|---|
| 工作日定时 | 北京时间08:40、20:45；附近已有判断则合并 |
| 周期复查 | 国际金价较上次成功判断时的输入变化≥0.4%即排队，无最小时间间隔 |
| 无明显变化兜底 | 距上次判断240分钟仍可排队复查 |
| 经济数据 | 美国重大/重要指标实际值到达，且超过公布后10分钟；最小间隔15分钟 |
| 快讯 | 原有严格规则、每天最多4批，最小间隔30分钟；原文放入本轮输入 |
| 价格异动 | 30分钟±0.6%，按原有提醒冷却与最小间隔合并 |
| 账户初始化/风控/拒绝 | 初始化请求首次分析；风控、拒绝按15分钟冷却合并 |
| 失败重试 | 等待30分钟，事件继续保留 |
| 全局预算 | 每模型北京时间每天最多120轮，其中最后2轮仅供重大消息/数据/风控；普通调用最多用到118轮 |

周期条件每个监控轮检查，达到波动条件即排队。中长线账户无变化时可简短持有，仍在同一轮返回六份结果。所有自动来源共用预算；成功、失败、中途取消均计入，旧版当天的调用也计入。达到上限后事件留在队列，到次日额度恢复后继续处理；已有委托和保护仍由程序检查。显式CLI手动强制分析可以越过自动预算，仍会记录实际调用次数。两个模型始终串行，轮换先后顺序。

前端账户页按模型、周期和初始仓位查看资产，AI 页集中显示当前保护价、决策与拒绝原因；操盘对比按六种相同起点配对。满仓的起点基准按各自开账报价持有不动，空仓基准为现金。完整平仓周期合并分批卖出后扣费计胜率。旧版概率账户不混入新实验，旧持仓仅保留原有风控。成交记录保留模型、批次、实际京东报价及具体决策，AI输入按批次分开存档共同市场与各模型账户。


### 分析频率配置

在仓库根目录 `.env` 设置以下参数；修改配置后重启 `gold-monitor` 与 `gold-web`。模型开关由网页写入数据库，不需要重启。

```dotenv
GOLD_AI_TRADING_MODE=six_account
GOLD_AI_SHORT_REVIEW_MINUTES=0
GOLD_AI_PERIODIC_MIN_MOVE_PCT=0.4
GOLD_AI_REVIEW_MAX_IDLE_MINUTES=240
GOLD_AI_MAX_RUNS_PER_DAY=120
GOLD_AI_URGENT_RESERVE=2
GOLD_AI_DECISION_MAX_AGE_MINUTES=15
GOLD_AI_HARD_STOP_LOSS=0.12
```

0.4%比较的是**各模型上一次成功分析时输入的国际金价 XAU/USD**，涨跌均取绝对值：`abs(当前价格 / 上次输入价格 - 1) × 100%`。例如上次为4000美元/盎司，达到4016或3984即满足波动条件。成交与账户估值仍使用京东积存金报价，不能用国际金价替代成交价。

`GOLD_AI_SHORT_REVIEW_MINUTES=0`表示没有最小分析间隔，负数关闭周期复查，正数设置最小间隔。程序每个监控轮检查条件并排队，不代表每分钟都调用模型；仍受串行运行、失败重试和每日预算约束。120轮是每模型每天的自动调用上限，普通来源最多118轮，最后2轮留给重大事件；不是计划每天固定调用120轮。无论是否触发 AI，程序仍每分钟检查有效报价、委托、止损和止盈。

### 网页看板与历史记录

| 页面 | 展示顺序与用途 |
|---|---|
| 总览 | 京东成交价及可用状态 → 模型运行与成绩摘要 → 最新操作/待成交委托 → 近期重要事件 |
| 账户 | 账户筛选 → 现金、持仓、成本、净值与收益 → 同步筛选的收益曲线；规则短线计划归入对照组 |
| 操盘对比 | 模型总成绩 → 六组同起点账户对比 → 组合曲线 → 比较口径与三个对照账户；标明开始时间、运行天数、平仓样本 |
| AI | 模型开关与运行状态 → 最新分析 → 六账户当前决策 → 折叠输入详情和预测准确度 → 分析历史入口 |
| 行情 | 报价 → 价格走势 → 经济日历 → 快讯 → 宏观指标 → 京东资金/挂单参考 |
| 操盘记录 | 默认实际成交，可切换 AI 决策、交易周期、分析历史、系统提醒；顶部筛选模型、时间与账户 |

模型开关只在 AI 页管理。资产明细集中在账户页，交易成绩集中在操盘对比页，完整成交和分析历史集中在操盘记录。已关闭模型的历史判断不参与当前一致/分歧提示。自动刷新只重绘当前页面发生变化的数据，保留详情展开状态、筛选和阅读位置；不额外调用模型或市场接口。

历史查询接口与网页使用相同登录保护：

```text
GET /api/history?kind=fills&model=codex&days=30&account=codex:short_empty&offset=0&limit=50
```

| 参数 | 支持值 |
|---|---|
| `kind` | `fills`实际成交、`plans`账户决策、`cycles`交易周期、`analysis`分析历史、`alerts`系统提醒 |
| `model` | `all`、`claude`、`codex`、`rules`对照账户 |
| `days` | `all`或正整数天数；网页提供24小时、7天、30天 |
| `account` | `all`或具体账户标识，如`codex:short_empty`；分析历史和系统提醒无需指定 |
| `offset` / `limit` | 起始偏移与页大小；默认0/50，页大小最多100 |

返回 `items`、`offset`、`limit`、`has_more`。模型、时间与账户筛选先作用于数据库，再分页，点击“加载更多”可继续查询完整历史。实际成交合并自主账户、日线对照和规则短线记录，显示价格、数量、金额、手续费及决策依据；AI 决策包含持有、观望、委托状态与拒绝原因；分析历史关联已到期的预测结果。预测命中率与交易胜率分别统计。

验证命令：`python3 -m unittest discover -s tests -v`。当前85项回归测试通过，涵盖六账户独立执行、调度预算、历史筛选与分页、预测结果及桌面/手机页面；浏览器测试需安装 Playwright 与 Chromium。
