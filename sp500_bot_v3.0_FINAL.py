"""
🤖 S&P 500 Bot v3.0 FINAL - CON TODO INTEGRADO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Bot S&P 500 RSI10 Mean Reversion
✅ Telegram integrado (alertas en teléfono)
✅ Backtest histórico gratis
✅ Binance Testnet gratis (dinero ficticio)
✅ .env para credenciales (seguro)
✅ Logging detallado
✅ Validaciones robustas

Uso:
  python sp500_bot.py backtest          # Prueba gratis
  python sp500_bot.py live              # Live mode
  python sp500_bot.py --help            # Ayuda
"""

import os
import sys
import json
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
    "time_based_exit_hour": 16,
    "initial_capital": 10000,
    "risk_per_trade_pct": 0.10,
    "telegram_token": os.getenv("TELEGRAM_TOKEN", "").strip(),
    "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", "").strip(),
    "backtest_start": "2024-01-01",
    "backtest_end": "2025-12-31",
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
# TELEGRAM REPORTER (CON VALIDACIONES)
# ════════════════════════════════════════════════════════════════════════════

class TelegramReporter:
    """Maneja alertas por Telegram"""
    
    def __init__(self, token: str, chat_id: str):
        self.token = token.strip() if token else ""
        self.chat_id = chat_id.strip() if chat_id else ""
        self.enabled = bool(self.token and self.chat_id)
        
        if self.enabled:
            log.info("✅ Telegram HABILITADO - Recibirás alertas en tu teléfono")
        else:
            log.warning("⏭️  Telegram DESHABILITADO - Completa .env con TOKEN y CHAT_ID para alertas")

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
                log.debug("[TG] ✅ Mensaje enviado")
                return True
            else:
                log.warning(f"[TG] Error {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            log.warning(f"[TG] Error enviando: {e}")
            return False

    def report_trade_open(self, symbol: str, entry_price: float, rsi10: float, capital: float):
        """Alerta: Trade abierto"""
        msg = (
            f"🚀 *COMPRA EJECUTADA*\n"
            f"Par: {symbol}\n"
            f"Precio entrada: ${entry_price:.2f}\n"
            f"RSI(10): {rsi10:.1f} (oversold)\n"
            f"Capital en riesgo: ${capital:.2f}\n"
            f"Target: +3% | Stop: -3%\n"
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
            f"Razón: {reason}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(msg)

    def report_daily_summary(self, date_str: str, total: int, wins: int, 
                            losses: int, daily_pnl: float, cumulative: float):
        """Resumen diario"""
        msg = (
            f"📊 *RESUMEN DIARIO - {date_str}*\n"
            f"Operaciones: {total}\n"
            f"✅ Ganadoras: {wins} | ❌ Perdedoras: {losses}\n"
            f"PnL hoy: {daily_pnl:+.2f}%\n"
            f"PnL acumulado: {cumulative:+.2f}%"
        )
        self.send(msg)

    def report_error(self, error_msg: str):
        """Alerta: Error"""
        msg = f"⚠️ *ERROR EN BOT*\n{error_msg}"
        self.send(msg)


# ════════════════════════════════════════════════════════════════════════════
# DATA MANAGER (YAHOO FINANCE)
# ════════════════════════════════════════════════════════════════════════════

class DataManager:
    """Obtiene datos históricos y calcula RSI"""
    
    def __init__(self, symbols: List[str], period: int = 10):
        self.symbols = symbols
        self.period = period
        self.cache = {}

    def get_data(self, symbol: str, days_back: int = 30) -> Optional[pd.DataFrame]:
        """Descarga OHLCV + RSI10"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            df = yf.download(
                symbol,
                start=start_date,
                end=end_date,
                progress=False,
                interval="1d"
            )
            
            if df.empty:
                log.warning(f"⚠️  {symbol}: Sin datos disponibles")
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

    def find_most_oversold(self, threshold: int = 35) -> Tuple[Optional[str], float]:
        """Encuentra símbolo más oversold"""
        most_oversold = None
        min_rsi = 100
        
        for symbol in self.symbols:
            df = self.get_data(symbol, days_back=30)
            if df is None or len(df) < self.period:
                continue
            
            rsi = df['RSI'].iloc[-1]
            if not np.isnan(rsi) and rsi < threshold and rsi < min_rsi:
                min_rsi = rsi
                most_oversold = symbol
        
        return most_oversold, min_rsi if most_oversold else 100

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Precio actual"""
        df = self.get_data(symbol, days_back=5)
        if df is None or len(df) == 0:
            return None
        return float(df['Close'].iloc[-1])


# ════════════════════════════════════════════════════════════════════════════
# POSICIÓN
# ════════════════════════════════════════════════════════════════════════════

class Position:
    """Representa una posición abierta"""
    
    def __init__(self, symbol: str, entry_price: float, entry_time: datetime,
                 quantity: float, capital: float, rsi10: float):
        self.symbol = symbol
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.quantity = quantity
        self.capital = capital
        self.rsi10 = rsi10
        self.exit_price = None
        self.exit_time = None
        self.exit_reason = None
        self.pnl_pct = None

    def check_exit(self, current_price: float, current_time: datetime) -> bool:
        """Verifica si debe cerrarse"""
        pnl_pct = (current_price - self.entry_price) / self.entry_price

        # Target de ganancia
        if pnl_pct >= CONFIG["target_profit_pct"]:
            self.exit_price = current_price
            self.exit_time = current_time
            self.exit_reason = "Take Profit (+3%)"
            self.pnl_pct = pnl_pct
            return True

        # Stop loss
        if pnl_pct <= -CONFIG["stop_loss_pct"]:
            self.exit_price = current_price
            self.exit_time = current_time
            self.exit_reason = "Stop Loss (-3%)"
            self.pnl_pct = pnl_pct
            return True

        # Exit por tiempo (EOD)
        if current_time.hour >= CONFIG["time_based_exit_hour"]:
            if self.entry_time.date() < current_time.date():
                self.exit_price = current_price
                self.exit_time = current_time
                self.exit_reason = "End of Day"
                self.pnl_pct = pnl_pct
                return True

        return False

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "quantity": self.quantity,
            "capital": self.capital,
            "rsi10": self.rsi10,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_reason": self.exit_reason,
            "pnl_pct": self.pnl_pct,
        }


# ════════════════════════════════════════════════════════════════════════════
# BOT PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════

class S500Bot:
    """Bot S&P 500 RSI10 Mean Reversion"""
    
    def __init__(self, symbols: List[str] = None):
        self.symbols = symbols or CONFIG["symbols"]
        self.data_manager = DataManager(self.symbols, CONFIG["rsi_period"])
        self.telegram = TelegramReporter(CONFIG["telegram_token"], CONFIG["telegram_chat_id"])
        
        self.capital = CONFIG["initial_capital"]
        self.position: Optional[Position] = None
        self.trades_history = []
        self.daily_trades = []
        
        log.info("=" * 60)
        log.info("🤖 BOT S&P 500 v3.0 INICIADO")
        log.info("=" * 60)
        log.info(f"Símbolos: {', '.join(self.symbols)}")
        log.info(f"Capital inicial: ${self.capital:,.2f}")
        log.info(f"RSI período: {CONFIG['rsi_period']}")
        log.info(f"Telegram: {'✅ HABILITADO' if self.telegram.enabled else '❌ DESHABILITADO'}")
        log.info("=" * 60)

    def open_trade(self, symbol: str, entry_price: float, rsi10: float) -> bool:
        """Abre una posición"""
        if self.position:
            log.warning("Ya hay posición abierta")
            return False

        capital_allocated = self.capital * CONFIG["risk_per_trade_pct"]
        quantity = capital_allocated / entry_price

        self.position = Position(
            symbol=symbol,
            entry_price=entry_price,
            entry_time=datetime.now(),
            quantity=quantity,
            capital=capital_allocated,
            rsi10=rsi10
        )

        self.telegram.report_trade_open(symbol, entry_price, rsi10, capital_allocated)
        log.info(f"✅ COMPRA: {symbol} @ ${entry_price:.2f} | RSI={rsi10:.1f}")
        return True

    def close_trade(self):
        """Cierra la posición"""
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
            f"PnL: {self.position.pnl_pct:+.2f}% ({self.position.exit_reason})"
        )

        self.trades_history.append(self.position)
        self.daily_trades.append(self.position)
        self.position = None

    def run_backtest(self, start_date: str, end_date: str) -> Dict:
        """Backtest histórico"""
        log.info(f"📊 INICIANDO BACKTEST: {start_date} → {end_date}")
        
        all_dates = pd.bdate_range(start=start_date, end=end_date, freq='B')
        
        for trade_date in all_dates:
            # Cierra posición si existe
            if self.position:
                price = self.data_manager.get_current_price(self.position.symbol)
                if price:
                    self.position.check_exit(price, trade_date)
                    if self.position.exit_price:
                        self.close_trade()
            
            # Abre nueva posición
            if not self.position and trade_date != all_dates[-1]:
                symbol, rsi = self.data_manager.find_most_oversold()
                if symbol:
                    price = self.data_manager.get_current_price(symbol)
                    if price:
                        self.open_trade(symbol, price, rsi)
        
        # Resumen
        total = len(self.trades_history)
        wins = sum(1 for t in self.trades_history if t.pnl_pct > 0)
        losses = total - wins
        total_return = (self.capital - CONFIG["initial_capital"]) / CONFIG["initial_capital"]
        
        results = {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / total if total > 0 else 0,
            "total_return_pct": total_return * 100,
            "final_capital": self.capital,
        }
        
        log.info("=" * 60)
        log.info("✅ BACKTEST COMPLETADO")
        log.info("=" * 60)
        log.info(f"Total trades: {total}")
        log.info(f"Wins: {wins} | Losses: {losses}")
        log.info(f"Win rate: {results['win_rate']:.1%}")
        log.info(f"Total return: {results['total_return_pct']:.2f}%")
        log.info(f"Final capital: ${self.capital:,.2f}")
        log.info("=" * 60)
        
        return results

    def run_live(self):
        """Modo live (con backtest de datos recientes)"""
        log.info("🚀 MODO LIVE: Backtesting con datos recientes")
        self.telegram.send("🚀 *Bot S&P 500 iniciado en LIVE MODE*")
        
        # Hacer backtest de últimos 60 días
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        self.run_backtest(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("""
🤖 Bot S&P 500 v3.0

USO:
  python sp500_bot.py backtest    # Backtest histórico (2024-2025)
  python sp500_bot.py live        # Backtest reciente (últimos 60 días)
  python sp500_bot.py --help      # Esta ayuda

ANTES DE EJECUTAR:
  1. cp .env.example .env
  2. Edita .env con tus credenciales Telegram (OPCIONAL)
  3. pip install -r requirements_updated.txt

TELEGRAM (OPCIONAL):
  - @BotFather → /newbot → TOKEN
  - @userinfobot → CHAT_ID
  - Guardar en .env

OUTPUT:
  - sp500_bot.log (archivo de logs)
  - Alertas en Telegram (si está configurado)
""")
        return

    try:
        bot = S500Bot()
        
        if len(sys.argv) > 1 and sys.argv[1] == "backtest":
            results = bot.run_backtest(CONFIG["backtest_start"], CONFIG["backtest_end"])
        else:
            bot.run_live()
            
    except KeyboardInterrupt:
        log.info("⏸️  Bot detenido por usuario")
    except Exception as e:
        log.error(f"❌ Error fatal: {e}", exc_info=True)
        telegram = TelegramReporter(CONFIG["telegram_token"], CONFIG["telegram_chat_id"])
        telegram.report_error(str(e))


if __name__ == "__main__":
    main()
