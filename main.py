import ccxt
import pandas as pd
import numpy as np
import requests
import os
import json

# =====================================================
# TELEGRAM CONFIG
# =====================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = "-1003734649641"

def send_telegram(message):
    if not BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except:
        pass


# =====================================================
# START MESSAGE (Manual Run Only)
# =====================================================

if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
    send_telegram("🚀 RSI Pivot Classic + Hidden Divergence Bot Started")


# =====================================================
# SETTINGS
# =====================================================

symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"]
timeframes = ["30m", "1h", "4h", "1d"]

rsi_len = 14
pivot_len = 3
lookback_limit = 50
state_file = "divergence_state.json"

exchange = ccxt.mexc({"enableRateLimit": True})


# =====================================================
# LOAD STATE SAFELY
# =====================================================

try:
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            sent_signals = json.load(f)
    else:
        sent_signals = {}
except:
    sent_signals = {}

def save_state():
    try:
        with open(state_file, "w") as f:
            json.dump(sent_signals, f)
    except:
        pass


# =====================================================
# RSI CALCULATION
# =====================================================

def compute_rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


# =====================================================
# TRUE PIVOT DETECTION
# =====================================================

def detect_pivots(series, left=3, right=3):

    pivots_low = []
    pivots_high = []

    for i in range(left, len(series) - right):

        window = series[i-left:i+right+1]

        if series[i] == window.min():
            pivots_low.append(i)

        if series[i] == window.max():
            pivots_high.append(i)

    return pivots_low, pivots_high


# =====================================================
# FETCH DATA
# =====================================================

def fetch_ohlcv(symbol, timeframe, limit=300):
    data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
    df["rsi"] = compute_rsi(df["close"], rsi_len)
    df = df.dropna().reset_index(drop=True)
    return df


# =====================================================
# DIVERGENCE ENGINE
# =====================================================

def check_divergence(df, symbol, timeframe):

    signals = []

    pivots_low, pivots_high = detect_pivots(df["rsi"], pivot_len, pivot_len)

    # ================= BULLISH SIDE =================
    if len(pivots_low) >= 2:

        prev_idx = pivots_low[-2]
        last_idx = pivots_low[-1]

        if last_idx >= len(df) - pivot_len - 1:
            if last_idx - prev_idx <= lookback_limit:

                prev_price = df.loc[prev_idx, "low"]
                last_price = df.loc[last_idx, "low"]

                prev_rsi = df.loc[prev_idx, "rsi"]
                last_rsi = df.loc[last_idx, "rsi"]

                # Classic Bullish
                if prev_price > last_price and prev_rsi < last_rsi:
                    key = f"{symbol}_{timeframe}_{last_idx}_BULL_CLASSIC"
                    if key not in sent_signals:
                        signals.append(f"📈 Bullish Classic\n{symbol} | {timeframe}")
                        sent_signals[key] = True
                    return signals

                # Hidden Bullish
                if prev_price < last_price and prev_rsi > last_rsi:
                    key = f"{symbol}_{timeframe}_{last_idx}_BULL_HIDDEN"
                    if key not in sent_signals:
                        signals.append(f"🟢 Hidden Bullish\n{symbol} | {timeframe}")
                        sent_signals[key] = True
                    return signals


    # ================= BEARISH SIDE =================
    if len(pivots_high) >= 2:

        prev_idx = pivots_high[-2]
        last_idx = pivots_high[-1]

        if last_idx >= len(df) - pivot_len - 1:
            if last_idx - prev_idx <= lookback_limit:

                prev_price = df.loc[prev_idx, "high"]
                last_price = df.loc[last_idx, "high"]

                prev_rsi = df.loc[prev_idx, "rsi"]
                last_rsi = df.loc[last_idx, "rsi"]

                # Classic Bearish
                if prev_price < last_price and prev_rsi > last_rsi:
                    key = f"{symbol}_{timeframe}_{last_idx}_BEAR_CLASSIC"
                    if key not in sent_signals:
                        signals.append(f"📉 Bearish Classic\n{symbol} | {timeframe}")
                        sent_signals[key] = True
                    return signals

                # Hidden Bearish
                if prev_price > last_price and prev_rsi < last_rsi:
                    key = f"{symbol}_{timeframe}_{last_idx}_BEAR_HIDDEN"
                    if key not in sent_signals:
                        signals.append(f"🔴 Hidden Bearish\n{symbol} | {timeframe}")
                        sent_signals[key] = True
                    return signals

    return signals


# =====================================================
# MAIN LOOP
# =====================================================

def main():

    all_signals = []

    for symbol in symbols:
        for timeframe in timeframes:
            try:
                df = fetch_ohlcv(symbol, timeframe)
                detected = check_divergence(df, symbol, timeframe)
                all_signals.extend(detected)
            except Exception as e:
                print(f"Error {symbol} {timeframe}: {e}")

    if all_signals:
        message = "📊 RSI Pivot Divergence Signals\n"
        message += "━━━━━━━━━━━━━━\n\n"
        message += "\n\n".join(all_signals)
        send_telegram(message)

    save_state()


if __name__ == "__main__":
    main()
    
