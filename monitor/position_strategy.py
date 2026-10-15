"""中长线持仓策略（纯函数，回测与实盘监控共用同一份规则）。

思路：只在长期上升趋势里持有；趋势中按回撤深度分批买入（越跌越买），
高位过热时分批止盈，长期趋势破位时清仓离场。信号全部基于人民币金价日线
（已包含汇率影响），成本按银行规则：买入免费、卖出 0.4%。

一年交易几次到一个月几次，手续费占比很小。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import gold_calc as gc


@dataclass(frozen=True)
class PositionParams:
    sma_mid: int = 50
    sma_long: int = 200
    high_lookback: int = 60                                 # 回撤以近 60 日最高收盘价为基准
    pullbacks: Tuple[float, ...] = (0.03, 0.07, 0.12)       # 第 1/2/3 批买入的回撤深度
    trend_start_window: int = 5                             # SMA50 上穿 SMA200 后 5 日内可直接买第一批
    exit_buffer: float = 0.03                               # 收盘跌破 SMA200 × (1−3%) 清仓
    tp_gain: float = 0.25                                   # 浮盈 ≥25% 且
    tp_rsi: float = 75.0                                    # RSI14 > 75 时
    tp_fraction: float = 1 / 3                              # 止盈 1/3 仓位
    tp_min_gap_days: int = 20                               # 两次止盈至少间隔 20 个交易日
    sell_fee_rate: float = gc.SELL_FEE_RATE

    @property
    def tranches(self) -> int:
        return len(self.pullbacks)


@dataclass
class Indicators:
    sma_mid: List[Optional[float]]
    sma_long: List[Optional[float]]
    rolling_high: List[Optional[float]]
    rsi: List[Optional[float]]


def sma(values: Sequence[float], n: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= n:
            total -= values[i - n]
        if i >= n - 1:
            out[i] = total / n
    return out


def rolling_max(values: Sequence[float], n: int) -> List[Optional[float]]:
    return [max(values[i - n + 1:i + 1]) if i >= n - 1 else None for i in range(len(values))]


def rsi(values: Sequence[float], n: int = 14) -> List[Optional[float]]:
    """Wilder RSI。"""
    out: List[Optional[float]] = [None] * len(values)
    if len(values) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        delta = values[i] - values[i - 1]
        gains += max(delta, 0)
        losses += max(-delta, 0)
    avg_gain, avg_loss = gains / n, losses / n
    for i in range(n, len(values)):
        if i > n:
            delta = values[i] - values[i - 1]
            avg_gain = (avg_gain * (n - 1) + max(delta, 0)) / n
            avg_loss = (avg_loss * (n - 1) + max(-delta, 0)) / n
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def compute_indicators(closes: Sequence[float], p: PositionParams) -> Indicators:
    return Indicators(sma(closes, p.sma_mid), sma(closes, p.sma_long), rolling_max(closes, p.high_lookback), rsi(closes))


@dataclass
class PositionState:
    budget: float
    cash: float
    grams: float = 0.0
    cost: float = 0.0                  # 持仓总成本（元），平均成本 = cost / grams
    tranches_used: int = 0
    last_tp_index: int = -10 ** 9
    fees_paid: float = 0.0
    start_index: int = 0               # 账户起始日在日线序列中的位置（定投判断「首个交易日」用）

    @property
    def avg_cost(self) -> Optional[float]:
        return self.cost / self.grams if self.grams > 1e-9 else None


@dataclass
class Order:
    side: str            # buy / sell
    amount: float        # buy: 人民币金额；sell: 克数
    reason: str
    tranche: Optional[int] = None


def decide(i: int, closes: Sequence[float], ind: Indicators, state: PositionState, p: PositionParams) -> List[Order]:
    """用第 i 日收盘后的信息给出下一笔操作（回测在次日开盘成交，实盘在银行开盘后成交）。"""
    close, long_ma, mid_ma = closes[i], ind.sma_long[i], ind.sma_mid[i]
    if long_ma is None or mid_ma is None or ind.rolling_high[i] is None:
        return []

    if state.grams > 1e-9:
        if close < long_ma * (1 - p.exit_buffer):
            return [Order("sell", state.grams, f"趋势破位：收盘 {close:.1f} 跌破 SMA{p.sma_long}×{1 - p.exit_buffer:.0%}={long_ma * (1 - p.exit_buffer):.1f}")]
        avg = state.avg_cost
        r = ind.rsi[i]
        if (avg and close >= avg * (1 + p.tp_gain) and r is not None and r > p.tp_rsi
                and i - state.last_tp_index >= p.tp_min_gap_days):
            return [Order("sell", state.grams * p.tp_fraction,
                          f"高位止盈：浮盈 {close / avg - 1:.0%}、RSI {r:.0f}，卖出 {p.tp_fraction:.0%}")]

    uptrend = close > long_ma and mid_ma > long_ma
    if not uptrend or state.tranches_used >= p.tranches:
        return []
    k = state.tranches_used
    drawdown = 1 - close / ind.rolling_high[i]
    tranche_cash = min(state.budget / p.tranches, state.cash)
    if tranche_cash < 1:
        return []
    if drawdown >= p.pullbacks[k]:
        return [Order("buy", tranche_cash, f"第{k + 1}批：距 {p.high_lookback} 日高点回撤 {drawdown:.1%}（阈值 {p.pullbacks[k]:.0%}）", k + 1)]
    if k == 0:
        start = max(1, i - p.trend_start_window + 1)
        crossed = any(
            ind.sma_mid[j - 1] is not None and ind.sma_long[j - 1] is not None
            and ind.sma_mid[j - 1] <= ind.sma_long[j - 1] and ind.sma_mid[j] > ind.sma_long[j]
            for j in range(start, i + 1)
        )
        if crossed:
            return [Order("buy", tranche_cash, f"第1批：SMA{p.sma_mid} 上穿 SMA{p.sma_long}，长期趋势转多", 1)]
    return []


def apply_fill(state: PositionState, order: Order, price: float, i: int, p: PositionParams) -> float:
    """按成交价更新持仓；返回该笔手续费。卖出后释放一个批次额度，允许回调时再买回。"""
    if order.side == "buy":
        grams = order.amount / price
        state.cash -= order.amount
        state.grams += grams
        state.cost += order.amount
        state.tranches_used += 1
        return 0.0
    grams = min(order.amount, state.grams)
    proceeds = grams * price
    fee = proceeds * p.sell_fee_rate
    avg = state.avg_cost or 0.0
    state.cash += proceeds - fee
    state.cost -= avg * grams
    state.grams -= grams
    state.fees_paid += fee
    if state.grams <= 1e-9:
        state.grams, state.cost, state.tranches_used = 0.0, 0.0, 0
    else:
        state.tranches_used = max(0, state.tranches_used - 1)
        state.last_tp_index = i
    return fee
