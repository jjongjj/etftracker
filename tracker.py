import os
import json
import logging
from datetime import datetime, timedelta
import requests
import pandas as pd
from pykrx import stock

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG_FILE = 'config.json'
HISTORY_DIR = 'history'
HISTORY_FILE = os.path.join(HISTORY_DIR, 'constituents.json')
DASHBOARD_FILE = 'dashboard_data.json'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram credentials not set. Logging message instead:")
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML" 
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        logging.error(f"Failed to send Telegram message: {response.text}")
    else:
        logging.info("Telegram message sent successfully.")

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_stock_name(ticker):
    try:
        return stock.get_market_ticker_name(ticker) or ticker
    except:
        return ticker

def get_last_business_day():
    try:
        url = "https://m.stock.naver.com/api/index/KOSPI/price?pageSize=1&page=1"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0 and 'localTradedAt' in data[0]:
                date_str = data[0]['localTradedAt'].split('T')[0].replace('-', '')
                return date_str
    except Exception as e:
        logging.error(f"Error fetching business day from Naver: {e}")
    
    # Fallback to simple weekday calculation if Naver fails
    date = datetime.today()
    if date.weekday() >= 5: # Saturday or Sunday
        date -= timedelta(days=date.weekday() - 4) # Fallback to Friday
    return date.strftime("%Y%m%d")

def get_pdf(ticker, date_str):
    # KRX Data HTTP API (Bypassing PyKrx formatting bugs)
    url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020506"
    }
    
    # ISIN Mapping for common ETFs (since PyKrx mapper is also broken)
    isin_map = {
        "069500": "KR7069500007", # KODEX 200
        "273620": "KR7273620002", # KODEX MSCI Korea
    }
    isin = isin_map.get(ticker, f"KR7{ticker}000") # Rough fallback
    
    date_obj = datetime.strptime(date_str, "%Y%m%d")
    
    for _ in range(10): 
        current_date_str = date_obj.strftime("%Y%m%d")
        payload = {
            "bld": "dbms/MDC/STAT/standard/MDCSTAT05001",
            "trdDd": current_date_str,
            "isuCd": isin
        }
        
        try:
            resp = requests.post(url, data=payload, headers=headers, timeout=10)
            data = resp.json()
            if 'output' in data and len(data['output']) > 0:
                # Extract bare tickers
                tickers = []
                for item in data['output']:
                    comp_cd = item.get('COMPST_ISU_CD', '')
                    # KRX might return full ISIN or 6-digit. Usually 6-digit.
                    if comp_cd:
                        # Sometimes they have an 'A' prefix like 'A005930' or 'KR7...'
                        clean_cd = comp_cd[-6:] if len(comp_cd) >= 6 else comp_cd
                        if clean_cd != ticker:
                            tickers.append(clean_cd)
                
                if tickers:
                    logging.info(f"KRX Direct Fetch success for {ticker} ({len(tickers)} items)")
                    return pd.DataFrame(index=tickers)
        except Exception as e:
            pass
            
        date_obj -= timedelta(days=1)
        
    logging.warning(f"KRX PDF failed for {ticker}. Using static fallback.")
    fallback_tickers = []
    if ticker == "069500" or ticker == "273620": # KODEX 200 / MSCI Korea
         fallback_tickers = [
            "005930", "000660", "373220", "207940", "005380", 
            "068270", "000270", "051910", "105560", "055550", 
            "005490", "035420", "032830", "012330", "028260", 
            "066570", "323410", "035720", "096770", "011200"
         ]
         df = pd.DataFrame(index=fallback_tickers)
         df['dummy'] = 1 # Prevent .empty evaluation
         return df
         
    return pd.DataFrame() # Return empty explicitly

import yfinance as yf

def fetch_daily_market_data(b_day, constituents):
    """Fetches OHLCV and Net Purchases for the given constituents using yfinance and pykrx."""
    data = {}
    
    # 1. Prepare YFinance tickers (.KS preferred, fallback .KQ if needed, we'll just try .KS then .KQ)
    # To keep it simple and fast, we'll query .KS first. If it fails or returns NaN, we query .KQ.
    # We can query all at once, yfinance handles missing gracefully.
    tickers_ks = [f"{t}.KS" for t in constituents]
    tickers_kq = [f"{t}.KQ" for t in constituents]
    
    try:
        logging.info("Fetching OHLCV from yfinance...")
        # Get last 5 days just to be safe and compute change
        yf_data_ks = yf.download(tickers_ks, period="5d", group_by="ticker", auto_adjust=False, threads=True)
        yf_data_kq = yf.download(tickers_kq, period="5d", group_by="ticker", auto_adjust=False, threads=True)
    except Exception as e:
        logging.error(f"yfinance download error: {e}")
        yf_data_ks, yf_data_kq = None, None

    # 2. Try pykrx for net purchases only (these endpoints might still work)
    net_f, net_i = pd.DataFrame(), pd.DataFrame()
    try:
        net_f_kospi = stock.get_market_net_purchases_of_equities_by_ticker(b_day, b_day, "KOSPI", "외국인")
        net_f_kosdaq = stock.get_market_net_purchases_of_equities_by_ticker(b_day, b_day, "KOSDAQ", "외국인")
        net_i_kospi = stock.get_market_net_purchases_of_equities_by_ticker(b_day, b_day, "KOSPI", "기관합계")
        net_i_kosdaq = stock.get_market_net_purchases_of_equities_by_ticker(b_day, b_day, "KOSDAQ", "기관합계")
        
        net_f = pd.concat([net_f_kospi, net_f_kosdaq]) if not net_f_kospi.empty else net_f_kospi
        net_i = pd.concat([net_i_kospi, net_i_kosdaq]) if not net_i_kospi.empty else net_i_kospi
    except Exception:
        logging.warning("Pykrx net purchase fetch failed (likely KRX API json error)")

    # 3. Assemble data
    for ticker in constituents:
        item = {"code": ticker, "name": get_stock_name(ticker), "change_rate": 0.0, "net_foreign": 0, "net_institutional": 0, "market_cap": 0}
        
        # Determine OHLCV source (.KS or .KQ)
        t_ks, t_kq = f"{ticker}.KS", f"{ticker}.KQ"
        
        # yfinance multi-ticker download returns a MultiIndex column DataFrame if multiple, or simple if 1.
        # Handling the structure:
        yf_ticker_df = None
        if yf_data_ks is not None and t_ks in yf_data_ks.columns.levels[0] if isinstance(yf_data_ks.columns, pd.MultiIndex) else False:
            yf_ticker_df = yf_data_ks[t_ks].dropna(how='all')
        elif yf_data_ks is not None and len(constituents) == 1:
            yf_ticker_df = yf_data_ks.dropna(how='all')
            
        if (yf_ticker_df is None or yf_ticker_df.empty) and yf_data_kq is not None:
             if isinstance(yf_data_kq.columns, pd.MultiIndex) and t_kq in yf_data_kq.columns.levels[0]:
                 yf_ticker_df = yf_data_kq[t_kq].dropna(how='all')
             elif len(constituents) == 1:
                 yf_ticker_df = yf_data_kq.dropna(how='all')

        if yf_ticker_df is not None and not yf_ticker_df.empty and len(yf_ticker_df) >= 2:
            close_today = float(yf_ticker_df['Close'].iloc[-1])
            close_prev = float(yf_ticker_df['Close'].iloc[-2])
            if close_prev > 0:
                item["change_rate"] = round(((close_today - close_prev) / close_prev) * 100, 2)
                
            # Try to get market cap if possible, yfinance download doesn't have it.
            # We'll fetch it via Yahoo ticker info individually (might be slow so we skip if > 50, or default to 0)
            # Actually, without market cap we can't do the Weight Pie chart accurately.
            # Let's fallback to PyKrx for Market Cap only using get_market_cap if it works:
            pass
            
        # Try Pykrx for market cap specifically because yfinance multi-download lacks it
        try:
             cap_df = stock.get_market_cap(b_day, market="ALL")
             if cap_df is not None and not cap_df.empty and ticker in cap_df.index:
                 item["market_cap"] = int(cap_df.loc[ticker].get("시가총액", 0))
        except:
             pass
                
        if not net_f.empty and ticker in net_f.index:
            item["net_foreign"] = int(net_f.loc[ticker].get("순매수대금", 0)) 
            
        if not net_i.empty and ticker in net_i.index:
            item["net_institutional"] = int(net_i.loc[ticker].get("순매수대금", 0))
            
        data[ticker] = item
        
    return data

def main():
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
        
    config = load_json(CONFIG_FILE)
    if not config or 'etfs' not in config:
        logging.error("Invalid config.json")
        return
        
    history = load_json(HISTORY_FILE)
    dashboard_data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "business_day": "",
        "etfs": {}
    }
    
    b_day = get_last_business_day()
    dashboard_data["business_day"] = b_day
    logging.info(f"Target Business Day: {b_day}")
    
    changes_detected = False
    full_message = f"🚨 <b>ETF 편입/편출 알림 ({b_day})</b> 🚨\n\n"
    
    # 1. Filter enabled ETFs
    active_etfs = [etf for etf in config['etfs'] if etf.get('enabled', True)]
    
    for etf in active_etfs:
        etf_code = etf['code']
        etf_name = etf['name']
        logging.info(f"Processing ETF: {etf_name} ({etf_code})")
        
        pdf = get_pdf(etf_code, b_day)
        if pdf is None or pdf.empty:
            logging.warning(f"No constituents found for {etf_name}")
            continue
            
        current_tickers = []
        if pdf.index is not None and len(pdf.index) > 0:
            current_tickers = [str(t) for t in pdf.index]
        else:
            try: current_tickers = [str(t) for t in pdf]
            except: pass

        # Structural changes (Additions / Deletions)
        previous_tickers = history.get(etf_code, [])
        curr_set = set(current_tickers)
        prev_set = set(previous_tickers)
        
        added = curr_set - prev_set if previous_tickers else set()
        removed = prev_set - curr_set if previous_tickers else set()
        
        added_list = [{"code": t, "name": get_stock_name(t)} for t in added]
        removed_list = [{"code": t, "name": get_stock_name(t)} for t in removed]

        if added or removed:
            changes_detected = True
            full_message += f"📊 <b>{etf_name} ({etf_code})</b>\n"
            if added:
                full_message += "➕ <b>편입</b>: " + ", ".join([get_stock_name(t) for t in added]) + "\n"
            if removed:
                full_message += "➖ <b>편출</b>: " + ", ".join([get_stock_name(t) for t in removed]) + "\n"
            full_message += "\n"
            
        # Daily Dynamic Data Collection
        daily_metrics = fetch_daily_market_data(b_day, current_tickers)
        metrics_list = list(daily_metrics.values())
        
        # Sort for Gainers / Losers
        gainers = sorted(metrics_list, key=lambda x: x["change_rate"], reverse=True)[:5]
        losers = sorted(metrics_list, key=lambda x: x["change_rate"])[:5]
        
        # Sort for Net Purchases (Top 3)
        foreign_buys = sorted(metrics_list, key=lambda x: x["net_foreign"], reverse=True)[:3]
        inst_buys = sorted(metrics_list, key=lambda x: x["net_institutional"], reverse=True)[:3]
        
        # ETF NAV Deviation calculation
        deviation = 0.0
        try:
            dev_df = stock.get_etf_price_deviation(b_day, etf_code)
            if dev_df is not None and not dev_df.empty:
                 deviation = float(dev_df.iloc[0].get("괴리율", 0.0))
        except:
             pass
             
        # Market Cap Weights computation
        total_market_cap = sum([m["market_cap"] for m in metrics_list])
        for m in metrics_list:
             m["weight"] = round((m["market_cap"] / total_market_cap * 100), 2) if total_market_cap > 0 else 0.0
             
        top_weights = sorted(metrics_list, key=lambda x: x["weight"], reverse=True)[:10]

        # Save to dashboard
        dashboard_data["etfs"][etf_code] = {
            "name": etf_name,
            "code": etf_code,
            "total_constituents": len(current_tickers),
            "deviation": deviation,
            "recent_changes": {
                "added": added_list,
                "removed": removed_list
            },
            "gainers": gainers,
            "losers": losers,
            "foreign_buys": foreign_buys,
            "inst_buys": inst_buys,
            "top_weights": top_weights,
            "constituents": metrics_list
        }
        
        history[etf_code] = current_tickers
        
    if changes_detected:
        logging.info("Changes detected. Sending Telegram message.")
        send_telegram_message(full_message)
        
    save_json(history, HISTORY_FILE)
    save_json(dashboard_data, DASHBOARD_FILE)

if __name__ == "__main__":
    main()
