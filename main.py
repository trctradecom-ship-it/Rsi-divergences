import ccxt
import pandas as pd
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
# EVENT DETECTION (Manual vs Schedule)
# =====================================================

EVENT_NAME = os.getenv("GITHUB_EVENT_NAME", "")

if EVENT_NAME == "workflow_dispatch":
    send_telegram("🚀 RSI Divergence Bot Started (Manual Run)")


# =====================================================
# SETTINGS
# =====================================================

symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"]
timeframes = ["30m", "1h", "4h", "1d", "1w"]
lookbacks = [3, 6]
rsi_period = 14
state_file = "divergence_state.json"

exchange = ccxt.mexc({"enableRateLimit": True})


# =====================================================
# LOAD / SAVE STATE (Prevent Duplicate Alerts)
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
# RSI CALCULATION
# =====================================================

def compute_rsi(prices, period=14):
    delta = pd.Series(prices).diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


# =====================================================
# FETCH DATA
# =====================================================

def fetch_ohlcv(symbol, timeframe, limit=200):
    data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

    df = pd.DataFrame(
        data,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )

    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


# =====================================================
# DIVERGENCE CHECK (Latest Candle Only)
# =====================================================

def check_divergence(df, symbol, timeframe):

    signals = []
    i = len(df) - 1

    for lb in lookbacks:

        price_now = df.iloc[i]["close"]
        price_prev = df.iloc[i - lb]["close"]

        rsi_now = df.iloc[i]["rsi"]
        rsi_prev = df.iloc[i - lb]["rsi"]

        if pd.isna(rsi_now) or pd.isna(rsi_prev):
            continue

        dt = str(df.iloc[i]["datetime"])
        base_key = f"{symbol}_{timeframe}_{lb}_{dt}"

        # -------------------------------
        # Bullish Regular
        # Price: Lower Low
        # RSI: Higher Low
        # -------------------------------
        if price_now < price_prev and rsi_now > rsi_prev:
            key = base_key + "_BR"
            if key not in sent_signals:
                signals.append(
                    f"📈 Bullish Regular\n"
                    f"Symbol: {symbol}\n"
                    f"Timeframe: {timeframe}\n"
                    f"Lookback: {lb}"
                )
                sent_signals[key] = True

        # -------------------------------
        # Bearish Regular
        # Price: Higher High
        # RSI: Lower High
        # -------------------------------
        elif price_now > price_prev and rsi_now < rsi_prev:
            key = base_key + "_BEAR"
            if key not in sent_signals:
                signals.append(
                    f"📉 Bearish Regular\n"
                    f"Symbol: {symbol}\n"
                    f"Timeframe: {timeframe}\n"
                    f"Lookback: {lb}"
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
                df["rsi"] = compute_rsi(df["close"], rsi_period)

                detected = check_divergence(df, symbol, timeframe)
                all_signals.extend(detected)

            except Exception as e:
                print(f"⚠ Error {symbol} {timeframe}: {e}")

    # ----------------------------------------
    # SEND ONE CLEAN MESSAGE (No Spam)
    # ----------------------------------------

    if all_signals:

        message = "📊 RSI Divergence Signals\n"
        message += "━━━━━━━━━━━━━━\n\n"
        message += "\n\n".join(all_signals)

        send_telegram(message)

    save_state()


if __name__ == "__main__":
    main()
    
