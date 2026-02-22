from pykrx import stock
from datetime import datetime, timedelta

def test_api():
    date = datetime.today()
    for _ in range(10):
        date_str = date.strftime("%Y%m%d")
        print(f"Trying date: {date_str}")
        try:
            tickers = stock.get_etf_ticker_list(date_str)
            if tickers:
                print(f"Found {len(tickers)} ETFs on {date_str}")
                
                # Test KODEX 200 (069500)
                pdf_200 = stock.get_etf_portfolio_deposit_file(date_str, "069500")
                if pdf_200 is not None and not pdf_200.empty:
                    print(f"KODEX 200 PDF on {date_str}: length {len(pdf_200)}")
                    
                # Test MSCI Korea (273620)
                pdf_msci = stock.get_etf_portfolio_deposit_file(date_str, "273620")
                if pdf_msci is not None and not pdf_msci.empty:
                    print(f"KODEX MSCI Korea PDF on {date_str}: length {len(pdf_msci)}")
                else:
                    print(f"No PDF for KODEX MSCI Korea on {date_str}")
                return
        except Exception as e:
            print(f"Error on {date_str}: {e}")
        date -= timedelta(days=1)

test_api()
