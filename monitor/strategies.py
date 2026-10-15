"""日线级策略注册表：回测（backtest.py）与实盘模拟盘（accounts.py）共用同一份规则。

每个策略只实现 decide()：用第 i 日收盘后的信息返回订单；成交、记账、手续费由引擎统一处理。

AI 增强版（requires_ai=True）在同名基础策略上叠加 AI 消息面判断，只能「收紧」或「调节力度」，
不能推翻硬规则（趋势破位清仓、止盈照常执行）。它们无法做历史回测（没有可复现的历史新闻判断，
且模型知道历史结果），只能靠实盘模拟盘与对应的基础策略对比，看 AI 是否真的带来增益。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .position_strategy import (Indicators, Order, PositionParams, PositionState, compute_indicators,
                                decide as position_decide)


class DailyStrategy:
    key = ""
    name = ""
    description = ""
    horizon = "长期"          # 网页展示用：长期 / 中长线
    requires_ai = False

    def __init__(self, params: PositionParams):
        self.params = params

    def indicators(self, closes: Sequence[float]) -> Indicators:
        return compute_indicators(closes, self.params)

    def decide(self, i: int, days: Sequence, closes: Sequence[float], ind: Indicators,
               state: PositionState, view: Optional[Dict[str, Any]] = None) -> List[Order]:
        raise NotImplementedError


def first_trading_day_of_month(i: int, days: Sequence, start_index: int) -> bool:
    return i == start_index or days[i].month != days[i - 1].month


class BuyAndHold(DailyStrategy):
    key, name = "hold", "买入持有"
    description = "基准：起始日全部买入，一直持有"

    def decide(self, i, days, closes, ind, state, view=None):
        if state.cash >= 1 and state.grams <= 1e-9:
            return [Order("buy", state.cash, "起始日一次性买入")]
        return []


class MonthlyDCA(DailyStrategy):
    key, name = "dca", "每月定投"
    description = "基准：本金分 24 个月，每月第一个交易日等额买入，从不卖出"
    months = 24

    def decide(self, i, days, closes, ind, state, view=None):
        if state.cash < 1 or not first_trading_day_of_month(i, days, state.start_index):
            return []
        return [Order("buy", min(state.budget / self.months, state.cash), "每月定投")]


class SmartDCA(MonthlyDCA):
    key, name = "dca_smart", "智能定投"
    description = "每月定投；距 60 日高点回撤 ≥10% 时买 2 倍，RSI>75 过热时买半份；从不卖出"

    def decide(self, i, days, closes, ind, state, view=None):
        if state.cash < 1 or not first_trading_day_of_month(i, days, state.start_index):
            return []
        base = state.budget / self.months
        high, r = ind.rolling_high[i], ind.rsi[i]
        drawdown = 1 - closes[i] / high if high else 0.0
        if drawdown >= 0.10:
            mult, why = 2.0, f"回撤 {drawdown:.0%}，加倍定投"
        elif r is not None and r > 75:
            mult, why = 0.5, f"RSI {r:.0f} 过热，半份定投"
        else:
            mult, why = 1.0, "每月定投"
        return [Order("buy", min(base * mult, state.cash), why)]


class TrendPosition(DailyStrategy):
    key, name = "position", "中长线趋势"
    horizon = "中长线"
    description = "SMA200 上升趋势中按回撤 3%/7%/12% 分三批买；浮盈≥25% 且 RSI>75 止盈 1/3；跌破 SMA200×97% 清仓"

    def decide(self, i, days, closes, ind, state, view=None):
        return position_decide(i, closes, ind, state, self.params)


def ai_risk_off(view: Optional[Dict[str, Any]]) -> bool:
    """AI 中长期看空（置信中等以上）或 24 小时内有硬事件。"""
    if not view:
        return False
    return (view["bias_long"] == "bearish" and view["confidence"] in ("medium", "high")) or bool(view.get("hard_risk_event"))


class SmartDCAAI(SmartDCA):
    key, name = "dca_smart_ai", "智能定投+AI"
    description = "智能定投的金额再乘 AI 系数：中长期看多且高置信 ×1.5；看空(中/高置信) ×0.5；有硬事件 ×0.75；从不卖出"
    requires_ai = True

    def decide(self, i, days, closes, ind, state, view=None):
        orders = super().decide(i, days, closes, ind, state)
        if not orders or not view:
            return orders
        order = orders[0]
        factor, why = 1.0, "AI 中性"
        if view["bias_long"] == "bullish" and view["confidence"] == "high":
            factor, why = 1.5, "AI 中长期看多(高置信)"
        elif view["bias_long"] == "bearish" and view["confidence"] in ("medium", "high"):
            factor, why = 0.5, f"AI 中长期看空({view['confidence']})"
        elif view.get("hard_risk_event"):
            factor, why = 0.75, "AI 提示 24h 内硬事件"
        order.amount = min(order.amount * factor, state.cash)
        order.reason = f"{order.reason}；{why} ×{factor:g}"
        return orders


class TrendPositionAI(TrendPosition):
    key, name = "position_ai", "中长线趋势+AI"
    description = "中长线趋势规则不变；AI 看空(中/高置信)或有硬事件时暂停加仓；AI 高置信看空时持仓减半（间隔≥20日）"
    requires_ai = True
    ai_reduce_gap_days = 20

    def decide(self, i, days, closes, ind, state, view=None):
        orders = super().decide(i, days, closes, ind, state)
        if any(o.side == "sell" for o in orders):
            return orders                         # 硬规则卖出永远优先
        if orders and ai_risk_off(view):
            return []                             # AI 风险偏空：本次不加仓
        if (view and state.grams > 1e-9 and view["bias_long"] == "bearish" and view["confidence"] == "high"
                and i - state.last_tp_index >= self.ai_reduce_gap_days):
            return [Order("sell", state.grams / 2, f"AI 中长期高置信看空：减仓一半（{view['summary'][:40]}…）")]
        return orders


REGISTRY: Dict[str, type] = {cls.key: cls for cls in
                             (BuyAndHold, MonthlyDCA, SmartDCA, TrendPosition, SmartDCAAI, TrendPositionAI)}
BACKTESTABLE = [k for k, cls in REGISTRY.items() if not cls.requires_ai]


def build(keys: Sequence[str], params: PositionParams) -> List[DailyStrategy]:
    return [REGISTRY[k](params) for k in keys if k in REGISTRY]
