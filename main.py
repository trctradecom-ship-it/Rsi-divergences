import ccxt
import numpy as np
import pandas as pd
import requests
import os
import json
from datetime import datetime, timezone

# ===============================
# 🤖 BOT SOURCE
# ===============================
BOT_SOURCE = "GitHub Actions"

# ===============================
# 🔐 TELEGRAM (SECURE)
# ===============================
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = "-1003734649641"

# ===============================
# SETTINGS
# ===============================
symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"]
timeframes = ["30m", "1h", "4h", "1d", "1w"]
lookbacks = [3, 6]
rsi_period = 14

STATE_FILE = "divergence_state.json"

exchange = ccxt.mexc({"enableRateLimit": True})

# ===============================
# LOAD / SAVE STATE
# ===============================
def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

# ===============================
# TELEGRAM
# ===============================
def send_telegram(message):
    if not TELEGRAM_TOKEN:
        print("BOT_TOKEN not found!")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message
        }, timeout=15)
    except Exception as e:
        print("Telegram Error:", e)

# ===============================
# RSI CALCULATION
# ===============================
def compute_rsi(prices, period=14):
    diff = np.diff(prices)
    gain = np.where(diff > 0, diff, 0)
    loss = np.where(diff < 0, -diff, 0)
    avg_gain = pd.Series(gain).rolling(period).mean()
    avg_loss = pd.Series(loss).rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return np.concatenate([np.full(period, np.nan), rsi[period:]])

# ===============================
# FETCH DATA
# ===============================
def fetch_ohlcv(symbol, timeframe, limit=200):
    data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

# ===============================
# DIVERGENCE CHECK
# ===============================
def check_divergence(df, lookback, symbol, timeframe, state):

    signals = []

    for i in range(lookback, len(df)-1):

        price_now = df.iloc[i]["close"]
        price_prev = df.iloc[i-lookback]["close"]

        rsi_now = df.iloc[i]["rsi"]
        rsi_prev = df.iloc[i-lookback]["rsi"]

        dt = df.iloc[i]["datetime"]

        if pd.isna(rsi_now) or pd.isna(rsi_prev):
            continue

        signal_type = None

        # Bullish Regular
        if price_now < price_prev and rsi_now > rsi_prev:
            signal_type = "Bullish Regular"

        # Bearish Regular
        elif price_now > price_prev and rsi_now < rsi_prev:
            signal_type = "Bearish Regular"

        # Hidden Bullish
        elif price_now > price_prev and rsi_now < rsi_prev:
            signal_type = "Hidden Bullish"

        # Hidden Bearish
        elif price_now < price_prev and rsi_now > rsi_prev:
            signal_type = "Hidden Bearish"

        if not signal_type:
            continue

        key = f"{symbol}_{timeframe}_{signal_type}_{lookback}_{dt}"

        if state.get(key):
            continue

        message = (
            f"📊 RSI Divergence Signal\n\n"
            f"🤖 Source: {BOT_SOURCE}\n\n"
            f"📈 Type: {signal_type}\n"
            f"📊 Pair: {symbol}\n"
            f"⏱ TF: {timeframe}\n"
            f"🔍 Lookback: {lookback}\n"
            f"💰 Price: {price_now:.2f}\n"
            f"📉 RSI: {rsi_now:.2f}\n"
            f"🕒 UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        )

        signals.append((key, message))

    return signals

# ===============================
# MAIN
# ===============================
def main():

    state = load_state()

    # Manual start message only
    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        send_telegram(
            "🚀 RSI Divergence Bot Started\n\n"
            f"🤖 Source: {BOT_SOURCE}\n"
            f"🕒 UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        )

    for symbol in symbols:
        for timeframe in timeframes:

            try:
                df = fetch_ohlcv(symbol, timeframe)
                df["rsi"] = compute_rsi(df["close"].values, rsi_period)

                for lb in lookbacks:
                    signals = check_divergence(df, lb, symbol, timeframe, state)

                    for key, msg in signals:
                        print(msg)
                        send_telegram(msg)
                        state[key] = True

            except Exception as e:
                print(f"Error {symbol} {timeframe}: {e}")

    save_state(state)

if __name__ == "__main__":
    main()
    
