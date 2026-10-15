"""中长线策略历史回测（人民币金价口径，卖出手续费 0.4%）。

  python3 -m monitor.backtest                  所有注册策略 + 分阶段 + 中长线参数稳健性
  python3 -m monitor.backtest --trades         另外列出中长线趋势策略的每笔成交
  python3 -m monitor.backtest --start 2015-01-01 --end 2020-12-31

成交模型：第 i 日收盘出信号，第 i+1 日开盘价成交；买入免费，卖出扣手续费；
闲置现金不计利息；期末按收盘价扣手续费折现，便于与对照组公平比较。
局限：GC=F 为期货价；国内价为理论换算，未含国内溢价；历史不代表未来。
"""

from __future__ import annotations

import argparse
import itertools
import statistics
import sys
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Dict, List, Optional, Sequence

from .config import Settings  # noqa: F401  先导入：把 skill scripts 加入 sys.path

from net_proxy import apply_proxy

from .history import Bar, History
from .position_strategy import Order, PositionParams, PositionState, apply_fill
from .strategies import BACKTESTABLE, DailyStrategy, TrendPosition, build
from .store import Store

BUDGET = 100_000.0


@dataclass
class Result:
    name: str
    start: date
    end: date
    final_value: float
    max_drawdown: float
    fills: int = 0
    fees: float = 0.0
    exposure: float = 1.0
    trades: List[Dict] = field(default_factory=list)

    @property
    def years(self) -> float:
        return max((self.end - self.start).days / 365.25, 1e-9)

    @property
    def multiple(self) -> float:
        return self.final_value / BUDGET

    @property
    def cagr(self) -> float:
        return self.multiple ** (1 / self.years) - 1


def max_drawdown(equity: Sequence[float]) -> float:
    peak, worst = 0.0, 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, 1 - v / peak)
    return worst


def start_index(bars: Sequence[Bar], start: date) -> int:
    return next(i for i, b in enumerate(bars) if b.day >= start)


def simulate(strategy: DailyStrategy, bars: Sequence[Bar], start: date, end: date) -> Result:
    """通用引擎：第 i 日收盘出信号 → 第 i+1 日开盘成交；期末按收盘价扣卖出手续费折现。"""
    p = strategy.params
    closes = [b.close for b in bars]
    days = [b.day for b in bars]
    ind = strategy.indicators(closes)            # 用起点之前的数据预热指标
    s = start_index(bars, start)
    e = max(i for i, b in enumerate(bars) if b.day <= end)
    state = PositionState(budget=BUDGET, cash=BUDGET, start_index=s)
    equity: List[float] = []
    trades: List[Dict] = []
    pending: List[Order] = []
    invested_days = 0
    for i in range(s, e + 1):
        for order in pending:
            price = bars[i].open
            grams_before = state.grams
            fee = apply_fill(state, order, price, i, p)
            trades.append({"day": bars[i].day, "side": order.side, "price": price, "reason": order.reason,
                           "grams": order.amount / price if order.side == "buy" else min(order.amount, grams_before),
                           "fee": fee, "holding": state.grams})
        pending = []
        equity.append(state.cash + state.grams * bars[i].close)
        invested_days += state.grams > 1e-9
        if i < e:
            pending = strategy.decide(i, days, closes, ind, state)
    final = state.cash + state.grams * bars[e].close * (1 - p.sell_fee_rate)
    return Result(strategy.name, bars[s].day, bars[e].day, final, max_drawdown(equity), len(trades),
                  state.fees_paid + state.grams * bars[e].close * p.sell_fee_rate,
                  invested_days / (e - s + 1), trades)


def fmt_row(r: Result) -> str:
    return (f"| {r.name} | {r.multiple:.2f}× | {r.cagr:+.1%} | {r.max_drawdown:.0%} | {r.fills} "
            f"| {r.fills / r.years:.1f} | {r.fees:,.0f} | {r.exposure:.0%} |")


HEADER = ("| 方案 | 期末/本金 | 年化 | 最大回撤 | 成交笔数 | 每年笔数 | 手续费(元) | 持仓时间占比 |\n"
          "|---|---|---|---|---|---|---|---|")

PERIODS = [
    ("2011–2015 熊市", date(2011, 1, 1), date(2015, 12, 31)),
    ("2016–2019 震荡", date(2016, 1, 1), date(2019, 12, 31)),
    ("2020–2022 冲高回落", date(2020, 1, 1), date(2022, 12, 31)),
    ("2023–至今 牛市+回调", date(2023, 1, 1), date(2100, 1, 1)),
]


def grid(base: PositionParams) -> List[PositionParams]:
    combos = itertools.product(
        (150, 200, 250),
        (0.02, 0.03, 0.05),
        ((0.02, 0.05, 0.09), (0.03, 0.07, 0.12), (0.05, 0.10, 0.15)),
        (0.25, 99.0),                     # 99 = 不止盈
    )
    return [replace(base, sma_long=a, exit_buffer=b, pullbacks=c, tp_gain=d) for a, b, c, d in combos]


def main() -> int:
    parser = argparse.ArgumentParser(description="中长线策略回测")
    parser.add_argument("--start", default="2011-01-01")
    parser.add_argument("--end", default="2100-01-01")
    parser.add_argument("--trades", action="store_true", help="列出默认参数的每笔成交")
    parser.add_argument("--db", default=None, help="SQLite 路径（默认用监控数据库缓存历史数据）")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    apply_proxy()

    settings = Settings()
    history = History(Store(settings.db_path if args.db is None else __import__("pathlib").Path(args.db)))
    history.refresh_if_stale()
    bars = history.bars()
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    p = PositionParams(sell_fee_rate=settings.sell_fee_rate)

    print(f"数据：{bars[0].day} – {bars[-1].day}，{len(bars)} 个交易日（GC=F × USD/CNY 理论换算，元/克）")
    print(f"本金 {BUDGET:,.0f} 元，卖出手续费 {p.sell_fee_rate:.1%}，次日开盘成交\n")

    strategies = build(BACKTESTABLE, p)   # AI 增强版无法回测，只在模拟盘比较
    position = next(st for st in strategies if st.key == "position")
    results = [simulate(st, bars, start, end) for st in strategies]
    bh = next(r for r, st in zip(results, strategies) if st.key == "hold")
    main_res = next(r for r, st in zip(results, strategies) if st.key == "position")
    print(f"## 全区间 {main_res.start} – {main_res.end}\n")
    print(HEADER)
    for r in results:
        print(fmt_row(r))
    print("\n（定投类按 24 个月投完本金；起始日买入/定投扣在次日开盘价）")

    print("\n## 分阶段（各阶段独立从零开始）\n")
    for name, ps, pe in PERIODS:
        if ps < start or ps > bars[-1].day:
            continue
        rs = [simulate(st, bars, ps, pe) for st in strategies]
        print(f"**{name}**：" + "；".join(f"{r.name} {r.multiple:.2f}×（回撤 {r.max_drawdown:.0%}）" for r in rs))

    print("\n## 中长线趋势：参数稳健性（54 组参数，同一全区间）\n")
    grid_results = [simulate(TrendPosition(q), bars, start, end) for q in grid(p)]
    mult = sorted(r.multiple for r in grid_results)
    dd = sorted(r.max_drawdown for r in grid_results)
    print(f"期末/本金：最差 {mult[0]:.2f}× ｜ 中位 {statistics.median(mult):.2f}× ｜ 最好 {mult[-1]:.2f}×（买入持有 {bh.multiple:.2f}×）")
    print(f"最大回撤：最好 {dd[0]:.0%} ｜ 中位 {statistics.median(dd):.0%} ｜ 最差 {dd[-1]:.0%}（买入持有 {bh.max_drawdown:.0%}）")
    print(f"回撤小于买入持有的组合：{sum(r.max_drawdown < bh.max_drawdown for r in grid_results)}/{len(grid_results)}；"
          f"收益高于买入持有的组合：{sum(r.multiple > bh.multiple for r in grid_results)}/{len(grid_results)}")
    print(f"每年成交笔数：{min(r.fills / r.years for r in grid_results):.1f} – {max(r.fills / r.years for r in grid_results):.1f}")

    if args.trades:
        print("\n## 中长线趋势（默认参数）逐笔成交\n")
        for t in main_res.trades:
            print(f"{t['day']} {'买' if t['side'] == 'buy' else '卖'} {t['grams']:.2f}g @ {t['price']:.2f} "
                  f"手续费 {t['fee']:.2f} 持仓 {t['holding']:.2f}g ｜ {t['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
