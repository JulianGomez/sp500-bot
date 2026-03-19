"""
🤖 S&P 500 Bot v3.1 FIXED - OPERANDO EN VIVO CON DATOS REALES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Bot S&P 500 RSI10 Mean Reversion
✅ Analiza precios REALES ahora
✅ Abre/cierra trades EN VIVO (sin dinero real, pero con lógica real)
✅ Telegram integrado (alertas instantáneas)
✅ Corre continuamente en Railway
✅ Aprendizaje día a día

Uso:
  python sp500_bot_v3.1_FIXED.py live    # Modo LIVE real
"""

import os
import sys
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import yfinance as yf
import requests
from dotenv import load_dotenv

# Cargar .env
load_dotenv()

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

CONFIG = {
    "symbols": ["VLO", "AMAT", "EOG", "MOS", "COST", "EQIX", "GILD"],
    "rsi_period": 10,
    "oversold_threshold": 35,
    "target_profit_pct": 0.03,
    "stop_loss_pct": 0.03,
    "time_based_exit_hour": 16,
    "initial_capital": 10000,
    "risk_per_trade_pct": 0.10,
    "telegram_token": os.getenv("TELEGRAM_TOKEN", "").strip(),
    "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", "").strip(),
    "check_interval_minutes": 30,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("sp500_bot.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# TELEGRAM
# ════════════════════════════════════════════════════════════════════════════

class TelegramReporter:
    def __init__(self, token: str, chat_id: str):
        self.token = token.strip() if token else ""
        self.chat_id = chat_id.strip() if chat_id else ""
        self.enabled = bool(self.token and self.chat_id)
        
        if self.enabled:
            log.info("✅ Telegram HABILITADO")

    def send(self, msg: str) -> bool:
        if not self.enabled:
            return False
        
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": msg,
                    "parse_mode": "Markdown"
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            log.warning(f"[TG] Error: {e}")
            return False

    def report_trade_open(self, symbol: str, entry_price: float, rsi10: float, capital: float):
        msg = (
            f"🚀 *COMPRA*\n"
            f"Símbolo: {symbol}\n"
            f"Precio: ${entry_price:.2f}\n"
            f"RSI(10): {rsi10:.1f}\n"
            f"Capital: ${capital:.2f}"
        )
        self.send(msg)

    def report_trade_close(self, symbol: str, entry: float, exit_price: float, 
                          pnl_pct: float, reason: str):
        emoji = "✅" if pnl_pct > 0 else "❌"
        msg = (
            f"{emoji} *VENTA*\n"
            f"Símbolo: {symbol}\n"
            f"${entry:.2f} → ${exit_price:.2f}\n"
            f"PnL: {pnl_pct:+.2f}%\n"
            f"Razón: {reason}"
        )
        self.send(msg)

    def report_status(self, msg: str):
        self.send(msg)


# ════════════════════════════════════════════════════════════════════════════
# DATA MANAGER
# ════════════════════════════════════════════════════════════════════════════

class DataManager:
    def __init__(self, symbols: List[str], period: int = 10):
        self.symbols = symbols
        self.period = period

    def get_live_data(self, symbol: str, days_back: int = 30) -> Optional[pd.DataFrame]:
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            df = yf.download(
                symbol,
                start=start_date,
                end=end_date,
                progress=False,
                interval="1d",
                auto_adjust=True
            )
            
            if df is None or df.empty or len(df) == 0:
                return None
            
            # Calcular RSI(10)
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            return df
            
        except Exception as e:
            log.warning(f"Error descargando {symbol}: {e}")
            return None

    def find_most_oversold_now(self, threshold: int = 35) -> Tuple[Optional[str], float, float]:
        """Encuentra símbolo más oversold"""
        most_oversold = None
        min_rsi = 100
        price = 0.0
        
        for symbol in self.symbols:
            try:
                df = self.get_live_data(symbol, days_back=30)
                if df is None or len(df) < self.period:
                    continue
                
                rsi_value = df['RSI'].iloc[-1]
                price_value = df['Close'].iloc[-1]
                
                # Convertir a float
                rsi_value = float(rsi_value)
                price_value = float(price_value)
                
                if not np.isnan(rsi_value) and rsi_value < threshold and rsi_value < min_rsi:
                    min_rsi = rsi_value
                    most_oversold = symbol
                    price = price_value
            except Exception as e:
                log.warning(f"Error procesando {symbol}: {e}")
                continue
        
        return most_oversold, min_rsi if most_oversold else 100.0, price

    def get_current_price_now(self, symbol: str) -> Optional[float]:
        """Obtiene precio actual"""
        try:
            df = yf.download(symbol, period="5d", progress=False, auto_adjust=True)
            if df is None or df.empty or len(df) == 0:
                return None
            price = float(df['Close'].iloc[-1])
            return price if price > 0 else None
        except Exception as e:
            log.warning(f"Error obteniendo precio de {symbol}: {e}")
            return None


# ════════════════════════════════════════════════════════════════════════════
# POSICIÓN
# ════════════════════════════════════════════════════════════════════════════

class Position:
    def __init__(self, symbol: str, entry_price: float, quantity: float, 
                 capital: float, rsi10: float):
        self.symbol = symbol
        self.entry_price = float(entry_price)
        self.entry_time = datetime.now()
        self.quantity = float(quantity)
        self.capital = float(capital)
        self.rsi10 = float(rsi10)
        self.exit_price = None
        self.exit_time = None
        self.exit_reason = None
        self.pnl_pct = None

    def check_exit_now(self, current_price: float, current_hour: int) -> bool:
        """Verifica si debe cerrarse"""
        current_price = float(current_price)
        pnl_pct = (current_price - self.entry_price) / self.entry_price

        if pnl_pct >= CONFIG["target_profit_pct"]:
            self.exit_price = current_price
            self.exit_time = datetime.now()
            self.exit_reason = "Take Profit (+3%)"
            self.pnl_pct = pnl_pct
            return True

        if pnl_pct <= -CONFIG["stop_loss_pct"]:
            self.exit_price = current_price
            self.exit_time = datetime.now()
            self.exit_reason = "Stop Loss (-3%)"
            self.pnl_pct = pnl_pct
            return True

        if current_hour >= CONFIG["time_based_exit_hour"]:
            self.exit_price = current_price
            self.exit_time = datetime.now()
            self.exit_reason = "End of Day"
            self.pnl_pct = pnl_pct
            return True

        return False


# ════════════════════════════════════════════════════════════════════════════
# BOT LIVE
# ════════════════════════════════════════════════════════════════════════════

class S500BotLive:
    def __init__(self):
        self.symbols = CONFIG["symbols"]
        self.data_manager = DataManager(self.symbols, CONFIG["rsi_period"])
        self.telegram = TelegramReporter(CONFIG["telegram_token"], CONFIG["telegram_chat_id"])
        
        self.capital = CONFIG["initial_capital"]
        self.position: Optional[Position] = None
        self.trades_history = []
        
        log.info("=" * 60)
        log.info("🤖 BOT S&P 500 v3.1 FIXED - EN VIVO")
        log.info("=" * 60)
        log.info(f"Símbolos: {', '.join(self.symbols)}")
        log.info(f"Capital: ${self.capital:,.2f}")
        log.info(f"Oversold threshold: < {CONFIG['oversold_threshold']}")
        log.info("=" * 60)
        
        self.telegram.send("🚀 *Bot S&P 500 v3.1 INICIADO*\nOperando en tiempo real...")

    def open_trade_now(self, symbol: str, entry_price: float, rsi10: float) -> bool:
        if self.position:
            log.info("⚠️  Ya hay posición abierta")
            return False

        capital_allocated = self.capital * CONFIG["risk_per_trade_pct"]
        quantity = capital_allocated / entry_price

        self.position = Position(
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            capital=capital_allocated,
            rsi10=rsi10
        )

        self.telegram.report_trade_open(symbol, entry_price, rsi10, capital_allocated)
        log.info(f"✅ COMPRA: {symbol} @ ${entry_price:.2f} | RSI={rsi10:.1f}")
        return True

    def close_trade_now(self):
        if not self.position:
            return

        pnl_usd = self.position.quantity * (self.position.exit_price - self.position.entry_price)
        self.capital += pnl_usd

        self.telegram.report_trade_close(
            self.position.symbol,
            self.position.entry_price,
            self.position.exit_price,
            self.position.pnl_pct,
            self.position.exit_reason
        )

        log.info(
            f"✅ VENTA: {self.position.symbol} @ ${self.position.exit_price:.2f} | "
            f"PnL: {self.position.pnl_pct:+.2f}% | Capital actual: ${self.capital:,.2f}"
        )

        self.trades_history.append(self.position)
        self.position = None

    def check_market_hours(self) -> bool:
        now = datetime.now()
        hour = now.hour - 3  # Ajustar para EST
        
        if now.weekday() >= 5:  # Weekend
            return False
        
        return 9 <= hour <= 16

    def run_live(self):
        log.info("🚀 MODO LIVE: Monitoreando mercado...")
        
        while True:
            try:
                now = datetime.now()
                
                if not self.check_market_hours():
                    log.info(f"⏰ Mercado cerrado")
                    time.sleep(300)
                    continue
                
                # Revisar posición abierta
                if self.position:
                    price = self.data_manager.get_current_price_now(self.position.symbol)
                    if price is not None and isinstance(price, (int, float)):
                        if self.position.check_exit_now(float(price), now.hour):
                            self.close_trade_now()
                
                # Buscar nueva oportunidad
                if not self.position:
                    symbol, rsi, price = self.data_manager.find_most_oversold_now()
                    if symbol is not None and price is not None and price > 0:
                        price = float(price)
                        rsi = float(rsi)
                        log.info(f"📊 {symbol} oversold (RSI={rsi:.1f}) @ ${price:.2f}")
                        self.open_trade_now(symbol, price, rsi)
                
                log.info(f"⏰ Siguiente check en {CONFIG['check_interval_minutes']} min")
                time.sleep(CONFIG['check_interval_minutes'] * 60)
                
            except Exception as e:
                log.error(f"❌ Error: {e}", exc_info=True)
                self.telegram.report_status(f"⚠️ Error: {str(e)}")
                time.sleep(60)


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    try:
        bot = S500BotLive()
        bot.run_live()
    except KeyboardInterrupt:
        log.info("⏸️  Bot detenido")
    except Exception as e:
        log.error(f"❌ Error fatal: {e}", exc_info=True)


if __name__ == "__main__":
    main()
