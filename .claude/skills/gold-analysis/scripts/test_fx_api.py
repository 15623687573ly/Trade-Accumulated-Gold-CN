import urllib.request
import json

from net_proxy import apply_proxy

apply_proxy()

url = 'https://open.er-api.com/v6/latest/USD'
headersStr = {
    'User-Agent': 'Mozilla/5.0'
}
try:
    req = urllib.request.Request(url, headers=headersStr)
    res = urllib.request.urlopen(req, timeout=5).read().decode()
    data = json.loads(res)
    print("SUCCESS USD_TO_CNY: ", data['rates']['CNY'])  # er-api 已不提供 XAU，改测 live_market_data 的备用汇率源
except Exception as e:
    print("ERROR: ", e)
