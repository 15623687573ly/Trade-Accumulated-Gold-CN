"""京东黄金结构化参考数据。仅分析时请求，无 LLM/浏览器，缓存跨进程重启有效。"""
from __future__ import annotations

import json
import math
import urllib.request
import uuid
from datetime import datetime, timezone

BASE = "https://youqian.jd.com/api/gateway/gold/"
TTL = 900


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite")
    return result


def items(raw):
    if not raw.get("success") or raw.get("code") != "0000":
        raise ValueError("provider rejected")
    values = raw.get("data")
    if not isinstance(values, list) or not values:
        raise ValueError("empty data")
    return [json.loads(x) if isinstance(x, str) else x for x in values]


def summarize(kind, raw, now):
    rows = items(raw)
    if kind == "funds":
        row = max(rows, key=lambda x: number(x["publishTime"]))
        stamp = number(row["publishTime"]) / 1000
        result = {"long_pct": number(row["longPositionRatio"]),
                  "short_pct": number(row["shortPositionRatio"]),
                  "volume_usd": number(row["tradingVolume"])}
        if any(not 0 <= result[k] <= 100 for k in ("long_pct", "short_pct")) or result["volume_usd"] < 0:
            raise ValueError("invalid ratios")
    else:
        row = max(rows, key=lambda x: number(x["time"]))
        stamp = number(row["time"])
        levels = row["levels"]
        levels = json.loads(levels) if isinstance(levels, str) else levels
        result = {"reference_price": number(row["price"]), "price_unit": "provider_unspecified",
                  "note": "非京东积存金成交盘口；仅比较占比，不换算或直接用作成交价"}
        for key, field in (("long_clusters", "ol"), ("short_clusters", "os")):
            parsed = [{"price": number(x["price"]), "pct": number(x[field])} for x in levels]
            if any(x["price"] <= 0 or not 0 <= x["pct"] <= 100 for x in parsed):
                raise ValueError("invalid levels")
            result[key] = sorted(parsed, key=lambda x: x["pct"], reverse=True)[:3]
    result["published_at"] = datetime.fromtimestamp(stamp, timezone.utc).isoformat(timespec="seconds")
    age = now.timestamp() - stamp
    # 资金炸弹是离散事件，最多提供最近 24h；盘口仅允许最近一小时。
    result["status"] = "fresh" if -300 <= age <= (86400 if kind == "funds" else 3600) else "stale"
    if result["status"] == "stale":
        return {"status": "stale", "published_at": result["published_at"]}
    return result


def fetch(endpoint, key):
    request = urllib.request.Request(BASE + endpoint, data=b"{}", headers={
        "Content-Type": "application/json", "apikey": key,
        "x-skill-code": "gold-analysis-hub", "x-skill-run-id": str(uuid.uuid4()),
    })
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read(1024 * 1024))


def snapshot(store, api_key, now=None):
    now = now or datetime.now(timezone.utc)
    result = {"source": "京东金融有钳", "url": "https://youqian.jd.com/"}
    for kind, endpoint in (("funds", "bomb"), ("orders", "order-book")):
        state_key = "jd_research:" + kind
        cached = store.get_state(state_key, {})
        try:
            age = now.timestamp() - datetime.fromisoformat(cached["fetched_at"]).timestamp()
        except (KeyError, ValueError, TypeError):
            age = TTL
        if 0 <= age < TTL:
            entry = dict(cached)
            # Re-evaluate source age even when the network cache is still valid.
            if entry.get("raw"):
                entry["summary"] = summarize(kind, entry["raw"], now)
        elif not api_key:
            entry = {"summary": {"status": "unconfigured"}}
        else:
            try:
                raw = fetch(endpoint, api_key)
                entry = {"fetched_at": now.isoformat(timespec="seconds"),
                         "summary": summarize(kind, raw, now), "raw": raw}
            except Exception as exc:
                # 不保存供应商错误文本（可能包含请求信息）；失败也缓存，避免轮询风暴。
                entry = {"fetched_at": now.isoformat(timespec="seconds"),
                         "summary": {"status": "unavailable", "error_type": type(exc).__name__}}
            store.set_state(state_key, entry)
        result[kind] = {"fetched_at": entry.get("fetched_at"), **entry["summary"]}
    return result
