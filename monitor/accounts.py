"""多策略模拟盘：每个日线策略一个独立账户，每个交易日 09:05（北京时间）后运行一次。

- 决策：用截至上一个已收盘纽约交易日的日线（与回测同一份 strategies.decide）
- 成交：按当时银行实时价（换算估值）成交；买入免费，卖出扣手续费
- 每天记录一次净值，用于收益、回撤统计
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from .config import BANK_NAMES, BJ, Settings
from .history import History
from .position_strategy import PositionParams, PositionState, apply_fill
from .store import Store, iso, utc_now
from .strategies import AIConfig, DailyStrategy, build

log = logging.getLogger("monitor.accounts")

NY = ZoneInfo("America/New_York")
RUN_AFTER_BJ = (9, 5)            # 银行 9:00 开市后运行
HISTORY_RETRY_MINUTES = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    strategy TEXT PRIMARY KEY, name TEXT, budget REAL, started_at TEXT, state_json TEXT, last_run_day TEXT
);
CREATE TABLE IF NOT EXISTS account_fills (
    strategy TEXT, ts TEXT, side TEXT, grams REAL, price REAL, fee REAL, reason TEXT
);
CREATE TABLE IF NOT EXISTS account_equity (
    strategy TEXT, day TEXT, value REAL, price REAL, grams REAL, cash REAL, PRIMARY KEY (strategy, day)
);
"""


def last_completed_ny_day(now: datetime) -> date:
    """纽约时间 17:00 收盘后当日日线才算完成。"""
    ny = now.astimezone(NY)
    return ny.date() if ny.hour >= 17 else ny.date() - timedelta(days=1)


class Accounts:
    def __init__(self, settings: Settings, store: Store, strategy_keys: List[str]):
        self.settings = settings
        self.store = store
        self.history = History(store)
        self.params = PositionParams(sell_fee_rate=settings.sell_fee_rate)
        ai_cfg = AIConfig(long_buy_edge=settings.ai_long_buy_edge, long_reduce_edge=settings.ai_long_reduce_edge,
                          long_exit_edge=settings.ai_long_exit_edge, long_stop_loss=settings.ai_long_stop_loss,
                          dca_max_mult=settings.ai_dca_max_mult)
        self.strategies: List[DailyStrategy] = build(strategy_keys, self.params, ai_cfg)
        self.bank = settings.paper_bank
        self._history_failed_at: Optional[datetime] = None
        store.conn.executescript(SCHEMA)
        store.conn.commit()
        for st in self.strategies:
            store.conn.execute(
                "INSERT OR IGNORE INTO accounts VALUES (?,?,?,?,?,?)",
                (st.key, st.name, settings.account_budget, iso(utc_now()),
                 json.dumps(asdict(PositionState(budget=settings.account_budget, cash=settings.account_budget,
                                                 start_index=-1))), None),
            )
            store.conn.execute("UPDATE accounts SET name=? WHERE strategy=?", (st.name, st.key))   # 策略改名时同步
        store.conn.commit()

    # ── 状态读写 ─────────────────────────────────────────────────────────
    def _load(self, key: str) -> PositionState:
        row = self.store.conn.execute("SELECT state_json FROM accounts WHERE strategy=?", (key,)).fetchone()
        return PositionState(**json.loads(row["state_json"]))

    def _save(self, key: str, state: PositionState, run_day: Optional[str] = None) -> None:
        if run_day:
            self.store.conn.execute("UPDATE accounts SET state_json=?, last_run_day=? WHERE strategy=?",
                                    (json.dumps(asdict(state)), run_day, key))
        else:
            self.store.conn.execute("UPDATE accounts SET state_json=? WHERE strategy=?", (json.dumps(asdict(state)), key))
        self.store.conn.commit()

    # ── 每日运行 ─────────────────────────────────────────────────────────
    def due(self, now_bj: datetime) -> bool:
        if now_bj.weekday() >= 5 or (now_bj.hour, now_bj.minute) < RUN_AFTER_BJ:
            return False
        today = now_bj.date().isoformat()
        rows = self.store.conn.execute("SELECT last_run_day FROM accounts").fetchall()
        return any(r["last_run_day"] != today for r in rows)

    def run_daily(self, snap: Dict[str, Any], view: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        now_bj = datetime.now(BJ)
        price = (snap.get("bank_est") or {}).get(self.bank)
        if not snap.get("market_open") or price is None or not self.due(now_bj):
            return []
        if self._history_failed_at and utc_now() - self._history_failed_at < timedelta(minutes=HISTORY_RETRY_MINUTES):
            return []
        try:
            self.history.refresh_if_stale()
        except Exception as exc:
            self._history_failed_at = utc_now()
            log.warning("历史日线刷新失败，%s 分钟后重试: %s", HISTORY_RETRY_MINUTES, exc)
            return []

        cutoff = last_completed_ny_day(utc_now())
        bars = [b for b in self.history.bars() if b.day <= cutoff]
        if len(bars) < self.params.sma_long + 5:
            log.warning("历史日线不足，跳过")
            return []
        closes = [b.close for b in bars]
        days = [b.day for b in bars]
        i = len(bars) - 1
        today = now_bj.date().isoformat()
        events: List[Dict[str, str]] = []

        for st in self.strategies:
            row = self.store.conn.execute("SELECT last_run_day FROM accounts WHERE strategy=?", (st.key,)).fetchone()
            if row["last_run_day"] == today:
                continue
            state = self._load(st.key)
            if st.requires_ai and view is None and state.start_index < 0:
                continue                         # AI 账户等第一次 AI 判断出来再开账，保证全程有 AI 参与
            if state.start_index < 0:
                state.start_index = i            # 账户从今天开始：今天就是「首个交易日」
                self.store.conn.execute("UPDATE accounts SET started_at=? WHERE strategy=?", (iso(utc_now()), st.key))
            for order in st.decide(i, days, closes, st.indicators(closes), state, view if st.requires_ai else None):
                if st.requires_ai and view is None:
                    order.reason += "（今日 AI 判断缺失，按基础规则）"
                grams_before = state.grams
                fee = apply_fill(state, order, price, i, self.params)
                grams = order.amount / price if order.side == "buy" else min(order.amount, grams_before)
                self.store.conn.execute("INSERT INTO account_fills VALUES (?,?,?,?,?,?,?)",
                                        (st.key, iso(utc_now()), order.side, grams, price, fee, order.reason))
                verb = "买入" if order.side == "buy" else "卖出"
                events.append({
                    "key": f"acct:{st.key}:{today}:{order.side}",
                    "title": f"📒[{st.name}]模拟{verb} {grams:.2f}克",
                    "body": (f"**[{st.name}] 模拟{verb}** {grams:.2f} 克 @ {price:.2f} 元/克"
                             f"{f'，手续费 {fee:.2f} 元' if fee else ''}\n\n- 原因：{order.reason}\n"
                             f"- 账户：持仓 {state.grams:.2f} 克，现金 {state.cash:,.0f} 元"),
                })
            self._save(st.key, state, run_day=today)
            self.record_equity(st.key, state, price, today)
        self.store.conn.commit()
        return events

    def record_equity(self, key: str, state: PositionState, price: float, day: str) -> None:
        value = state.cash + state.grams * price * (1 - self.params.sell_fee_rate)   # 按「现在全卖」计净值
        self.store.conn.execute("INSERT OR REPLACE INTO account_equity VALUES (?,?,?,?,?,?)",
                                (key, day, value, price, state.grams, state.cash))
        self.store.conn.commit()

    # ── 战绩 ─────────────────────────────────────────────────────────────
    def leaderboard(self, price: Optional[float]) -> List[Dict[str, Any]]:
        board = []
        for st in self.strategies:
            acct = self.store.conn.execute("SELECT * FROM accounts WHERE strategy=?", (st.key,)).fetchone()
            state = self._load(st.key)
            values = [r["value"] for r in self.store.conn.execute(
                "SELECT value FROM account_equity WHERE strategy=? ORDER BY day", (st.key,)).fetchall()]
            value = state.cash + state.grams * price * (1 - self.params.sell_fee_rate) if price else (values[-1] if values else state.cash)
            peak, mdd = 0.0, 0.0
            for v in values + [value]:
                peak = max(peak, v)
                mdd = max(mdd, 1 - v / peak) if peak else mdd
            fills = self.store.conn.execute("SELECT COUNT(*) c, COALESCE(SUM(fee),0) f FROM account_fills WHERE strategy=?",
                                            (st.key,)).fetchone()
            board.append({
                "key": st.key, "name": st.name, "description": st.description,
                "started_flag": state.start_index >= 0, "requires_ai": st.requires_ai,
                "started": acct["started_at"][:10], "budget": acct["budget"], "value": value,
                "return": value / acct["budget"] - 1, "max_drawdown": mdd,
                "grams": state.grams, "cash": state.cash, "avg_cost": state.avg_cost,
                "invested": acct["budget"] - state.cash if state.grams > 1e-9 else 0.0,
                "fills": fills["c"], "fees": fills["f"],
            })
        return sorted(board, key=lambda b: (not b["started_flag"], -b["return"]))


def format_leaderboard(board: List[Dict[str, Any]], price: Optional[float], short_stats: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
    lines = [f"**模拟盘战绩**（按「现在全部卖出」扣 0.4% 计；现价 {price:.2f} 元/克）" if price else "**模拟盘战绩**",
             "", "| 策略 | 收益率 | 净值(元) | 最大回撤 | 持仓(克) | 成本 | 成交 | 手续费 |", "|---|---|---|---|---|---|---|---|"]
    for b in board:
        if not b["started_flag"]:
            lines.append(f"| {b['name']} | 未开始（{'等待 AI 启用' if b['requires_ai'] else '等待首个交易日'}） | — | — | — | — | — | — |")
            continue
        cost = f"{b['avg_cost']:.1f}" if b["avg_cost"] else "—"
        lines.append(f"| {b['name']} | {b['return']:+.2%} | {b['value']:,.0f} | {b['max_drawdown']:.1%} | "
                     f"{b['grams']:.1f} | {cost} | {b['fills']} | {b['fees']:.0f} |")
    if board:
        started = [b["started"] for b in board if b["started_flag"]]
        lines.append(f"\n各账户本金 {board[0]['budget']:,.0f} 元" + (f"，最早起始 {min(started)}" if started else ""))
    for label, st in (short_stats or {}).items():
        wr = f"{st['win_rate']:.0%}" if st["win_rate"] is not None else "—"
        lines.append(f"\n**{label}**（每笔 10 克，单独统计）：{st['trades']} 笔，胜率 {wr}，累计 {st['total_pnl_cny']:+.2f} 元")
    return "\n".join(lines)
