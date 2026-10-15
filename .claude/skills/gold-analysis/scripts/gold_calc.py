"""SKILL 中所有确定性计算：轴心、换算、溢价拦截、R:R、三轴 AxisL/AxisS、执行门控、点位筛选。

纯函数、无网络，供 skill 工作流与 monitor/ 常驻程序共用——数字一律由代码算，不交给模型手算。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

GRAMS_PER_TROY_OUNCE = 31.1035
PREMIUM_NORMAL_ABS = 15.0     # 溢价正常波动范围 ±15 元/克
PREMIUM_ABORT_ABS = 30.0      # 超过即判定抓取错误
SELL_FEE_RATE = 0.004         # 浙商/民生积存金卖出手续费 0.4%（买入 0%），见 references/accumulation-gold.md
DEFAULT_SPREAD_CNY = 0.0      # 民生为买卖单一报价、浙商页面也只展示单一实时金价，默认无价差
MIN_RR = 1.5

BULL, BEAR, RANGE = "偏多", "偏空", "震荡"


# ── 换算 ────────────────────────────────────────────────────────────────

def theoretical_cny_per_gram(xauusd: float, usdcny: float) -> float:
    return xauusd * usdcny / GRAMS_PER_TROY_OUNCE


def conversion_ratio(bank_price: float, xauusd: float) -> float:
    return bank_price / xauusd


def premium(bank_price: float, xauusd: float, usdcny: float) -> float:
    return bank_price - theoretical_cny_per_gram(xauusd, usdcny)


def premium_status(value: float) -> str:
    """ok / unusual（超出常态但未到拦截线）/ abort（必须停止并人工核实）"""
    if abs(value) > PREMIUM_ABORT_ABS:
        return "abort"
    if abs(value) > PREMIUM_NORMAL_ABS:
        return "unusual"
    return "ok"


def to_cny(xauusd_level: float, ratio: float) -> float:
    return round(xauusd_level * ratio, 2)


# ── 轴心与风险收益 ──────────────────────────────────────────────────────

def intraday_pivot(day_high: float, day_low: float) -> float:
    return (day_high + day_low) / 2


def structural_pivot(r1: float, s1: float) -> float:
    return (r1 + s1) / 2


def net_sell_proceeds(sell_price: float, sell_fee_rate: float = SELL_FEE_RATE, spread: float = 0.0) -> float:
    """卖出 1 克实际到手：卖出价 × (1 − 手续费率) − 价差。"""
    return sell_price * (1 - sell_fee_rate) - spread


def breakeven_price(entry: float, sell_fee_rate: float = SELL_FEE_RATE, spread: float = 0.0) -> float:
    """卖出价至少达到多少才不亏（含手续费与价差）。"""
    return (entry + spread) / (1 - sell_fee_rate)


def risk_reward_long(entry: float, stop: float, target: float, spread: float = 0.0,
                     sell_fee_rate: float = 0.0) -> Optional[float]:
    """做多 R:R（按实际到手计）：收益 = 目标价卖出净得 − 买入价；风险 = 买入价 − 止损价卖出净得。

    积存金须传 sell_fee_rate=SELL_FEE_RATE（价格为元/克时）；纯 XAUUSD 口径可不传。
    """
    risk = entry - net_sell_proceeds(stop, sell_fee_rate, spread)
    reward = net_sell_proceeds(target, sell_fee_rate, spread) - entry
    if risk <= 0:
        return None
    return reward / risk


# ── 多时间框架信号 ──────────────────────────────────────────────────────

def rating_label(value: Optional[float]) -> str:
    """TradingView Recommend.All（-1..1）→ 五档信号，阈值与 TradingView 官方一致。"""
    if value is None:
        return "无数据"
    if value >= 0.5:
        return "强烈买入"
    if value >= 0.1:
        return "买入"
    if value > -0.1:
        return "中性"
    if value > -0.5:
        return "卖出"
    return "强烈卖出"


def _sign(value: Optional[float]) -> int:
    if value is None or -0.1 < value < 0.1:
        return 0
    return 1 if value > 0 else -1


def execution_gate(r30: Optional[float], r60: Optional[float]) -> str:
    """30m/1H 执行门控：allow（可按计划入场）/ block（不入场等支撑）/ light（矛盾，轻仓或观望）"""
    s30, s60 = _sign(r30), _sign(r60)
    if s30 > 0 and s60 > 0:
        return "allow"
    if s30 < 0 and s60 < 0:
        return "block"
    return "light"


GATE_TEXT = {"allow": "✅ 门控允许按计划入场", "block": "⛔ 不入场，等支撑", "light": "🔄 信号矛盾，轻仓或观望"}


def axis_s(r30: Optional[float], r60: Optional[float], r240: Optional[float], r1d: Optional[float]) -> Dict[str, str]:
    """AxisS：短线(30m/1H) 与 大级别(4H 或日线) 同向 → 该方向；反向 → 震荡（短线逆势）。"""
    short = _sign((r30 or 0) + (r60 or 0)) if r30 is not None or r60 is not None else 0
    big_values = [v for v in (r240, r1d) if v is not None]
    big = _sign(sum(big_values) / len(big_values)) if big_values else 0
    if short != 0 and short == big:
        return {"axis": BULL if short > 0 else BEAR, "note": "短线与大级别同向"}
    if short != 0 and big != 0:
        return {"axis": RANGE, "note": "短线逆势（与 4H/日线 反向）"}
    return {"axis": RANGE, "note": "信号不明确"}


def axis_l(price: float, pivot: float, r1: float, s1: float, band: Optional[float] = None) -> Dict[str, str]:
    """AxisL：明显高于 P 且更近 R1 → 偏多；明显低于 P 且更近 S1 → 偏空；否则震荡。"""
    band = band if band is not None else price * 0.001
    if price > pivot + band and (r1 - price) < (price - s1):
        return {"axis": BULL, "note": f"高于轴心 {price - pivot:+.1f} 且更接近 R1"}
    if price < pivot - band and (price - s1) < (r1 - price):
        return {"axis": BEAR, "note": f"低于轴心 {price - pivot:+.1f} 且更接近 S1"}
    return {"axis": RANGE, "note": f"距轴心 {price - pivot:+.1f}，夹在 R1/S1 之间"}


def combine_axes(axes: Sequence[str]) -> Dict[str, str]:
    bulls, bears = axes.count(BULL), axes.count(BEAR)
    if bulls and bears:
        return {"axis": RANGE, "grade": "多轴互斥", "note": "优先级：硬事件 > 日线趋势 > 30m 噪音"}
    if bulls == 3 or bears == 3:
        return {"axis": BULL if bulls else BEAR, "grade": "三轴一致", "note": ""}
    if bulls == 2 or bears == 2:
        return {"axis": BULL if bulls else BEAR, "grade": "两轴一致一轴背离", "note": "条件单式操作"}
    if bulls == 1 or bears == 1:
        return {"axis": RANGE, "grade": "一轴有方向两轴震荡", "note": ""}
    return {"axis": RANGE, "grade": "三轴一致（震荡）", "note": "区间操作"}


# ── 点位筛选 ────────────────────────────────────────────────────────────

@dataclass
class Level:
    price: float
    reasons: List[str] = field(default_factory=list)

    @property
    def strength(self) -> int:
        return len(self.reasons)


def cluster_levels(candidates: Dict[str, Optional[float]], merge_within: float) -> List[Level]:
    """把来源各异的候选价位按距离合并，合并后的 reasons 数即共振强度。"""
    items = sorted((p, name) for name, p in candidates.items() if p)
    levels: List[Level] = []
    for price, name in items:
        if levels and price - levels[-1].price <= merge_within:
            last = levels[-1]
            n = last.strength
            last.price = (last.price * n + price) / (n + 1)
            last.reasons.append(name)
        else:
            levels.append(Level(price, [name]))
    return levels


def pick_levels(
    price: float,
    candidates: Dict[str, Optional[float]],
    *,
    merge_within: float = 6.0,
    min_gap: float = 4.0,
    round_step: float = 50.0,
    count: int = 3,
) -> Dict[str, List[Level]]:
    """返回 {"resistance": [R1..], "support": [S1..]}（各 count 个），R 由近到远、S 由近到远。

    自动补充整数关口；离现价不足 min_gap 的价位视为「正在测试」，不作为 R1/S1。
    """
    pool = dict(candidates)
    base = int(price // round_step) * round_step
    for k in range(-2, 4):
        pool[f"整数关口{base + k * round_step:.0f}"] = base + k * round_step
    levels = cluster_levels(pool, merge_within)
    above = [lv for lv in levels if lv.price >= price + min_gap]
    below = [lv for lv in levels if lv.price <= price - min_gap]
    return {"resistance": above[:count], "support": list(reversed(below))[:count]}
