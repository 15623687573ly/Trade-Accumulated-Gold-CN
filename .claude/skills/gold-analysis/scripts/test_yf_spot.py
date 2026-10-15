import yfinance as yf

from net_proxy import apply_proxy

apply_proxy()

gold = yf.Ticker("GC=F")  # XAUUSD=X 已无数据，改用 COMEX 黄金期货
current_price = gold.fast_info['lastPrice']
print("SUCCESS YFINANCE COMEX GOLD FUTURES: ", current_price)
