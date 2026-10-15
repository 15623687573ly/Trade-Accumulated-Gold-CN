"""XAUUSD 现货价 + USD/CNY 汇率采集。

银行积存金报价由 fetch_bank_quotes.py 单独负责（SKILL 阶段2 STEP 1 中两条命令并行运行），
本脚本不再重复抓取，避免 Playwright 跑两遍。

输出: 人类可读摘要 + 完整 JSON。任一数据源失败时对应字段为 null 并附 error，
绝不使用写死的兜底数值（防幻觉纪律）。
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

from net_proxy import apply_proxy

GRAMS_PER_TROY_OUNCE = 31.1035
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

CNBC_XAU_URL = "https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=XAU="
FRANKFURTER_URL = "https://api.frankfurter.app/latest?from=USD&to=CNY"
ER_API_URL = "https://open.er-api.com/v6/latest/USD"


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def compact_error_message(message):
    if not message:
        return "未知错误"
    return str(message).strip().splitlines()[0]


def http_get_json(url, timeout=10):
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())


def fetch_spot_gold():
    """使用 CNBC API 获取外盘现货黄金 (London Spot Gold XAU=) 秒级报价"""
    try:
        data = http_get_json(CNBC_XAU_URL)
        quote = data["FormattedQuoteResult"]["FormattedQuote"][0]
        # 解析如 "5,125.71" 带有逗号的字符串
        price = float(quote.get("last", "0").replace(",", ""))
        if price <= 0:
            raise ValueError(f"CNBC 返回了无效价格: {quote.get('last')!r}")
        return {
            "status": "ok",
            "source": "cnbc",
            "url": CNBC_XAU_URL,
            "price": price,
            # CNBC 返回的时间字符串，如 "2026-03-03T19:19:00.000-0500"
            "market_time": quote.get("last_time", ""),
            "fetched_at": utc_now_iso(),
        }
    except Exception as exc:
        return {"status": "error", "source": "cnbc", "url": CNBC_XAU_URL,
                "error": f"CNBC 现货金获取失败: {exc}", "fetched_at": utc_now_iso()}


def fetch_cny_rate():
    """获取 USD/CNY 汇率，按 frankfurter → open.er-api 顺序尝试。

    注意: 两个源都是日更参考汇率（非银行间即期）。DXY 大幅波动时须按 SKILL 搜索A 另取即期汇率。
    """
    errors = []
    try:
        data = http_get_json(FRANKFURTER_URL, timeout=8)
        return {"status": "ok", "source": "frankfurter (ECB 参考汇率)", "url": FRANKFURTER_URL,
                "rate": float(data["rates"]["CNY"]), "rate_date": data.get("date"),
                "fetched_at": utc_now_iso()}
    except Exception as exc:
        errors.append(f"frankfurter: {compact_error_message(exc)}")
    try:
        data = http_get_json(ER_API_URL, timeout=8)
        return {"status": "ok", "source": "open.er-api", "url": ER_API_URL,
                "rate": float(data["rates"]["CNY"]), "rate_date": data.get("time_last_update_utc"),
                "fetched_at": utc_now_iso()}
    except Exception as exc:
        errors.append(f"open.er-api: {compact_error_message(exc)}")
    return {"status": "error", "error": "; ".join(errors), "fetched_at": utc_now_iso()}


def collect_market_data():
    gold = fetch_spot_gold()
    fx = fetch_cny_rate()
    result = {"fetched_at": utc_now_iso(), "xauusd": gold, "usdcny": fx, "theoretical_cny_per_gram": None}
    if gold["status"] == "ok" and fx["status"] == "ok":
        result["theoretical_cny_per_gram"] = round(gold["price"] * fx["rate"] / GRAMS_PER_TROY_OUNCE, 2)
    return result


def print_human_summary(result):
    print("=" * 45)
    print("🤖 黄金行情采集 (XAUUSD + USD/CNY)")
    print(f"⏰ 取价时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
    print("-" * 45)

    gold = result["xauusd"]
    if gold["status"] == "ok":
        print(f"📍 [1] 国际黄金 (伦敦现货金 XAU/USD): ${gold['price']:.2f} /盎司")
        print(f"   └─ 数据源原始更新时刻: {gold['market_time'] or '未知'}")
    else:
        print(f"❌ [1] 国际黄金获取失败: {compact_error_message(gold['error'])}")

    fx = result["usdcny"]
    if fx["status"] == "ok":
        print(f"📍 [2] USD/CNY: {fx['rate']:.4f}  ({fx['source']}, 日期 {fx['rate_date']})")
    else:
        print(f"❌ [2] USD/CNY 获取失败: {fx['error']}")
        print("   └─ 请按 SKILL 搜索A 用 web_search 获取即期汇率，禁止使用估计值")

    if result["theoretical_cny_per_gram"] is not None:
        print(f"--- 理论换算价(无溢价): {result['theoretical_cny_per_gram']:.2f} 元/克 ---")
    print("=" * 45)
    print("JSON:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    apply_proxy()
    market = collect_market_data()
    print_human_summary(market)
    sys.exit(0 if market["xauusd"]["status"] == "ok" and market["usdcny"]["status"] == "ok" else 1)
