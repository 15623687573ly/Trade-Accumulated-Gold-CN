"""日线级策略注册表：回测（backtest.py）与实盘模拟盘（accounts.py）共用同一份规则。

每个策略只实现 decide()：用第 i 日收盘后的信息返回订单；成交、记账、手续费由引擎统一处理。

AI 版（requires_ai=True）由 AI 的概率判断主导方向（建仓、加减仓、清仓、定投力度），
规则只负责风控（止损、止盈、仓位上限）。它们无法做历史回测（没有可复现的历史新闻判断，
且模型知道历史结果），只能靠实盘模拟盘与对应的基础策略对比，看 AI 是否真的带来增益。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .position_strategy import (Indicators, Order, PositionParams, PositionState, compute_indicators,
                                decide as position_decide)


class DailyStrategy:
    key = ""
    name = ""
    description = ""
    horizon = "长期"          # 网页展示用：长期 / 中长线
    requires_ai = False

    def __init__(self, params: PositionParams, ai: Optional["AIConfig"] = None):
        self.params = params
        self.ai = ai or AIConfig()

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


@dataclass(frozen=True)
class AIConfig:
    """AI 主导账户的阈值（来自 .env，见 config.Settings）。"""
    long_buy_edge: float = 0.10
    long_reduce_edge: float = -0.10
    long_exit_edge: float = -0.25
    long_stop_loss: float = 0.12
    dca_max_mult: float = 2.5


def _long_edge(view: Optional[Dict[str, Any]]) -> Optional[float]:
    from .ai import long_edge
    return long_edge(view)


class SmartDCAAI(MonthlyDCA):
    key, name = "dca_smart_ai", "AI 定投"
    description = "每月定投金额 = 基础额 × AI 系数（0~2.5 倍，由 AI 对未来 3 个月涨跌概率之差决定）；从不卖出"
    requires_ai = True

    def decide(self, i, days, closes, ind, state, view=None):
        if state.cash < 1 or not first_trading_day_of_month(i, days, state.start_index):
            return []
        base = state.budget / self.months
        edge = _long_edge(view)
        if edge is None:
            return [Order("buy", min(base, state.cash), "每月定投；AI 判断缺失，按 1 倍")]
        mult = min(max(1 + 3 * edge, 0.0), self.ai.dca_max_mult)
        if mult < 0.05:
            return []
        return [Order("buy", min(base * mult, state.cash), f"AI 定投：3 个月涨跌概率差 {edge:+.0%} → ×{mult:.2f}")]


class TrendPositionAI(TrendPosition):
    key, name = "position_ai", "AI 中长线"
    description = ("AI 主导：3 个月涨跌概率差 ≥+10% 建仓（第 1 批立即，之后回撤 7%/12% 加仓，批量随把握 0.5~1.5 倍）；"
                   "≤−10% 减仓一半，≤−25% 清仓。风控：亏损超 12% 清仓、浮盈≥25% 且 RSI>75 止盈 1/3")
    requires_ai = True
    gap_days = 20

    def decide(self, i, days, closes, ind, state, view=None):
        p, cfg, close = self.params, self.ai, closes[i]
        avg = state.avg_cost
        if state.grams > 1e-9 and avg:
            if close <= avg * (1 - cfg.long_stop_loss):          # 风控优先，与 AI 无关
                return [Order("sell", state.grams, f"风控止损：亏损超过 {cfg.long_stop_loss:.0%}")]
            r = ind.rsi[i]
            if close >= avg * (1 + p.tp_gain) and r is not None and r > p.tp_rsi and i - state.last_tp_index >= p.tp_min_gap_days:
                return [Order("sell", state.grams * p.tp_fraction, f"止盈：浮盈 {close / avg - 1:.0%}、RSI {r:.0f}")]
        edge = _long_edge(view)
        if edge is None:
            return []                                              # AI 缺失：不开新仓，持仓继续受风控保护
        if state.grams > 1e-9:
            if edge <= cfg.long_exit_edge:
                return [Order("sell", state.grams, f"AI 看跌清仓：3 个月涨跌概率差 {edge:+.0%}")]
            if edge <= cfg.long_reduce_edge and i - state.last_tp_index >= self.gap_days:
                return [Order("sell", state.grams / 2, f"AI 看跌减半：3 个月涨跌概率差 {edge:+.0%}")]
        if edge < cfg.long_buy_edge or state.tranches_used >= p.tranches or state.cash < 1:
            return []
        k = state.tranches_used
        high = ind.rolling_high[i]
        drawdown = 1 - close / high if high else 0.0
        if k > 0 and drawdown < p.pullbacks[k]:
            return []
        size = min(max(edge / 0.3, 0.5), 1.5)
        amount = min(state.budget / p.tranches * size, state.cash)
        why = "AI 看涨建仓" if k == 0 else f"回撤 {drawdown:.1%} 加仓"
        return [Order("buy", amount, f"第{k + 1}批 {why}：3 个月涨跌概率差 {edge:+.0%}，×{size:.2f}", k + 1)]


REGISTRY: Dict[str, type] = {cls.key: cls for cls in
                             (BuyAndHold, MonthlyDCA, SmartDCA, TrendPosition, SmartDCAAI, TrendPositionAI)}
BACKTESTABLE = [k for k, cls in REGISTRY.items() if not cls.requires_ai]

# Separate identities without duplicating the trading rules or changing legacy accounts.
for _model in ("claude", "codex"):
    for _base in (SmartDCAAI, TrendPositionAI):
        _key = f"{_model}:{_base.key}"
        REGISTRY[_key] = type(f"{_model}_{_base.__name__}", (_base,),
                              {"key": _key, "name": f"{_model.title()} · {_base.name}", "analyst": _model})


def build(keys: Sequence[str], params: PositionParams, ai: Optional[AIConfig] = None) -> List[DailyStrategy]:
    return [REGISTRY[k](params, ai) for k in keys if k in REGISTRY]
