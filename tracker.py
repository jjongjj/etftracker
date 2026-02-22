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
    date = datetime.today()
    for _ in range(10):
        date_str = date.strftime("%Y%m%d")
        try:
            ohlcv = stock.get_index_ohlcv(date_str, date_str, "1001") 
            if ohlcv is not None and not ohlcv.empty:
                return date_str
        except Exception:
            pass
        date -= timedelta(days=1)
    return date.strftime("%Y%m%d")

def get_pdf(ticker, date_str):
    for _ in range(5):
        try:
            pdf = stock.get_etf_portfolio_deposit_file(date_str, ticker)
            if pdf is not None and not pdf.empty:
                return pdf
        except Exception as e:
             logging.debug(f"Error fetching PDF for {ticker} on {date_str}: {e}")
        # Try previous day
        date_obj = datetime.strptime(date_str, "%Y%m%d") - timedelta(days=1)
        date_str = date_obj.strftime("%Y%m%d")
    return None

def fetch_daily_market_data(b_day, constituents):
    """Fetches OHLCV and Net Purchases for the given constituents."""
    data = {}
    try:
        ohlcv = stock.get_market_ohlcv(b_day, market="ALL")
        net_f_kospi = stock.get_market_net_purchases_of_equities_by_ticker(b_day, b_day, "KOSPI", "외국인")
        net_f_kosdaq = stock.get_market_net_purchases_of_equities_by_ticker(b_day, b_day, "KOSDAQ", "외국인")
        net_i_kospi = stock.get_market_net_purchases_of_equities_by_ticker(b_day, b_day, "KOSPI", "기관합계")
        net_i_kosdaq = stock.get_market_net_purchases_of_equities_by_ticker(b_day, b_day, "KOSDAQ", "기관합계")
        
        # Merge DataFrames safely
        net_f = pd.concat([net_f_kospi, net_f_kosdaq]) if not net_f_kospi.empty else net_f_kospi
        net_i = pd.concat([net_i_kospi, net_i_kosdaq]) if not net_i_kospi.empty else net_i_kospi

        for ticker in constituents:
            item = {"code": ticker, "name": get_stock_name(ticker), "change_rate": 0.0, "net_foreign": 0, "net_institutional": 0, "market_cap": 0}
            
            if ticker in ohlcv.index:
                row = ohlcv.loc[ticker]
                item["change_rate"] = float(row.get("등락률", 0.0))
                item["market_cap"] = int(row.get("시가총액", 0))
                
            if not net_f.empty and ticker in net_f.index:
                # Value is usually in won (순매수거래대금)
                item["net_foreign"] = int(net_f.loc[ticker].get("순매수대금", 0)) 
                
            if not net_i.empty and ticker in net_i.index:
                item["net_institutional"] = int(net_i.loc[ticker].get("순매수대금", 0))
                
            data[ticker] = item
            
    except Exception as e:
        logging.error(f"Error fetching daily market data: {e}")
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
            
        current_tickers = [str(t) for t in pdf.index]
        if not current_tickers:
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
