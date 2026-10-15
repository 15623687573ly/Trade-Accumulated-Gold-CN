"""金十数据快讯：抓取最新快讯并筛出与金价相关的条目。

接口为金十网页版自身使用的公开快讯接口（非官方开放 API，字段或访问方式可能变化）。
每次返回最近约 20 条（数分钟内）。国内站点，直连即可，无需代理。

用法: python jin10_flash.py   → 打印最新快讯中与黄金相关的条目（标出金十「重要」标红）
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

FLASH_URL = "https://flash-api.jin10.com/get_flash_list?channel=-8200&vip=1"
HEADERS = {"User-Agent": "Mozilla/5.0", "x-app-id": "bVBF4FyRTn5NJF5n", "x-version": "1.0.0",
           "Origin": "https://www.jin10.com", "Referer": "https://www.jin10.com/"}

# 与金价相关的判断：核心词直接命中；地缘词须同时出现冲突词；排除上市公司公告类
CORE_RE = re.compile(
    r"金价|现货黄金|黄金期货|贵金属|美联储|联储|FOMC|鲍威尔|沃什|Warsh|加息|降息|利率决议|点阵图|"
    r"非农|CPI|PCE|PPI|通胀|美元指数|美债|国债收益率|央行购金|增持黄金|黄金储备|黄金ETF|关税|避险"
)
GEO_RE = re.compile(r"伊朗|以色列|俄罗斯|乌克兰|中东|霍尔木兹|朝鲜|也门|胡塞|黎巴嫩|加沙")
CONFLICT_RE = re.compile(r"战争|冲突|袭击|导弹|空袭|制裁|停火|军事|核设施|开火|入侵|封锁")
EXCLUDE_RE = re.compile(r"公告|净利润|营业收入|证券简称|证券代码|股东|回购|分红")
LEAD_RE = re.compile(r"金十数据\d+月\d+日讯[，,]?")
TAG_RE = re.compile(r"<[^>]+>")


def clean_text(raw: str) -> str:
    text = html.unescape(TAG_RE.sub("", raw or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"点击查看\.*$", "", text).strip()


BJ = ZoneInfo("Asia/Shanghai")


def fetch_flash(timeout: float = 10, max_time: Optional[str] = None) -> List[Dict[str, Any]]:
    """返回一页快讯（新→旧，约 20 条）：id、北京时间、是否重要、正文。max_time 用于向前翻页。"""
    url = FLASH_URL + (f"&max_time={urllib.parse.quote(max_time)}" if max_time else "")
    req = urllib.request.Request(url, headers=HEADERS)
    payload = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
    items = []
    for x in payload.get("data") or []:
        data = x.get("data") or {}
        text = clean_text(data.get("content") or data.get("title") or "")
        if not text:
            continue
        items.append({"id": str(x.get("id")), "time_bj": x.get("time"), "important": bool(x.get("important")), "text": text})
    return items


def fetch_since(since_bj: Optional[str], hours_back: float = 24, max_pages: int = 120,
                pause: float = 0.3) -> List[Dict[str, Any]]:
    """向前翻页，直到早于 since_bj（上次抓到的最新时间）或回溯满 hours_back 小时；返回去重后的新→旧列表。"""
    floor = (datetime.now(BJ) - timedelta(hours=hours_back)).strftime("%Y-%m-%d %H:%M:%S")
    stop_at = max(since_bj or floor, floor)
    out: Dict[str, Dict[str, Any]] = {}
    max_time = None
    for _ in range(max_pages):
        page = fetch_flash(max_time=max_time)
        if not page:
            break
        for item in page:
            if item["time_bj"] >= stop_at:
                out.setdefault(item["id"], item)
        oldest = page[-1]["time_bj"]
        if oldest < stop_at or oldest == max_time:
            break
        max_time = oldest
        time.sleep(pause)
    return sorted(out.values(), key=lambda x: x["time_bj"], reverse=True)


def is_gold_related(item: Dict[str, Any]) -> bool:
    text = LEAD_RE.sub("", item["text"])
    if EXCLUDE_RE.search(text):
        return False
    return bool(CORE_RE.search(text) or (GEO_RE.search(text) and CONFLICT_RE.search(text)))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    flashes = fetch_flash()
    related = [x for x in flashes if is_gold_related(x)]
    print(f"最新 {len(flashes)} 条快讯，其中与金价相关 {len(related)} 条：")
    for x in related:
        print(f"{x['time_bj']} {'🔴重要' if x['important'] else '      '} {x['text'][:120]}")
