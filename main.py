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
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": CHAT_ID, "text": message})
    except:
        pass


# =====================================================
# EVENT DETECTION
# =====================================================

EVENT_NAME = os.getenv("GITHUB_EVENT_NAME", "")

if EVENT_NAME == "workflow_dispatch":
    send_telegram("🚀 RSI Pivot Divergence Bot Started")


# =====================================================
# SETTINGS (Match TradingView Script)
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
# RSI FUNCTION
# =====================================================

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# =====================================================
# TRUE PIVOT DETECTION (LEFT & RIGHT CONFIRMATION)
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
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


# =====================================================
# DIVERGENCE ENGINE (STRICT VERSION)
# =====================================================

def check_divergence(df, symbol, timeframe):

    signals = []

    df["rsi"] = compute_rsi(df["close"], rsi_len)

    rsi_series = df["rsi"]

    pivots_low, pivots_high = detect_pivots(rsi_series, pivot_len, pivot_len)

    # =========================
    # BULLISH CLASSIC
    # =========================
    if len(pivots_low) >= 2:

        prev_idx = pivots_low[-2]
        last_idx = pivots_low[-1]

        # Only check if latest pivot confirmed recently
        if last_idx >= len(df) - pivot_len - 1:

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

                    return signals   # prevent opposite signal


    # =========================
    # BEARISH CLASSIC
    # =========================
    if len(pivots_high) >= 2:

        prev_idx = pivots_high[-2]
        last_idx = pivots_high[-1]

        if last_idx >= len(df) - pivot_len - 1:

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
    
