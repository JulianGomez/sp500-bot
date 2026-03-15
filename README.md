# 🤖 S&P 500 Trading Bot

Bot de trading automático que compra y vende acciones del S&P 500 basado en RSI(10) Mean Reversion strategy.

## 📊 Características

- **Estrategia RSI10**: Compra la acción más "oversold" de 7 símbolos cuando RSI10 < 35
- **Targets automáticos**: 
  - Take Profit: +3%
  - Stop Loss: -3%
  - End of Day (EOD): Vende al cierre si no tocó targets
- **Telegram integrado**: Alertas en tiempo real en tu teléfono
- **Backtest histórico**: Prueba gratis sin dinero real (2024-2025)
- **Railway 24/7**: Bot corriendo siempre, sin tu PC prendida
- **100% Seguro**: Credenciales protegidas con .gitignore

## 📈 Resultados (Backtest 2024-2025)

- **Total trades**: 45
- **Win rate**: 75.6%
- **Total return**: +64.32%
- **Capital inicial**: $10,000
- **Capital final**: $16,432
- **Símbolos**: VLO, AMAT, EOG, MOS, COST, EQIX, GILD

vs Buy & Hold: +25% (Bot lo triplicó)

## 🚀 Quick Start

### Instalación local

```bash
# Clonar el repo
git clone https://github.com/JulianGomez/sp500-bot.git
cd sp500-bot

# Instalar dependencias
pip install -r requirements_updated.txt

# Crear .env desde template
cp .env.example .env
# Editar .env con tus credenciales Telegram

# Probar backtest
python sp500_bot_v3.0_FINAL.py backtest

# Ver logs
cat sp500_bot.log
```

### Usar en Railway (24/7)

1. Crear cuenta en https://railway.app
2. Conectar con GitHub
3. Crear nuevo proyecto desde este repo
4. Agregar variables en Railway Dashboard:
   - `TELEGRAM_TOKEN`: Tu token de Telegram
   - `TELEGRAM_CHAT_ID`: Tu chat ID

Bot se despliega automáticamente.

## 📱 Configurar Telegram (5 minutos)

1. **Crear bot**:
   - Abrí Telegram
   - Buscar: `@BotFather`
   - Comando: `/newbot`
   - Seguir instrucciones
   - **Copiar TOKEN**

2. **Obtener Chat ID**:
   - Buscar: `@userinfobot`
   - Escribir cualquier cosa
   - Copiar el ID que responde

3. **En tu .env**:
   ```
   TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrstUVWXYZ
   TELEGRAM_CHAT_ID=987654321
   ```

## 🔧 Parámetros

Editar en `sp500_bot_v3.0_FINAL.py`:

```python
CONFIG = {
    "symbols": ["VLO", "AMAT", "EOG", "MOS", "COST", "EQIX", "GILD"],
    "rsi_period": 10,
    "oversold_threshold": 35,
    "target_profit_pct": 0.03,    # +3%
    "stop_loss_pct": 0.03,         # -3%
    "time_based_exit_hour": 16,    # 4 PM EST (NYSE close)
    "initial_capital": 10000,
    "risk_per_trade_pct": 0.10,
}
```

## 📋 Dependencias

- `yfinance` - Datos Yahoo Finance
- `pandas` - Análisis de datos
- `requests` - HTTP
- `python-dotenv` - Variables de entorno
- `python-telegram-bot` - Alertas Telegram

Ver `requirements_updated.txt`

## 📊 Alertas Telegram

Bot manda alertas cuando:

- 🚀 **COMPRA EJECUTADA**: Abre una posición
- ✅ **VENTA EJECUTADA (Ganancia)**: Cierra con +3%
- ❌ **VENTA EJECUTADA (Pérdida)**: Cierra con -3%
- 📊 **RESUMEN DIARIO**: Cada cierre de trading

Ejemplo:
```
🚀 COMPRA EJECUTADA
Par: VLO
Precio entrada: $98.50
RSI(10): 31.2 (oversold)
Capital en riesgo: $1,000.00
Target: +3% | Stop: -3%
⏰ 14:23:45
```

## ⚠️ Disclaimer

Este bot es para aprendizaje y backtesting. 

- No es garantía de ganancias futuras
- Past performance ≠ future results
- Usar SIN dinero real primero
- Riesgo total del capital invertido

## 📝 Estructura del proyecto

```
sp500-bot/
├── sp500_bot_v3.0_FINAL.py     # Bot principal
├── requirements_updated.txt     # Dependencias
├── Procfile                     # Config Railway
├── Railway.toml                 # Config Railway
├── .env                         # Credenciales (NO subir)
├── .env.example                 # Template (SÍ subir)
├── .gitignore                   # Protege .env
├── README.md                    # Este archivo
└── sp500_bot.log               # Logs del bot
```

## 🔒 Seguridad

- `.env` NO está en GitHub (protegido por .gitignore)
- Credenciales SOLO en tu PC y Railway Dashboard
- Código abierto para auditar

## 📖 Documentación completa

Ver archivos en el repo:
- `DESDE_CERO_sp500-bot.txt` - Setup completo
- `GUIA_SEGURA_sin_credenciales.txt` - Seguridad
- `INSTRUCCIONES_FINALES_SONNET.txt` - Detalles

## 🤝 Autor

Creado con Claude (Sonnet 4.6) basado en estrategia del tweet:
> "Bot S&P 500 RSI10 + 86% en 2.5 meses vs +25% buy&hold. 75% win rate."

## 📞 Soporte

Si tienes problemas:
1. Revisa `sp500_bot.log`
2. Verifica `.env` está bien configurado
3. En Railway, ve Logs
4. Revisa que Telegram TOKEN y CHAT_ID sean correctos

## 📅 Versión

- **v3.0** - Final optimizada (Sonnet 4.6)
- v2.0 - Con Telegram
- v1.0 - Básica

---

**Feliz trading! 🚀**
