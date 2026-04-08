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
    "symbols": ["VLO", "AMAT", "EOG", "MOS", "COST", "EQIX", "GILD", "AMD", "NVDA", "TSLA", "PYPL", "INTC", "BA", "NFLX", "SBUX"],
    "rsi_period": 10,
    "oversold_threshold": 40,  # 🟢 SUBIDO DE 35 A 40 PARA DAR MÁS OPORTUNIDADES
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
# DATA MANAGER (Ahora con Logs Verbosos)
# ════════════════════════════════════════════════════════════════════════════
class DataManager:
    def __init__(self, symbols):
        self.symbols = symbols

    def get_rsi(self, symbol):
        try:
            df = yf.download(symbol, period="1mo", interval="1d", progress=False, auto_adjust=True)
            if df.empty or len(df) < CONFIG["rsi_period"]:
                return None, None
            
            close_prices = df['Close'].squeeze()
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=CONFIG["rsi_period"]).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=CONFIG["rsi_period"]).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi.iloc[-1]), float(close_prices.iloc[-1])
        except Exception as e:
            log.error(f"❌ Error obteniendo datos de {symbol}: {e}")
            return None, None

    def find_best_opportunity(self):
        best_symbol = None
        min_rsi = 100.0
        price = 0.0

        log.info("🔍 INICIANDO ESCANEO DE MERCADO...")
        
        for s in self.symbols:
            time.sleep(random.uniform(2, 4)) 
            rsi, p = self.get_rsi(s)
            
            if rsi is not None:
                # LOG DETALLADO: Aquí es donde ves que el bot está trabajando
                status = "🎯 SOBREVENDIDO" if rsi < CONFIG["oversold_threshold"] else "⏩ Saltando"
                log.info(f"   - {s}: RSI={rsi:.2f} | Precio=${p:.2f} -> {status}")
                
                if rsi < min_rsi:
                    min_rsi = rsi
                    best_symbol = s
                    price = p
            else:
                log.info(f"   - {s}: ⚠️ Sin datos disponibles")
        
        if best_symbol:
            log.info(f"✅ Escaneo finalizado. El RSI más bajo fue {best_symbol} con {min_rsi:.2f}")
            if min_rsi >= CONFIG["oversold_threshold"]:
                log.info(f"😴 Ninguna acción bajó del umbral de {CONFIG['oversold_threshold']}. Sin trades.")
        
        return best_symbol if min_rsi < CONFIG["oversold_threshold"] else None, min_rsi, price

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
        log.info(f"🕒 Hora actual en NY: {now_ny.strftime('%Y-%m-%d %H:%M:%S')} | Día: {now_ny.weekday()}")

        if now_ny.weekday() >= 5: return False
        if now_ny.hour < 9 or (now_ny.hour == 9 and now_ny.minute < 30): return False
        if now_ny.hour >= 16: return False
        return True

    def run(self):
        log.info("🚀 BOT S&P 500 v3.7 (Modo Verboso) INICIADO")
        self.tg.send("🤖 *Bot S&P 500 v3.7 Activo*\nUmbral ajustado a 35. Logs detallados activados.")

        while True:
            try:
                if not self.is_market_open():
                    log.info("⏰ Mercado cerrado. Esperando...")
                    time.sleep(600)
                    continue

                if self.position:
                    symbol = self.position['symbol']
                    log.info(f"📈 Monitoreando posición abierta en {symbol}...")
                    time.sleep(5)
                    _, current_price = self.dm.get_rsi(symbol)
                    
                    if current_price:
                        pnl = (current_price - self.position['entry_price']) / self.position['entry_price']
                        log.info(f"   - {symbol} PnL actual: {pnl:.2%}")
                        if pnl >= CONFIG["target_profit_pct"] or pnl <= -CONFIG["stop_loss_pct"]:
                            reason = "Take Profit" if pnl > 0 else "Stop Loss"
                            self.close_position(current_price, pnl, reason)
                        else:
                            log.info("   - Manteniendo posición...")
                
                else:
                    symbol, rsi, price = self.dm.find_best_opportunity()
                    if symbol:
                        self.open_position(symbol, price, rsi)

                log.info(f"💤 Esperando {CONFIG['check_interval_minutes']} min para el próximo escaneo...")
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
        log.info(f"💰 COMPRA EJECUTADA: {symbol} @ {price:.2f} (RSI={rsi:.2f})")

    def close_position(self, price, pnl, reason):
        symbol = self.position['symbol']
        profit_usd = (price - self.position['entry_price']) * self.position['qty']
        self.capital += profit_usd
        emoji = "✅" if pnl > 0 else "❌"
        msg = f"{emoji} *VENTA EJECUTADA*\nSímbolo: {symbol}\nPrecio: ${price:.2f}\nPnL: {pnl:.2%}\nMotivo: {reason}\nCapital Total: ${self.capital:.2f}"
        self.tg.send(msg)
        log.info(f"📉 VENTA EJECUTADA: {symbol} | PnL: {pnl:.2%} | Motivo: {reason}")
        self.position = None

if __name__ == "__main__":
    bot = S500Bot()
    bot.run()