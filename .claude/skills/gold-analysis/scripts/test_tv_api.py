import urllib.request
import json

from net_proxy import apply_proxy

apply_proxy()

url = 'https://scanner.tradingview.com/cfd/scan'
data = b'{"symbols":{"tickers":["OANDA:XAUUSD"]},"columns":["name","close","update_mode"]}'
headersStr = {
    'User-Agent': 'Mozilla/5.0',
    'Content-Type': 'application/json'
}
try:
    req = urllib.request.Request(url, data=data, headers=headersStr)
    res = urllib.request.urlopen(req, timeout=5).read().decode()
    data = json.loads(res)
    print("SUCCESS: ", data)
except Exception as e:
    print("ERROR: ", e)
