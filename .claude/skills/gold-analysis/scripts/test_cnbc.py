import urllib.request
import json

from net_proxy import apply_proxy

apply_proxy()

url = 'https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=XAU='
headersStr = {
    'User-Agent': 'Mozilla/5.0'
}
try:
    req = urllib.request.Request(url, headers=headersStr)
    res = urllib.request.urlopen(req, timeout=5).read().decode()
    data = json.loads(res)
    print("SUCCESS CNBC API:", data)
except Exception as e:
    print("ERROR CNBC:", e)
