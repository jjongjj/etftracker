from pykrx import stock

b_day = "20260220" # Recent Friday
try:
    ohlcv = stock.get_market_ohlcv(b_day, market="ALL")
    print("ALL OK", len(ohlcv))
except Exception as e:
    print("ALL Error:", repr(e))

try:
    ohlcv = stock.get_market_ohlcv(b_day, market="KOSPI")
    print("KOSPI OK", len(ohlcv))
except Exception as e:
    print("KOSPI Error:", repr(e))
