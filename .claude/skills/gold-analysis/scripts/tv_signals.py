"""TradingView 扫描接口：XAUUSD 当日 OHLC + 多时间框架技术评级 + 指标。

不需要浏览器、不受 Investing.com 403 影响；SKILL 阶段2 Investing.com 不可达时用它替代多时间框架信号。
注意：TradingView 提供 30m/1H/4H/日线/周线，没有 Investing.com 的 5H 档，报告中以 4H 代替并注明。

用法: python tv_signals.py   → 人类可读摘要 + JSON
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict

from gold_calc import rating_label
from net_proxy import apply_proxy

TV_SCAN_URL = "https://scanner.tradingview.com/cfd/scan"
TV_SYMBOL = "OANDA:XAUUSD"

# TradingView 列名 → 输出字段名
COLUMNS = {
    "close": "price",
    "open": "day_open",
    "high": "day_high",
    "low": "day_low",
    "change": "change_pct",
    "Recommend.All|30": "rating_30m",
    "Recommend.All|60": "rating_1h",
    "Recommend.All|240": "rating_4h",
    "Recommend.All": "rating_1d",
    "Recommend.All|1W": "rating_1w",
    "RSI": "rsi_1d",
    "RSI|60": "rsi_1h",
    "MACD.macd": "macd_1d",
    "MACD.signal": "macd_signal_1d",
    "Stoch.K": "stoch_k_1d",
    "Stoch.D": "stoch_d_1d",
    "BB.upper": "bb_upper_1d",
    "BB.lower": "bb_lower_1d",
    "SMA20": "sma20_1d",
    "SMA50": "sma50_1d",
    "EMA20|60": "ema20_1h",
    "EMA50|60": "ema50_1h",
    "BB.upper|60": "bb_upper_1h",
    "BB.lower|60": "bb_lower_1h",
    "Pivot.M.Classic.Middle": "pivot_m_classic",
    "Pivot.M.Classic.R1": "pivot_m_r1",
    "Pivot.M.Classic.S1": "pivot_m_s1",
}

TIMEFRAMES = [("30m", "rating_30m"), ("1H", "rating_1h"), ("4H", "rating_4h"), ("日线", "rating_1d"), ("周线", "rating_1w")]


def fetch_tv_snapshot(timeout: float = 10) -> Dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        body = json.dumps({"symbols": {"tickers": [TV_SYMBOL]}, "columns": list(COLUMNS)}).encode()
        req = urllib.request.Request(
            TV_SCAN_URL, data=body, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
        )
        payload = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
        row = payload["data"][0]["d"]
        result: Dict[str, Any] = {"status": "ok", "source": "tradingview", "symbol": TV_SYMBOL,
                                  "url": TV_SCAN_URL, "fetched_at": fetched_at}
        result.update({COLUMNS[col]: value for col, value in zip(COLUMNS, row)})
        result["signals"] = {tf: rating_label(result.get(key)) for tf, key in TIMEFRAMES}
        return result
    except Exception as exc:
        return {"status": "error", "source": "tradingview", "url": TV_SCAN_URL,
                "error": f"TradingView 扫描失败: {exc}", "fetched_at": fetched_at}


def print_human_summary(snap: Dict[str, Any]) -> None:
    print("=" * 45)
    print("📊 TradingView XAUUSD 多时间框架信号")
    if snap["status"] != "ok":
        print(f"❌ {snap['error']}")
    else:
        print(f"现价 {snap['price']:.2f} | 今日 {snap['day_low']:.2f} – {snap['day_high']:.2f} | 涨跌 {snap['change_pct']:+.2f}%")
        for tf, key in TIMEFRAMES:
            value = snap.get(key)
            print(f"  {tf:<4} {snap['signals'][tf]:<5} ({value:+.2f})" if value is not None else f"  {tf:<4} 无数据")
        print(f"  RSI(日) {snap['rsi_1d']:.1f} | RSI(1H) {snap['rsi_1h']:.1f} | MACD(日) {snap['macd_1d']:.1f}/{snap['macd_signal_1d']:.1f}")
    print("=" * 45)
    print("JSON:")
    print(json.dumps(snap, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    apply_proxy()
    snapshot = fetch_tv_snapshot()
    print_human_summary(snapshot)
    sys.exit(0 if snapshot["status"] == "ok" else 1)
