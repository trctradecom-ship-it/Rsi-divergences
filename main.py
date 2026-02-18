import ccxt
import numpy as np
import pandas as pd
import requests
import os
from datetime import datetime

# -----------------------
# TELEGRAM CONFIG
# -----------------------
TELEGRAM_TOKEN = "7213196077:AAE6OqSQuAnMYm7oiuaViYpwH0VqgilVPBI"
CHAT_ID = "-1003734649641"

def send_telegram(message):
    """
    Send Telegram message
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.get(url, params={"chat_id": CHAT_ID, "text": message})

# -----------------------
# EVENT TYPE DETECTION
# -----------------------
EVENT_NAME = os.getenv("EVENT_NAME", "schedule")  # GitHub passes this
if EVENT_NAME == "workflow_dispatch":
    # Only send this message on manual run
    send_telegram("🚀 Crypto Divergence Bot started manually!")

# -----------------------
# EXCHANGE & PAIRS
# -----------------------
symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"]
timeframes = ["30m", "1h", "4h", "1d", "1w"]
lookbacks = [3, 6]
rsi_period = 14

exchange = ccxt.mexc({"enableRateLimit": True})

# -----------------------
# RSI CALCULATION
# -----------------------
def compute_rsi(prices, period=14):
    diff = np.diff(prices)
    gain = np.where(diff > 0, diff, 0)
    loss = np.where(diff < 0, -diff, 0)
    avg_gain = pd.Series(gain).rolling(period).mean()
    avg_loss = pd.Series(loss).rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return np.concatenate([np.full(period, np.nan), rsi[period:]])

# -----------------------
# FETCH OHLCV DATA
# -----------------------
def fetch_ohlcv(symbol, timeframe, limit=200):
    data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

# -----------------------
# TRACK SENT SIGNALS TO AVOID DUPLICATES
# -----------------------
sent_signals = set()

# -----------------------
# DIVERGENCE CHECK
# -----------------------
def check_divergence(df, lookback, symbol, timeframe):
    signals = []

    for i in range(lookback, len(df)):
        price_now, price_prev = df.iloc[i]["close"], df.iloc[i-lookback]["close"]
        rsi_now, rsi_prev = df.iloc[i]["rsi"], df.iloc[i-lookback]["rsi"]
        dt = df.iloc[i]["datetime"]

        # Bullish Regular
        if price_now < price_prev and rsi_now > rsi_prev:
            sig_id = f"{symbol}_{timeframe}_BR_{lookback}_{dt}"
            if sig_id not in sent_signals:
                signals.append(f"📈 Bullish Regular {symbol} {timeframe} at {dt} | Price: {price_now:.2f} | RSI: {rsi_now:.2f} | lookback:{lookback}")
                sent_signals.add(sig_id)

        # Bearish Regular
        if price_now > price_prev and rsi_now < rsi_prev:
            sig_id = f"{symbol}_{timeframe}_BEAR_{lookback}_{dt}"
            if sig_id not in sent_signals:
                signals.append(f"📉 Bearish Regular {symbol} {timeframe} at {dt} | Price: {price_now:.2f} | RSI: {rsi_now:.2f} | lookback:{lookback}")
                sent_signals.add(sig_id)

        # Hidden Bullish
        if price_now > price_prev and rsi_now < rsi_prev:
            sig_id = f"{symbol}_{timeframe}_HIDDEN_BULL_{lookback}_{dt}"
            if sig_id not in sent_signals:
                signals.append(f"🔹 Hidden Bullish {symbol} {timeframe} at {dt} | Price: {price_now:.2f} | RSI: {rsi_now:.2f} | lookback:{lookback}")
                sent_signals.add(sig_id)

        # Hidden Bearish
        if price_now < price_prev and rsi_now > rsi_prev:
            sig_id = f"{symbol}_{timeframe}_HIDDEN_BEAR_{lookback}_{dt}"
            if sig_id not in sent_signals:
                signals.append(f"🔸 Hidden Bearish {symbol} {timeframe} at {dt} | Price: {price_now:.2f} | RSI: {rsi_now:.2f} | lookback:{lookback}")
                sent_signals.add(sig_id)

    return signals

# -----------------------
# MAIN LOOP
# -----------------------
def main():
    for symbol in symbols:
        for timeframe in timeframes:
            try:
                df = fetch_ohlcv(symbol, timeframe)
                df["rsi"] = compute_rsi(df["close"].values, rsi_period)

                all_signals = []

                for lb in lookbacks:
                    signals = check_divergence(df, lb, symbol, timeframe)
                    all_signals.extend(signals)

                # Send all signals
                for msg in all_signals:
                    print(msg)
                    send_telegram(msg)

            except Exception as e:
                print(f"⚠ Error fetching {symbol} {timeframe}: {e}")

if __name__ == "__main__":
    main()
  
