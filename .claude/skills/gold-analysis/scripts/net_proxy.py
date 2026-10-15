"""境外数据源共用的 HTTP 代理配置。

默认走本机 Clash (http://127.0.0.1:7890)，解决 403 Forbidden 和境外失连问题；
设 GOLD_TRADING_HTTP_PROXY= 为空可直连（代理未开时避免 WinError 10054 / Connection refused）。
"""

import os

DEFAULT_PROXY_URL = "http://127.0.0.1:7890"


def apply_proxy() -> str:
    proxy_url = os.environ.get("GOLD_TRADING_HTTP_PROXY", DEFAULT_PROXY_URL).strip()
    if proxy_url:
        os.environ["http_proxy"] = proxy_url
        os.environ["https_proxy"] = proxy_url
    return proxy_url
