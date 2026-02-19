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
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.get(url, params={"chat_id": CHAT_ID, "text": message})


# =====================================================
# EVENT DETECTION
# =====================================================

EVENT_NAME = os.getenv("GITHUB_EVENT_NAME", "")

if EVENT_NAME == "workflow_dispatch":
    send_telegram("🚀 Powerful RSI Pivot Divergence Bot Started")


# =====================================================
# SETTINGS (Match Pine Script)
# =====================================================

symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"]
timeframes = ["30m", "1h", "4h", "1d"]

rsi_len = 14
pivot_len = 3
lookback_limit = 50
state_file = "divergence_state.json"

exchange = ccxt.mexc({"enableRateLimit": True})


# =====================================================
# LOAD STATE
# =====================================================

if os.path.exists(state_file):
    with open(state_file, "r") as f:
        sent_signals = json.load(f)
else:
    sent_signals = {}

def save_state():
    with open(state_file, "w") as f:
        json.dump(sent_signals, f)


# =====================================================
# RSI
# =====================================================

def compute_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# =====================================================
# PIVOT DETECTION (Like ta.pivotlow / pivothigh)
# =====================================================

def pivot_low(series, left, right):
    return series[(series.shift(left) > series) & 
                  (series.shift(-right) > series)]

def pivot_high(series, left, right):
    return series[(series.shift(left) < series) & 
                  (series.shift(-right) < series)]


# =====================================================
# FETCH DATA
# =====================================================

def fetch_ohlcv(symbol, timeframe, limit=300):
    data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


# =====================================================
# DIVERGENCE LOGIC (True Pivot Based)
# =====================================================

def check_divergence(df, symbol, timeframe):

    signals = []

    df["rsi"] = compute_rsi(df["close"], rsi_len)

    # Find pivot lows/highs on RSI
    rsi_lows = pivot_low(df["rsi"], pivot_len, pivot_len)
    rsi_highs = pivot_high(df["rsi"], pivot_len, pivot_len)

    # Get last two pivot lows
    last_two_lows = rsi_lows.dropna().tail(2)
    last_two_highs = rsi_highs.dropna().tail(2)

    # -------------------------------
    # CLASSIC BULLISH
    # -------------------------------
    if len(last_two_lows) == 2:

        prev_idx, last_idx = last_two_lows.index[0], last_two_lows.index[1]

        if last_idx - prev_idx <= lookback_limit:

            prev_price = df.loc[prev_idx, "low"]
            last_price = df.loc[last_idx, "low"]

            prev_rsi = df.loc[prev_idx, "rsi"]
            last_rsi = df.loc[last_idx, "rsi"]

            if prev_price > last_price and prev_rsi < last_rsi:

                key = f"{symbol}_{timeframe}_{last_idx}_BULL"

                if key not in sent_signals:
                    signals.append(
                        f"📈 Bullish Classic Divergence\n"
                        f"{symbol} | {timeframe}"
                    )
                    sent_signals[key] = True

    # -------------------------------
    # CLASSIC BEARISH
    # -------------------------------
    if len(last_two_highs) == 2:

        prev_idx, last_idx = last_two_highs.index[0], last_two_highs.index[1]

        if last_idx - prev_idx <= lookback_limit:

            prev_price = df.loc[prev_idx, "high"]
            last_price = df.loc[last_idx, "high"]

            prev_rsi = df.loc[prev_idx, "rsi"]
            last_rsi = df.loc[last_idx, "rsi"]

            if prev_price < last_price and prev_rsi > last_rsi:

                key = f"{symbol}_{timeframe}_{last_idx}_BEAR"

                if key not in sent_signals:
                    signals.append(
                        f"📉 Bearish Classic Divergence\n"
                        f"{symbol} | {timeframe}"
                    )
                    sent_signals[key] = True

    return signals


# =====================================================
# MAIN
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
    
