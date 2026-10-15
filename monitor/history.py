"""历史日线：Yahoo GC=F（COMEX 黄金期货，与现货有小幅基差）+ CNY=X（USD/CNY），
合成国内人民币金价序列（元/克，不含国内溢价——无历史溢价数据），供中长线策略与回测使用。

数据缓存到 SQLite 的 daily_bars 表，每天最多联网刷新一次。
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from .config import BJ
from .store import Store

import gold_calc

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={p1}&period2={p2}&interval=1d"
GOLD_SYMBOL = "GC=F"
FX_SYMBOL = "CNY=X"
HISTORY_START = date(2010, 1, 1)


@dataclass
class Bar:
    day: date
    xau_open: float
    xau_close: float
    usdcny: float
    open: float    # 元/克
    close: float   # 元/克


def _fetch_yahoo(symbol: str, start: date) -> Dict[date, Dict[str, float]]:
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    url = YAHOO_CHART.format(symbol=symbol, p1=p1, p2=int(time.time()))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    result = json.loads(urllib.request.urlopen(req, timeout=30).read())["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    out: Dict[date, Dict[str, float]] = {}
    for ts, o, c in zip(result["timestamp"], quote["open"], quote["close"]):
        if o is None or c is None:
            continue
        # Yahoo 日线时间戳是交易所当地开盘时刻，换到北京时间取日期会错位，统一用 UTC 日期
        out[datetime.fromtimestamp(ts, timezone.utc).date()] = {"open": float(o), "close": float(c)}
    return out


def build_bars(gold: Dict[date, Dict[str, float]], fx: Dict[date, Dict[str, float]]) -> List[Bar]:
    bars: List[Bar] = []
    last_fx: Optional[float] = None
    fx_days = sorted(fx)
    fx_idx = 0
    for day in sorted(gold):
        while fx_idx < len(fx_days) and fx_days[fx_idx] <= day:   # 汇率按日期向前填充
            last_fx = fx[fx_days[fx_idx]]["close"]
            fx_idx += 1
        if last_fx is None:
            continue
        g = gold[day]
        bars.append(Bar(day, g["open"], g["close"], last_fx,
                        round(gold_calc.theoretical_cny_per_gram(g["open"], last_fx), 2),
                        round(gold_calc.theoretical_cny_per_gram(g["close"], last_fx), 2)))
    return bars


class History:
    def __init__(self, store: Store):
        self.store = store
        store.conn.execute(
            "CREATE TABLE IF NOT EXISTS daily_bars (day TEXT PRIMARY KEY, xau_open REAL, xau_close REAL,"
            " usdcny REAL, open REAL, close REAL)"
        )
        store.conn.commit()

    def refresh_if_stale(self) -> None:
        today = datetime.now(BJ).date().isoformat()
        if self.store.get_state("history_refreshed") == today and self._count() > 0:
            return
        bars = build_bars(_fetch_yahoo(GOLD_SYMBOL, HISTORY_START), _fetch_yahoo(FX_SYMBOL, HISTORY_START))
        self.store.conn.executemany(
            "INSERT OR REPLACE INTO daily_bars VALUES (?,?,?,?,?,?)",
            [(b.day.isoformat(), b.xau_open, b.xau_close, b.usdcny, b.open, b.close) for b in bars],
        )
        self.store.conn.commit()
        self.store.set_state("history_refreshed", today)

    def _count(self) -> int:
        return self.store.conn.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0]

    def bars(self, start: Optional[date] = None, end: Optional[date] = None) -> List[Bar]:
        rows = self.store.conn.execute("SELECT * FROM daily_bars ORDER BY day").fetchall()
        out = [Bar(date.fromisoformat(r["day"]), r["xau_open"], r["xau_close"], r["usdcny"], r["open"], r["close"])
               for r in rows]
        return [b for b in out if (start is None or b.day >= start) and (end is None or b.day <= end)]
