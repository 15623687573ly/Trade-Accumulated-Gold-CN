"""由行情快照生成交易计划：点位 → 三轴 → 门控 → 入场区/止损/目标/R:R（全部代码计算）。

积存金只能做多，「卖出」即平掉持仓；三轴综合偏空时不出买入计划，只给持仓减仓区。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import gold_calc as gc

ENTRY_ZONE_BELOW_USD = 3.0     # 入场区：支撑位下方 3 美元
ENTRY_ZONE_ABOVE_USD = 4.0     # 入场区：支撑位上方 4 美元
STOP_BUFFER_USD = 5.0          # 止损放在下一档支撑再下方 5 美元
MAX_STOP_PCT = 0.008           # 下一档支撑太远（>0.8%）或不存在时，止损 = 入场价 × (1 - 0.5%)
FALLBACK_STOP_PCT = 0.005
MIN_TARGET_R = 1.5             # T1 至少距入场 1.5 倍风险距离，否则视为无有效目标
SHOWN_LEVELS = 3


def level_candidates(snap: Dict[str, Any], extra: Optional[Dict[str, float]] = None) -> Dict[str, Optional[float]]:
    tv = snap.get("tv") or {}
    cands = {
        "今日高": snap.get("day_high"), "今日低": snap.get("day_low"), "今日开": snap.get("day_open"),
        "日BOLL上轨": tv.get("bb_upper_1d"), "日BOLL下轨": tv.get("bb_lower_1d"),
        "日SMA20": tv.get("sma20_1d"), "日SMA50": tv.get("sma50_1d"),
        "1H EMA20": tv.get("ema20_1h"), "1H EMA50": tv.get("ema50_1h"),
        "1H BOLL上轨": tv.get("bb_upper_1h"), "1H BOLL下轨": tv.get("bb_lower_1h"),
        "月轴心": tv.get("pivot_m_classic"), "月R1": tv.get("pivot_m_r1"), "月S1": tv.get("pivot_m_s1"),
    }
    cands.update(extra or {})  # 额外候选价位（目前未使用）
    return cands


def build_plan(snap: Dict[str, Any], *, axis_m: Dict[str, str], spread_cny: float, sell_fee_rate: float,
               extra_levels: Optional[Dict[str, float]] = None, ratio_bank: str = "zheshang") -> Dict[str, Any]:
    price = snap["xauusd"]
    ratings = snap.get("ratings") or {}
    levels = gc.pick_levels(price, level_candidates(snap, extra_levels), count=6)
    res_all, sup_all = levels["resistance"], levels["support"]
    res, sup = res_all[:SHOWN_LEVELS], sup_all[:SHOWN_LEVELS]
    if not res or not sup:
        return {"ok": False, "reason": "点位不足（缺少压力或支撑）"}

    pivot = gc.intraday_pivot(snap["day_high"], snap["day_low"]) if snap.get("day_high") else price
    r1, s1 = res[0].price, sup[0].price
    ax_l = gc.axis_l(price, pivot, r1, s1)
    ax_s = gc.axis_s(ratings.get("30m"), ratings.get("1h"), ratings.get("4h"), ratings.get("1d"))
    combined = gc.combine_axes([axis_m["axis"], ax_l["axis"], ax_s["axis"]])
    gate = gc.execution_gate(ratings.get("30m"), ratings.get("1h"))

    ratio_entry = (snap.get("ratios") or {}).get(ratio_bank)
    ratio = ratio_entry["ratio"] if ratio_entry else None

    def cny(usd: float) -> Optional[float]:
        return gc.to_cny(usd, ratio) if ratio else None

    plan: Dict[str, Any] = {
        "ok": True, "price": price, "pivot": pivot, "structural_pivot": gc.structural_pivot(r1, s1),
        "resistance": [{"price": lv.price, "cny": cny(lv.price), "reasons": lv.reasons} for lv in res],
        "support": [{"price": lv.price, "cny": cny(lv.price), "reasons": lv.reasons} for lv in sup],
        "axis_m": axis_m, "axis_l": ax_l, "axis_s": ax_s, "combined": combined,
        "gate": gate, "gate_text": gc.GATE_TEXT[gate], "ratio_bank": ratio_bank, "ratio": ratio,
        "reduce_zone": [r1 - 3, r1 + 3], "buy": None,
    }

    if combined["axis"] == gc.BEAR:
        plan["action"] = "reduce_only"
        plan["summary"] = f"{combined['grade']}·偏空：不新开多，持仓在 R1 {r1:.0f} 附近减仓"
        return plan

    # 入场点：在展示的支撑里选共振（强度≥2）的第一档；偏多从 S1 起找，震荡从 S2 起找（区间下沿）
    start = 0 if combined["axis"] == gc.BULL else min(1, len(sup) - 1)
    buy_idx = next((i for i in range(start, len(sup)) if sup[i].strength >= 2), start)
    entry = sup[buy_idx].price
    lower = sup_all[buy_idx + 1].price if len(sup_all) > buy_idx + 1 else None
    if lower is not None and entry - lower <= entry * MAX_STOP_PCT:
        stop = lower - STOP_BUFFER_USD
    else:
        stop = entry * (1 - FALLBACK_STOP_PCT)
    min_t1 = entry + (entry - stop) * MIN_TARGET_R
    targets: List[float] = sorted(lv.price for lv in sup_all[:buy_idx] + res_all if lv.price >= min_t1)
    t1 = targets[0] if targets else None
    t2 = targets[1] if len(targets) > 1 else None

    buy: Dict[str, Any] = {
        "level": f"S{buy_idx + 1}", "entry": entry,
        "zone": [entry - ENTRY_ZONE_BELOW_USD, entry + ENTRY_ZONE_ABOVE_USD],
        "stop": stop, "t1": t1, "t2": t2,
        "rr1_usd": gc.risk_reward_long(entry, stop, t1) if t1 else None,
        "rr2_usd": gc.risk_reward_long(entry, stop, t2) if t2 else None,
    }
    if ratio:
        buy.update({
            "entry_cny": cny(entry), "zone_cny": [cny(buy["zone"][0]), cny(buy["zone"][1])],
            "stop_cny": cny(stop), "t1_cny": cny(t1) if t1 else None, "t2_cny": cny(t2) if t2 else None,
        })
        cost = {"spread": spread_cny, "sell_fee_rate": sell_fee_rate}
        buy["rr1"] = gc.risk_reward_long(buy["entry_cny"], buy["stop_cny"], buy["t1_cny"], **cost) if t1 else None
        buy["rr2"] = gc.risk_reward_long(buy["entry_cny"], buy["stop_cny"], buy["t2_cny"], **cost) if t2 else None
        buy["breakeven_cny"] = round(gc.breakeven_price(buy["entry_cny"], sell_fee_rate, spread_cny), 2)
    else:
        buy["rr1"], buy["rr2"] = buy["rr1_usd"], buy["rr2_usd"]

    buy["valid"] = bool(buy["rr1"] is not None and buy["rr1"] >= gc.MIN_RR)
    plan["buy"] = buy
    head = f"{combined['grade']}·{combined['axis']}"
    if t1 is None:
        plan["action"] = "wait"
        plan["summary"] = f"{head}：{buy['level']} 上方没有足够远的目标位，只观望"
    elif not buy["valid"]:
        plan["action"] = "wait"
        plan["summary"] = f"{head}：{buy['level']} 低吸扣手续费后 R:R {buy['rr1']:.2f} 不足 {gc.MIN_RR}，只观望"
    else:
        plan["action"] = "buy_on_dip"
        plan["summary"] = (f"{head}：回落到 {buy['level']} {buy['zone'][0]:.0f}–{buy['zone'][1]:.0f} "
                           f"且门控不为「不入场」时低吸")
    return plan
