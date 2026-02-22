import yfinance as yf

def test_yf_prices(tickers):
    # KRX tickers need .KS for Kospi or .KQ for Kosdaq.
    # We can try .KS first, if no data, fallback to .KQ
    # Actually, yf.download can take multiple tickers
    
    formatted = [f"{t}.KS" for t in tickers]
    data = yf.download(formatted, period="5d", group_by="ticker")
    print(data)

test_yf_prices(["005930", "000660"])
