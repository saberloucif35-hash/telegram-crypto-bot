import os
import time
import threading
import ccxt
import pandas as pd
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from flask import Flask
from datetime import datetime

# ─── Flask Status Server ───────────────────────────────────────────────────────
app = Flask(__name__)

# Simple in-memory stats
stats = {
    "started_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    "signals_sent": 0,
    "last_scan": "لم يبدأ بعد",
    "last_signal": "لا يوجد حتى الآن",
}

@app.route('/')
def home():
    return f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="30">
        <title>Bot Sab3r - SMC Scanner</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0d1117; color: #e6edf3;
                   display: flex; flex-direction: column; align-items: center;
                   justify-content: center; min-height: 100vh; margin: 0; }}
            .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px;
                    padding: 32px 48px; text-align: center; max-width: 480px; }}
            h1 {{ color: #58a6ff; margin-bottom: 4px; }}
            .badge {{ background: #238636; color: #fff; border-radius: 20px;
                     padding: 4px 14px; font-size: 14px; display: inline-block; margin: 8px 0 20px; }}
            .row {{ display: flex; justify-content: space-between; padding: 8px 0;
                   border-bottom: 1px solid #21262d; font-size: 15px; }}
            .row:last-child {{ border-bottom: none; }}
            .label {{ color: #8b949e; }}
            .value {{ color: #e6edf3; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>⚡ Bot Sab3r</h1>
            <div class="badge">🟢 يعمل الآن 24/7</div>
            <div class="row"><span class="label">القناة</span><span class="value">@qsqsaberspot</span></div>
            <div class="row"><span class="label">العملات المراقبة</span><span class="value">30 عملة</span></div>
            <div class="row"><span class="label">الفريمات</span><span class="value">15m + 4H</span></div>
            <div class="row"><span class="label">الإشارات المُرسلة</span><span class="value">{stats['signals_sent']}</span></div>
            <div class="row"><span class="label">آخر فحص</span><span class="value">{stats['last_scan']}</span></div>
            <div class="row"><span class="label">آخر إشارة</span><span class="value">{stats['last_signal']}</span></div>
            <div class="row"><span class="label">تشغيل منذ</span><span class="value">{stats['started_at']}</span></div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "ok", "signals_sent": stats["signals_sent"]}, 200

# ─── Bot Scanner ───────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = "@qsqsaberspot"

SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "ADA/USDT", "AVAX/USDT", "LINK/USDT", "NEAR/USDT", "SUI/USDT",
    "APT/USDT", "PEPE/USDT", "DOGE/USDT", "DOT/USDT", "LTC/USDT",
    "SHIB/USDT", "MATIC/USDT", "UNI/USDT", "ATOM/USDT", "INJ/USDT",
    "TAO/USDT", "FET/USDT", "RENDER/USDT", "WIF/USDT", "SEI/USDT",
    "TIA/USDT", "OP/USDT", "ARB/USDT", "FIL/USDT", "STX/USDT"
]

exchange = ccxt.mexc({'enableRateLimit': True})

def send_telegram_photo(image_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(image_path, 'rb') as photo:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
            res = requests.post(url, data=payload, files={"photo": photo})
            if res.status_code == 200:
                stats["signals_sent"] += 1
                print("✅ تم إرسال الإشارة بنجاح!")
            else:
                print(f"❌ فشل الإرسال: {res.text}")
    except Exception as e:
        print(f"خطأ في الإرسال: {e}")

def generate_chart(df, symbol, setup):
    plt.figure(figsize=(10, 5), dpi=150)
    plt.style.use('dark_background')
    plt.plot(df['timestamp'], df['close'], label=f"Price ({setup['tf']})", color='#00F0FF', linewidth=1.5)
    plt.axhline(setup['retest'],      color='yellow', linestyle='--', label=f"Entry: {setup['retest']}$")
    plt.axhline(setup['invalidation'], color='red',    linestyle='--', label=f"SL: {setup['invalidation']}$")
    plt.axhline(setup['target'],       color='lime',   linestyle='--', label=f"TP: {setup['target']}$")
    plt.axhspan(setup['ob_low'], setup['ob_high'], alpha=0.15,
                color='green' if setup['side'] == 'BUY' else 'red', label='OB Zone')
    title_type = f"Bullish OB ({setup['tf']})" if setup['side'] == 'BUY' else f"Bearish OB ({setup['tf']})"
    plt.title(f"{symbol} — {title_type} | SMC Setup", fontsize=14, color='white', fontweight='bold')
    plt.ylabel("Price (USDT)", color='white')
    plt.grid(True, alpha=0.2)
    plt.legend(loc='upper left', fontsize=8)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    plt.xticks(rotation=30, fontsize=7)
    plt.tight_layout()
    filename = f"chart_{setup['tf']}.png"
    plt.savefig(filename)
    plt.close()
    return filename

def fetch_data(symbol, timeframe, limit=100):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except:
        return None

def check_higher_trend(symbol, higher_tf):
    df = fetch_data(symbol, timeframe=higher_tf, limit=60)
    if df is None: return "NEUTRAL"
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    if df['close'].iloc[-1] > df['ema20'].iloc[-1] > df['ema50'].iloc[-1]: return "BULLISH"
    if df['close'].iloc[-1] < df['ema20'].iloc[-1] < df['ema50'].iloc[-1]: return "BEARISH"
    return "NEUTRAL"

def analyze_smc(symbol, tf, higher_tf, min_range_pct, sl_margin):
    trend = check_higher_trend(symbol, higher_tf)
    if trend == "NEUTRAL": return None
    df = fetch_data(symbol, timeframe=tf, limit=100)
    if df is None or len(df) < 6: return None

    for i in range(len(df) - 5, len(df) - 2):
        ob_low, ob_high = df['low'].iloc[i], df['high'].iloc[i]
        price = df['close'].iloc[-1]
        if ((ob_high - ob_low) / price) * 100 < min_range_pct:
            continue

        if trend == "BULLISH":
            is_down    = df['close'].iloc[i]   < df['open'].iloc[i]
            breakout   = df['close'].iloc[i+1] > df['high'].iloc[i-2:i].max()
            has_fvg    = df['low'].iloc[i+2]   > df['high'].iloc[i]
            if is_down and breakout and has_fvg:
                d = 6 if ob_low < 1 else 2
                sl, retest = round(ob_low*(1-sl_margin), d), round(ob_high, d)
                tp = round(retest + (retest - sl) * 2.5, d)
                return {'symbol': symbol, 'side': 'BUY', 'tf': tf,
                        'type': f"Bullish OB 🟢 [{tf}]", 'retest': retest,
                        'invalidation': sl, 'target': tp, 'ob_low': ob_low,
                        'ob_high': ob_high, 'time': df['timestamp'].iloc[i].strftime('%Y-%m-%d %H:%M'), 'df': df}

        elif trend == "BEARISH":
            is_up      = df['close'].iloc[i]   > df['open'].iloc[i]
            breakout   = df['close'].iloc[i+1] < df['low'].iloc[i-2:i].min()
            has_fvg    = df['high'].iloc[i+2]  < df['low'].iloc[i]
            if is_up and breakout and has_fvg:
                d = 6 if ob_high < 1 else 2
                sl, retest = round(ob_high*(1+sl_margin), d), round(ob_low, d)
                tp = round(retest - (sl - retest) * 2.5, d)
                return {'symbol': symbol, 'side': 'SELL', 'tf': tf,
                        'type': f"Bearish OB 🔴 [{tf}]", 'retest': retest,
                        'invalidation': sl, 'target': tp, 'ob_low': ob_low,
                        'ob_high': ob_high, 'time': df['timestamp'].iloc[i].strftime('%Y-%m-%d %H:%M'), 'df': df}
    return None

def bot_scanner():
    """Bot scanner loop — runs in a background thread."""
    print("🚀 Bot Sab3r SMC Scanner started (30 coins | 15m + 4H)")
    sent_signals = set()
    while True:
        stats["last_scan"] = datetime.utcnow().strftime("%H:%M:%S UTC")
        print(f"\n🔍 Scanning 30 symbols (dual TF)... [{stats['last_scan']}]")
        found = 0
        for symbol in SYMBOLS:
            for sig in [
                analyze_smc(symbol, tf="15m", higher_tf="1h",  min_range_pct=0.4, sl_margin=0.003),
                analyze_smc(symbol, tf="4h",  higher_tf="1d",  min_range_pct=0.8, sl_margin=0.008),
            ]:
                if sig:
                    sid = f"{sig['symbol']}_{sig['tf']}_{sig['side']}_{sig['time']}"
                    if sid not in sent_signals:
                        found += 1
                        chart = generate_chart(sig['df'], sig['symbol'], sig)
                        action = "🟢 دخول شراء (LONG)" if sig['side'] == 'BUY' else "🔴 دخول بيع (SHORT)"
                        label  = "⚡️ صفقة سكالبينج" if sig['tf'] == '15m' else "🏛 صفقة هيكلية كبرى"
                        msg = (
                            f"{label} *SMC* | `{sig['tf']}`\n"
                            f"📌 *النوع:* {sig['type']}\n\n"
                            f"🪙 *الزوج:* `{sig['symbol']}`\n"
                            f"🎯 *الاتجاه:* {action}\n\n"
                            f"📍 *الدخول (Retest):* `{sig['retest']}$`\n"
                            f"🛑 *الوقف (SL):* `{sig['invalidation']}$`\n"
                            f"🎯 *الهدف (TP):* `{sig['target']}$`\n\n"
                            f"📌 *نطاق OB:* `{sig['ob_low']}$ - {sig['ob_high']}$`\n\n"
                            f"📡 *القناة:* @qsqsaberspot"
                        )
                        send_telegram_photo(chart, msg)
                        stats["last_signal"] = f"{sig['symbol']} {sig['tf']} {sig['side']}"
                        sent_signals.add(sid)
                        time.sleep(2)
        if found == 0:
            print("📭 No signals this round.")
        print("💤 Waiting 15 min for next scan...")
        time.sleep(900)

# ─── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Start bot scanner in background thread
    scanner_thread = threading.Thread(target=bot_scanner, daemon=True)
    scanner_thread.start()

    # Start Flask web server (Replit uses PORT env var)
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Flask status server starting on port {port}...")
    app.run(host='0.0.0.0', port=port)
