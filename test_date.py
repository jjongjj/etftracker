from pykrx import stock
from datetime import datetime, timedelta

def get_last_business_day():
    date = datetime.today()
    for _ in range(10):
        date_str = date.strftime("%Y%m%d")
        try:
            ohlcv = stock.get_index_ohlcv(date_str, date_str, "1001") 
            if ohlcv is not None and not ohlcv.empty:
                return date_str
        except Exception as e:
            print(f"Error on {date_str}: {e}")
            pass
        date -= timedelta(days=1)
    return date.strftime("%Y%m%d")

print("Business Day:", get_last_business_day())

def get_last_business_day2():
    date = datetime.today()
    # Find any working ETF price instead
    for _ in range(10):
        date_str = date.strftime("%Y%m%d")
        try:
            ohlcv = stock.get_market_ohlcv(date_str, market="KOSPI") 
            if ohlcv is not None and not ohlcv.empty:
                return date_str
        except Exception as e:
            print(f"Error 2 on {date_str}: {e}")
            pass
        date -= timedelta(days=1)
    return date.strftime("%Y%m%d")

print("Business Day 2:", get_last_business_day2())
