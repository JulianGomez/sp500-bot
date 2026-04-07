import os
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf
import requests
from dotenv import load_dotenv
import pytz
import random

load_dotenv()

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════════════════════════
CONFIG = {
    "symbols": ["VLO", "AMAT", "EOG", "MOS", "COST", "EQIX", "GILD"],
    "rsi_period": 10,
    "oversold_threshold": 30, 
    "target_profit_pct": 0.03,
    "stop_loss_pct": 0.03,
    "initial_capital": 10000,
    "risk_per_trade_pct": 0.10,
    "telegram_token": os.getenv("TELEGRAM_TOKEN", "").strip(),
    "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", "").strip(),
    "check_interval_minutes": 15,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("sp500_bot.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# CAMUFLAJE PARA YAHOO FINANCE (Evitar Rate Limit)
# ════════════════════════════════════════════════════════════════════════════
# Creamos una sesión de requests que imite a un navegador real
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
})

# ════════════════════════════════════════════════════════════════════════════
# TELEGRAM
# ════════════════════════════════════════════════════════════════════════════
class TelegramReporter:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)
        if self.enabled: log.info("✅ Telegram HABILITADO")

    def send(self, msg):
        if not self.enabled: return False
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            requests.post(url, json={"chat_id": self.chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=10)
            return True
        except Exception as e:
            log.error(f"Error enviando Telegram: {e}")
            return False

# ════════════════════════════════════════════════════════════════════════════
# DATA MANAGER (Con camuflaje y reintentos)
# ════════════════════════════════════════════════════════════════════════════
class DataManager:
    def __init__(self, symbols):
        self.symbols = symbols

    def get_rsi(self, symbol):
        try:
            # Usamos la sesión con User-Agent para evitar el RateLimitError
            df = yf.download(symbol, period="1mo", interval="1d", progress=False, auto_adjust=True, session=session)
            
            if df.empty or len(df) < CONFIG["rsi_period"]:
                return None, None
            
            close_prices = df['Close'].squeeze()
            
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=CONFIG["rsi_period"]).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=CONFIG["rsi_period"]).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            current_rsi = float(rsi.iloc[-1])
            current_price = float(close_prices.iloc[-1])
            
            return current_rsi, current_price
        except Exception as e:
            log.error(f"❌ Error obteniendo datos de {symbol}: {e}")
            return None, None

    def find_best_opportunity(self):
        best_symbol = None
        min_rsi = 100.0
        price = 0.0

        for s in self.symbols:
            # AGREGAMOS UN RETRASO ALEATORIO entre cada acción para no alertar a Yahoo
            time.sleep(random.uniform(2, 5)) 
            
            rsi, p = self.get_rsi(s)
            if rsi is not None and rsi < CONFIG["oversold_threshold"]:
                log.info(f"📊 {s} detectado como sobrevendido: RSI={rsi:.2f}")
                if rsi < min_rsi:
                    min_rsi = rsi
                    best_symbol = s
                    price = p
        
        return best_symbol, min_rsi, price

# ════════════════════════════════════════════════════════════════════════════
# LÓGICA DEL BOT
# ════════════════════════════════════════════════════════════════════════════
class S500Bot:
    def __init__(self):
        self.dm = DataManager(CONFIG["symbols"])
        self.tg = TelegramReporter(CONFIG["telegram_token"], CONFIG["telegram_chat_id"])
        self.capital = CONFIG["initial_capital"]
        self.position = None 

    def is_market_open(self):
        tz_ny = pytz.timezone('America/New_York')
        now_ny = datetime.now(tz_ny)
        
        # LOG DETALLADO para debuggear el horario
        log.info(f"🕒 Hora actual en NY: {now_ny.strftime('%Y-%m-%d %H:%M:%S')} | Día: {now_ny.weekday()}")

        if now_ny.weekday() >= 5: return False
        if now_ny.hour < 9 or (now_ny.hour == 9 and now_ny.minute < 30): return False
        if now_ny.hour >= 16: return False
        return True

    def run(self):
        log.info("🚀 BOT S&P 500 v3.4 (Anti-Bloqueo) INICIADO")
        self.tg.send("🤖 *Bot S&P 500 v3.4 Activo*\nProtección Anti-Bloqueo activada.")

        while True:
            try:
                if not self.is_market_open():
                    log.info("⏰ Mercado cerrado. Esperando...")
                    time.sleep(600)
                    continue

                if self.position:
                    symbol = self.position['symbol']
                    # Espera pequeña antes de consultar precio
                    time.sleep(2)
                    _, current_price = self.dm.get_rsi(symbol)
                    
                    if current_price:
                        pnl = (current_price - self.position['entry_price']) / self.position['entry_price']
                        if pnl >= CONFIG["target_profit_pct"] or pnl <= -CONFIG["stop_loss_pct"]:
                            reason = "Take Profit" if pnl > 0 else "Stop Loss"
                            self.close_position(current_price, pnl, reason)
                        else:
                            log.info(f"⏳ Manteniendo {symbol} | PnL: {pnl:.2%}")
                
                else:
                    symbol, rsi, price = self.dm.find_best_opportunity()
                    if symbol:
                        self.open_position(symbol, price, rsi)

                time.sleep(CONFIG["check_interval_minutes"] * 60)

            except Exception as e:
                log.error(f"❌ Error en ciclo principal: {e}")
                time.sleep(60)

    def open_position(self, symbol, price, rsi):
        amount = self.capital * CONFIG["risk_per_trade_pct"]
        qty = amount / price
        self.position = {'symbol': symbol, 'entry_price': price, 'qty': qty}
        msg = f"🚀 *COMPRA EJECUTADA*\nSímbolo: {symbol}\nPrecio: ${price:.2f}\nRSI: {rsi:.2f}\nCapital riesgo: ${amount:.2f}"
        self.tg.send(msg)
        log.info(f"✅ Compra {symbol} @ {price:.2f}")

    def close_position(self, price, pnl, reason):
        symbol = self.position['symbol']
        profit_usd = (price - self.position['entry_price']) * self.position['qty']
        self.capital += profit_usd
        emoji = "✅" if pnl > 0 else "❌"
        msg = f"{emoji} *VENTA EJECUTADA*\nSímbolo: {symbol}\nPrecio: ${price:.2f}\nPnL: {pnl:.2%}\nMotivo: {reason}\nCapital Total: ${self.capital:.2f}"
        self.tg.send(msg)
        log.info(f"✅ Venta {symbol} | PnL: {pnl:.2%}")
        self.position = None

if __name__ == "__main__":
    bot = S500Bot()
    bot.run()