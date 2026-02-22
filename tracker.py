import os
import json
import logging
from datetime import datetime, timedelta
import requests
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
        # HTML formatting since some characters might break MarkdownV2
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
        # get_market_ticker_name expects ticker string
        name = stock.get_market_ticker_name(ticker)
        return name if name else ticker
    except:
        return ticker

def get_pdf(ticker):
    """
    Tries to get the portfolio deposit file for the last few days
    until it finds a non-empty result.
    """
    date = datetime.today()
    for _ in range(10): # Look back up to 10 days
        date_str = date.strftime("%Y%m%d")
        try:
            pdf = stock.get_etf_portfolio_deposit_file(date_str, ticker)
            if pdf is not None and not pdf.empty:
                logging.info(f"Loaded PDF for {ticker} on {date_str} (Length: {len(pdf)})")
                return pdf
        except Exception as e:
             logging.debug(f"Error fetching PDF for {ticker} on {date_str}: {e}")
        # Try previous day
        date -= timedelta(days=1)
    return None

def main():
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
        
    config = load_json(CONFIG_FILE)
    if not config or 'etfs' not in config:
        logging.error("Invalid or missing config.json")
        return
        
    history = load_json(HISTORY_FILE)
    dashboard_data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "etfs": {}
    }
    
    changes_detected = False
    full_message = "🚨 <b>ETF 구성 종목 편입/편출 알림</b> 🚨\n\n"
    
    for etf in config['etfs']:
        etf_code = etf['code']
        etf_name = etf['name']
        logging.info(f"Processing ETF: {etf_name} ({etf_code})")
        
        pdf = get_pdf(etf_code)
        if pdf is None or pdf.empty:
            logging.warning(f"No constituents found for {etf_name} in the recent days.")
            continue
            
        # The result index contains the ticker symbols
        current_tickers = [str(t) for t in pdf.index]
        if not current_tickers: # If it's a list instead of index, try iterating pdf directly
            try:
                current_tickers = [str(t) for t in pdf]
            except:
                pass

        previous_tickers = history.get(etf_code, [])
        
        # Checking additions and deletions
        curr_set = set(current_tickers)
        prev_set = set(previous_tickers)
        
        # Only compare if we have previous records
        added = curr_set - prev_set if previous_tickers else set()
        removed = prev_set - curr_set if previous_tickers else set()

        added_list = []
        removed_list = []
        
        if added or removed:
            changes_detected = True
            full_message += f"📊 <b>{etf_name} ({etf_code})</b>\n"
            
            if added:
                full_message += "➕ <b>편입 (Additions)</b>\n"
                for t in added:
                    name = get_stock_name(t)
                    full_message += f" - {name} ({t})\n"
                    added_list.append({"code": t, "name": name})
            
            if removed:
                full_message += "➖ <b>편출 (Deletions)</b>\n"
                for t in removed:
                    name = get_stock_name(t)
                    full_message += f" - {name} ({t})\n"
                    removed_list.append({"code": t, "name": name})
                    
            full_message += "\n"
        else:
             logging.info(f"No changes for {etf_name}")
        
        # Save to dashboard
        etf_dashboard_info = {
            "name": etf_name,
            "code": etf_code,
            "total_constituents": len(current_tickers),
            "recent_changes": {
                "added": added_list,
                "removed": removed_list
            },
            "constituents": [{"code": t, "name": get_stock_name(t)} for t in current_tickers]
        }
        dashboard_data["etfs"][etf_code] = etf_dashboard_info
        
        # Update state immediately
        history[etf_code] = current_tickers
        
    if changes_detected:
        logging.info("Changes detected. Sending Telegram message.")
        send_telegram_message(full_message)
    else:
        logging.info("No ETF constituent changes detected today.")
        
    # Persist the states
    save_json(history, HISTORY_FILE)
    logging.info(f"Saved history to {HISTORY_FILE}")
    
    save_json(dashboard_data, DASHBOARD_FILE)
    logging.info(f"Saved dashboard data to {DASHBOARD_FILE}")

if __name__ == "__main__":
    main()
