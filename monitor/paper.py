"""模拟盘：按交易计划在入场区虚拟买入，止损/目标在入场时冻结。

成本模型（与银行交易规则一致）：按银行报价（换算估值）买入、买入 0 手续费；
卖出到手 = 卖出价 × (1 − 卖出手续费率) − 价差，与 gold_calc.risk_reward_long 口径一致。T1 平一半并把止损移到保本卖价（含手续费），T2 平剩余。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

import gold_calc as gc

from .config import BANK_NAMES, Settings
from .store import Store, iso, utc_now


class PaperBook:
    def __init__(self, settings: Settings, store: Store, strategy: str = "short", label: str = "短线日内"):
        self.settings = settings
        self.store = store
        self.bank = settings.paper_bank
        self.strategy = strategy
        self.label = label

    def on_tick(self, snap: Dict[str, Any], plan: Dict[str, Any]) -> List[Dict[str, str]]:
        price = (snap.get("bank_est") or {}).get(self.bank)
        if price is None or not snap.get("market_open"):
            return []
        trade = self.store.open_trade(self.bank, self.strategy)
        if trade is not None:
            if plan.get("force_exit"):   # AI 主导账户：AI 看跌时提前离场
                return self._exit_now(trade, price, "AI 看跌离场")
            return self._manage(trade, price)
        return self._maybe_open(snap, plan, price)

    # ── 开仓 ─────────────────────────────────────────────────────────────
    def _maybe_open(self, snap: Dict[str, Any], plan: Dict[str, Any], price: float) -> List[Dict[str, str]]:
        buy = plan.get("buy") if plan.get("ok") else None
        if not plan.get("ok") or plan.get("action") != "buy_on_dip" or not buy or not buy.get("valid") or "zone_cny" not in buy:
            return []
        if plan.get("ratio_bank") != self.bank or (plan["gate"] == "block" and not plan.get("ignore_gate")):
            return []
        low, high = buy["zone_cny"]
        if not (low <= price <= high):
            return []
        last = self.store.last_closed_trade(self.bank, self.strategy)
        if last is not None and last["closed_at"]:
            closed_at = datetime.fromisoformat(last["closed_at"])
            if utc_now() - closed_at < timedelta(minutes=self.settings.reentry_cooldown_minutes):
                return []

        # 原版：门控矛盾时半仓；AI 主导：按 AI 把握大小 0.5~1.5 倍
        grams = self.settings.paper_grams * plan.get("size_mult", 1.0) * (
            0.5 if plan["gate"] == "light" and not plan.get("ignore_gate") else 1.0)
        self.store.insert_trade(
            bank=self.bank, strategy=self.strategy, status="open", opened_at=iso(utc_now()), entry_usd=snap["xauusd"],
            entry_cny=price, grams=grams, open_grams=grams,
            stop_cny=buy["stop_cny"], t1_cny=buy["t1_cny"], t2_cny=buy["t2_cny"] or buy["t1_cny"],
            plan_json=json.dumps(plan, ensure_ascii=False, default=str),
        )
        name = BANK_NAMES[self.bank]
        return [{
            "key": f"paper:{self.strategy}:open:{iso(utc_now())}",
            "title": f"📗[{self.label}]模拟买入 {price:.2f}",
            "body": (f"**模拟买入** {name} {grams:g} 克 @ {price:.2f} 元/克（XAUUSD {snap['xauusd']:.2f}）\n\n"
                     f"- 止损 {buy['stop_cny']:.2f} ｜ T1 {buy['t1_cny']:.2f} ｜ T2 {(buy['t2_cny'] or buy['t1_cny']):.2f}\n"
                     f"- 保本价 {buy['breakeven_cny']:.2f}（卖出手续费 {self.settings.sell_fee_rate:.1%}）｜ R:R {buy['rr1']:.2f} ｜ 门控：{plan['gate_text']}\n"
                     f"- 依据：{plan['summary']}"),
        }]

    # ── 持仓管理 ─────────────────────────────────────────────────────────
    def _exit_now(self, trade, price: float, reason: str) -> List[Dict[str, str]]:
        per_gram = gc.net_sell_proceeds(price, self.settings.sell_fee_rate, self.settings.spread_cny) - trade["entry_cny"]
        realized = trade["realized_cny"] + per_gram * trade["open_grams"]
        self._close(trade["id"], realized, reason)
        return [self._close_event(trade, price, realized, reason, BANK_NAMES[self.bank])]

    def _manage(self, trade, price: float) -> List[Dict[str, str]]:
        name = BANK_NAMES[self.bank]
        per_gram = gc.net_sell_proceeds(price, self.settings.sell_fee_rate, self.settings.spread_cny) - trade["entry_cny"]
        events: List[Dict[str, str]] = []

        if price <= trade["stop_cny"]:
            realized = trade["realized_cny"] + per_gram * trade["open_grams"]
            reason = "保本止损" if trade["t1_hit"] else "止损"
            self._close(trade["id"], realized, reason)
            events.append(self._close_event(trade, price, realized, reason, name))
        elif not trade["t1_hit"] and price >= trade["t1_cny"]:
            half = trade["open_grams"] / 2
            realized = trade["realized_cny"] + per_gram * half
            breakeven = round(gc.breakeven_price(trade["entry_cny"], self.settings.sell_fee_rate, self.settings.spread_cny), 2)
            self.store.update_trade(trade["id"], t1_hit=1, open_grams=trade["open_grams"] - half,
                                    realized_cny=realized, stop_cny=breakeven)
            events.append({
                "key": f"paper:{self.strategy}:t1:{trade['id']}",
                "title": f"📘[{self.label}]T1止盈 {price:.2f}",
                "body": (f"**T1 到达**，平一半 {half:g} 克 @ {price:.2f}，本笔已实现 {realized:+.2f} 元；"
                         f"剩余止损上移到保本卖价 {breakeven:.2f}（含手续费），等 T2 {trade['t2_cny']:.2f}"),
            })
        elif trade["t1_hit"] and price >= trade["t2_cny"]:
            realized = trade["realized_cny"] + per_gram * trade["open_grams"]
            self._close(trade["id"], realized, "T2止盈")
            events.append(self._close_event(trade, price, realized, "T2止盈", name))
        return events

    def _close(self, trade_id: int, realized: float, reason: str) -> None:
        self.store.update_trade(trade_id, status="closed", open_grams=0, closed_at=iso(utc_now()),
                                realized_cny=round(realized, 2), close_reason=reason)

    def _close_event(self, trade, price: float, realized: float, reason: str, name: str) -> Dict[str, str]:
        stats = self.store.trade_stats(self.bank, self.strategy)
        win_rate = f"{stats['win_rate']:.0%}" if stats["win_rate"] is not None else "—"
        return {
            "key": f"paper:{self.strategy}:close:{trade['id']}",
            "title": f"📕[{self.label}]平仓 {reason}",
            "body": (f"**{reason}** 平仓 @ {price:.2f}，本笔 {realized:+.2f} 元（入场 {trade['entry_cny']:.2f}）\n\n"
                     f"累计：{stats['trades']} 笔，胜率 {win_rate}，总盈亏 {stats['total_pnl_cny']:+.2f} 元"),
        }
