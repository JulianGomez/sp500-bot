"""
🤖 S&P 500 Bot v3.1 - OPERANDO EN VIVO CON DATOS REALES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Bot S&P 500 RSI10 Mean Reversion
✅ Analiza precios REALES ahora
✅ Abre/cierra trades EN VIVO (sin dinero real, pero con lógica real)
✅ Telegram integrado (alertas instantáneas)
✅ Corre continuamente en Railway
✅ Aprendizaje día a día

Uso:
  python sp500_bot_v3.1_LIVE_REAL.py live    # Modo LIVE real (recomendado)
  python sp500_bot_v3.1_LIVE_REAL.py --help  # Ayuda
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
# CONFIG Y SETUP
# ════════════════════════════════════════════════════════════════════════════

CONFIG = {
    "symbols": ["VLO", "AMAT", "EOG", "MOS", "COST", "EQIX", "GILD"],
    "rsi_period": 10,
    "oversold_threshold": 35,
    "target_profit_pct": 0.03,
    "stop_loss_pct": 0.03,
    "time_based_exit_hour": 16,  # 4 PM EST (cierre NYSE)
    "initial_capital": 10000,
    "risk_per_trade_pct": 0.10,
    "telegram_token": os.getenv("TELEGRAM_TOKEN", "").strip(),
    "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", "").strip(),
    "check_interval_minutes": 30,  # Revisar cada 30 minutos durante horario de mercado
}

# Logging setup
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
# TELEGRAM REPORTER
# ════════════════════════════════════════════════════════════════════════════

class TelegramReporter:
    """Maneja alertas por Telegram"""
    
    def __init__(self, token: str, chat_id: str):
        self.token = token.strip() if token else ""
        self.chat_id = chat_id.strip() if chat_id else ""
        self.enabled = bool(self.token and self.chat_id)
        
        if self.enabled:
            log.info("✅ Telegram HABILITADO")
        else:
            log.warning("⏭️  Telegram DESHABILITADO")

    def send(self, msg: str) -> bool:
        """Envía mensaje a Telegram"""
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
            
            if response.status_code == 200:
                log.debug("[TG] ✅ Enviado")
                return True
            else:
                log.warning(f"[TG] Error {response.status_code}")
                return False
                
        except Exception as e:
            log.warning(f"[TG] Error: {e}")
            return False

    def report_trade_open(self, symbol: str, entry_price: float, rsi10: float, capital: float):
        """Alerta: Trade abierto"""
        msg = (
            f"🚀 *COMPRA EJECUTADA*\n"
            f"Par: {symbol}\n"
            f"Precio: ${entry_price:.2f}\n"
            f"RSI(10): {rsi10:.1f}\n"
            f"Capital: ${capital:.2f}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(msg)

    def report_trade_close(self, symbol: str, entry: float, exit_price: float, 
                          pnl_pct: float, reason: str):
        """Alerta: Trade cerrado"""
        emoji = "✅" if pnl_pct > 0 else "❌"
        msg = (
            f"{emoji} *VENTA EJECUTADA*\n"
            f"Par: {symbol}\n"
            f"${entry:.2f} → ${exit_price:.2f}\n"
            f"PnL: {pnl_pct:+.2f}%\n"
            f"Razón: {reason}"
        )
        self.send(msg)

    def report_status(self, msg: str):
        """Estado general"""
        self.send(msg)


# ════════════════════════════════════════════════════════════════════════════
# DATA MANAGER - DATOS EN VIVO
# ════════════════════════════════════════════════════════════════════════════

class DataManager:
    """Obtiene datos EN VIVO y calcula RSI"""
    
    def __init__(self, symbols: List[str], period: int = 10):
        self.symbols = symbols
        self.period = period
        self.cache = {}

    def get_live_data(self, symbol: str, days_back: int = 30) -> Optional[pd.DataFrame]:
        """Descarga datos ACTUALES de Yahoo Finance"""
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
            
            if df.empty:
                log.warning(f"⚠️  {symbol}: Sin datos")
                return None
            
            # Calcular RSI(10)
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            self.cache[symbol] = df
            return df
            
        except Exception as e:
            log.error(f"Error descargando {symbol}: {e}")
            return None

    def find_most_oversold_now(self, threshold: int = 35) -> Tuple[Optional[str], float, float]:
        """Encuentra símbolo más oversold AHORA"""
        most_oversold = None
        min_rsi = 100
        price = 0
        
        for symbol in self.symbols:
            df = self.get_live_data(symbol, days_back=30)
            if df is None or len(df) < self.period:
                continue
            
            rsi = df['RSI'].iloc[-1]
            current_price = df['Close'].iloc[-1]
            
            if not np.isnan(rsi) and rsi < threshold and rsi < min_rsi:
                min_rsi = rsi
                most_oversold = symbol
                price = current_price
        
        return most_oversold, min_rsi if most_oversold else 100, price

    def get_current_price_now(self, symbol: str) -> Optional[float]:
        """Precio ACTUAL ahora"""
        try:
            df = yf.download(symbol, period="1d", progress=False, auto_adjust=True)
            if df.empty:
                return None
            return float(df['Close'].iloc[-1])
        except:
            return None


# ════════════════════════════════════════════════════════════════════════════
# POSICIÓN EN VIVO
# ════════════════════════════════════════════════════════════════════════════

class Position:
    """Posición abierta EN VIVO"""
    
    def __init__(self, symbol: str, entry_price: float, quantity: float, 
                 capital: float, rsi10: float):
        self.symbol = symbol
        self.entry_price = entry_price
        self.entry_time = datetime.now()
        self.quantity = quantity
        self.capital = capital
        self.rsi10 = rsi10
        self.exit_price = None
        self.exit_time = None
        self.exit_reason = None
        self.pnl_pct = None

    def check_exit_now(self, current_price: float, current_hour: int) -> bool:
        """Verifica si debe cerrarse AHORA"""
        pnl_pct = (current_price - self.entry_price) / self.entry_price

        # Target de ganancia
        if pnl_pct >= CONFIG["target_profit_pct"]:
            self.exit_price = current_price
            self.exit_time = datetime.now()
            self.exit_reason = "Take Profit (+3%)"
            self.pnl_pct = pnl_pct
            return True

        # Stop loss
        if pnl_pct <= -CONFIG["stop_loss_pct"]:
            self.exit_price = current_price
            self.exit_time = datetime.now()
            self.exit_reason = "Stop Loss (-3%)"
            self.pnl_pct = pnl_pct
            return True

        # Exit por cierre de mercado (4 PM EST)
        if current_hour >= CONFIG["time_based_exit_hour"]:
            self.exit_price = current_price
            self.exit_time = datetime.now()
            self.exit_reason = "End of Day"
            self.pnl_pct = pnl_pct
            return True

        return False


# ════════════════════════════════════════════════════════════════════════════
# BOT LIVE - OPERANDO EN TIEMPO REAL
# ════════════════════════════════════════════════════════════════════════════

class S500BotLive:
    """Bot que opera EN VIVO con datos reales"""
    
    def __init__(self):
        self.symbols = CONFIG["symbols"]
        self.data_manager = DataManager(self.symbols, CONFIG["rsi_period"])
        self.telegram = TelegramReporter(CONFIG["telegram_token"], CONFIG["telegram_chat_id"])
        
        self.capital = CONFIG["initial_capital"]
        self.position: Optional[Position] = None
        self.trades_history = []
        self.daily_trades = []
        
        log.info("=" * 60)
        log.info("🤖 BOT S&P 500 v3.1 LIVE - OPERANDO EN VIVO")
        log.info("=" * 60)
        log.info(f"Símbolos: {', '.join(self.symbols)}")
        log.info(f"Capital: ${self.capital:,.2f}")
        log.info(f"RSI Threshold: {CONFIG['rsi_period']}")
        log.info(f"Oversold: < {CONFIG['oversold_threshold']}")
        log.info(f"Telegram: {'✅' if self.telegram.enabled else '❌'}")
        log.info("=" * 60)
        
        self.telegram.send("🚀 *Bot S&P 500 v3.1 INICIADO EN LIVE*\nOperando en tiempo real...")

    def open_trade_now(self, symbol: str, entry_price: float, rsi10: float) -> bool:
        """Abre trade AHORA"""
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
        log.info(f"✅ COMPRA EN VIVO: {symbol} @ ${entry_price:.2f} | RSI={rsi10:.1f}")
        return True

    def close_trade_now(self):
        """Cierra trade AHORA"""
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
            f"✅ VENTA EN VIVO: {self.position.symbol} @ ${self.position.exit_price:.2f} | "
            f"PnL: {self.position.pnl_pct:+.2f}% | Capital: ${self.capital:,.2f}"
        )

        self.trades_history.append(self.position)
        self.daily_trades.append(self.position)
        self.position = None

    def check_market_hours(self) -> bool:
        """Verifica si el mercado está abierto (9:30 AM - 4 PM EST)"""
        now = datetime.now()
        # EST timezone (puede variar según horario de verano)
        hour = now.hour - 3  # Ajustar según tu zona horaria
        
        # Mercado abierto: 9:30 AM - 4 PM EST (lunes-viernes)
        if now.weekday() >= 5:  # Sábado o domingo
            return False
        
        return 9 <= hour <= 16

    def run_live(self):
        """Corre EN VIVO monitoreando en tiempo real"""
        log.info("🚀 MODO LIVE: Monitoreando mercado en tiempo real...")
        
        while True:
            try:
                now = datetime.now()
                
                # Verificar horario de mercado
                if not self.check_market_hours():
                    log.info(f"⏰ Mercado cerrado. Próxima revisión: {now + timedelta(minutes=CONFIG['check_interval_minutes'])}")
                    time.sleep(300)  # Esperar 5 minutos si está cerrado
                    continue
                
                # REVISAR POSICIÓN ABIERTA
                if self.position:
                    price = self.data_manager.get_current_price_now(self.position.symbol)
                    if price:
                        if self.position.check_exit_now(price, now.hour):
                            self.close_trade_now()
                
                # BUSCAR NUEVA OPORTUNIDAD
                if not self.position:
                    symbol, rsi, price = self.data_manager.find_most_oversold_now()
                    if symbol and price > 0:
                        log.info(f"📊 {symbol} oversold (RSI={rsi:.1f}) @ ${price:.2f}")
                        self.open_trade_now(symbol, price, rsi)
                
                # Esperar antes de siguiente revisión
                log.info(f"⏰ Siguiente revisión en {CONFIG['check_interval_minutes']} min ({now.strftime('%H:%M')})")
                time.sleep(CONFIG['check_interval_minutes'] * 60)
                
            except Exception as e:
                log.error(f"❌ Error: {e}", exc_info=True)
                self.telegram.report_status(f"⚠️ Error en bot: {str(e)}")
                time.sleep(60)


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("""
🤖 Bot S&P 500 v3.1 - LIVE TRADING

USO:
  python sp500_bot_v3.1_LIVE_REAL.py live    # ⭐ Operar EN VIVO
  python sp500_bot_v3.1_LIVE_REAL.py --help  # Ayuda

CARACTERISTICAS:
  ✅ Analiza precios REALES ahora
  ✅ Abre/cierra trades EN VIVO
  ✅ Monitorea cada 30 minutos (9:30 AM - 4 PM EST)
  ✅ Sin dinero real (pero con lógica real)
  ✅ Telegram alertas instantáneas

BEFORE:
  1. cp .env.example .env
  2. Edita .env con TELEGRAM_TOKEN y TELEGRAM_CHAT_ID
  3. pip install -r requirements.txt

LOGS:
  sp500_bot.log (archivo de log)
""")
        return

    try:
        bot = S500BotLive()
        bot.run_live()
            
    except KeyboardInterrupt:
        log.info("⏸️  Bot detenido por usuario")
    except Exception as e:
        log.error(f"❌ Error fatal: {e}", exc_info=True)
        telegram = TelegramReporter(CONFIG["telegram_token"], CONFIG["telegram_chat_id"])
        telegram.report_status(f"❌ Bot detenido: {str(e)}")


if __name__ == "__main__":
    main()
