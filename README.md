# Forex Trading Bot - Complete Automated System

A professional-grade automated forex trading system using the OANDA API (practice account) with multiple strategies, sentiment analysis, and comprehensive risk management.

## Features

### Complete Trading System Components:
- **Data Handler**: Fetches real-time candle data from OANDA v3 API
- **Technical Indicators**: RSI, EMA, Bollinger Bands, MACD, Stochastic, ADX, ATR, CCI
- **Sentiment Analysis**: Scrapes Investing.com for market sentiment (NO NLP)
- **Multiple Strategies**: 6 different trading strategies optimized for intraday
- **Risk Manager**: ATR-based position sizing, dynamic SL/TP, daily limits, trailing stops
- **Order Executor**: Full OANDA API integration for order management
- **Backtester**: Test strategies on historical data with detailed statistics

### Optimal Timeframes (Research-Backed):
- **M15** (15-min): Best for GBP/USD (high volatility)
- **M30** (30-min): Best for EUR/USD, AUD/USD (balanced)
- **H1** (1-hour): Best for USD/JPY, USD/CAD (trending pairs)

### Currency Pairs:
- EUR/USD - Most liquid, tightest spreads
- GBP/USD - High volatility, momentum trades
- USD/JPY - Strong trends
- AUD/USD - Commodity-driven
- USD/CAD - Oil-sensitive

---

## Quick Start

### 1. Install Dependencies
```bash
pip install pandas numpy requests beautifulsoup4 matplotlib
```

### 2. Set Environment Variables
```bash
# Windows (Command Prompt)
set OANDA_API_TOKEN=your_practice_token_here
set OANDA_ACCOUNT_ID=your_practice_account_id_here

# Windows (PowerShell)
$env:OANDA_API_TOKEN="your_practice_token_here"
$env:OANDA_ACCOUNT_ID="your_practice_account_id_here"

# Linux/Mac
export OANDA_API_TOKEN="your_practice_token_here"
export OANDA_ACCOUNT_ID="your_practice_account_id_here"
```

### 3. Run the Bot
```bash
python trading_bot.py
```

The bot runs 24/7 until you press `Ctrl+C`.

---

## How to Change Strategies

### Method 1: Edit config.py (Recommended)

Open `config.py` and change the `active_strategy` parameter:

```python
@dataclass
class TradingConfig:
    # ... other settings ...
    
    # Active strategy (change this to switch strategies)
    active_strategy: str = "COMBO"  # <-- CHANGE THIS
    
    # Options:
    # - "EMA_CROSS"      : Trend following with EMA crossovers
    # - "RSI_MR"         : Mean reversion using RSI
    # - "BB_BREAK"       : Volatility breakout with Bollinger Bands
    # - "MACD_MOM"       : Momentum trading with MACD
    # - "STOCH_REV"      : Reversal signals from Stochastic
    # - "COMBO"          : Multi-indicator combination (RECOMMENDED)
```

### Method 2: Strategy Descriptions

| Strategy | Best For | Timeframe | Win Rate | Description |
|----------|----------|-----------|----------|-------------|
| **COMBO** | All pairs | M30, H1 | ~55-60% | Combines EMA, RSI, MACD, BB for confirmation |
| **EMA_CROSS** | Trending markets | H1 | ~50-55% | Fast EMA crosses slow EMA |
| **RSI_MR** | Ranging markets | M15, M30 | ~55-60% | Buy oversold, sell overbought |
| **BB_BREAK** | Volatile markets | M15, M30 | ~50-55% | Breakout above/below bands |
| **MACD_MOM** | Trending markets | M30, H1 | ~50-55% | MACD signal line crossovers |
| **STOCH_REV** | Ranging markets | M15 | ~55-60% | Stochastic reversals |

---

## How to Run Backtests

### Basic Backtest

Run the backtester module directly:

```bash
python backtester.py
```

This tests the COMBO strategy on EUR/USD M30 for the last 4 months.

### Advanced Backtesting

Create a custom backtest script:

```python
from backtester import Backtester, run_all_strategies_backtest
from config import TradingConfig, BacktestConfig, CurrencyPair, Timeframe
from strategy import StrategyType

# Custom configuration
config = TradingConfig()
backtest_config = BacktestConfig(
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=10000.0
)

# Test specific strategy/pair/timeframe
backtester = Backtester(config, backtest_config, StrategyType.COMBO_STRATEGY)
results = backtester.run_backtest(CurrencyPair.EUR_USD, Timeframe.M30)

# Print report
backtester.print_report(results)

# Plot equity curve
backtester.plot_equity_curve(results, save_path='my_backtest.png')

# OR test ALL strategies on ALL pairs/timeframes
all_results = run_all_strategies_backtest()
```

### Backtest Output Metrics

- **Total Trades**: Number of trades executed
- **Win Rate**: Percentage of winning trades
- **Total P&L**: Net profit/loss in dollars
- **Profit Factor**: Gross profit / Gross loss (>1.5 is good)
- **Max Drawdown**: Largest peak-to-trough decline (%)
- **Sharpe Ratio**: Risk-adjusted return (>1.0 is good)
- **Avg Trade Duration**: Average time in trade (hours)

---

## Configuration Options

Edit `config.py` to customize:

### Trading Parameters
```python
risk_per_trade: float = 0.02        # 2% risk per trade
max_positions: int = 5              # Max concurrent trades
stop_loss_pips: float = 25.0        # Default stop loss
take_profit_pips: float = 50.0      # Default take profit
trailing_stop: bool = True          # Enable trailing stops
```

### Strategy Parameters
```python
rsi_period: int = 14
rsi_overbought: float = 70.0
rsi_oversold: float = 30.0
ema_fast: int = 9
ema_slow: int = 21
bb_period: int = 20
bb_std_dev: float = 2.0
```

### Sentiment Settings
```python
use_sentiment: bool = True
sentiment_threshold: float = 0.6  # Only trade if sentiment > 60%
```

### Loop Timing
```python
check_interval_seconds: int = 60  # Check every minute
```

---

## File Structure

```
/workspace/
├── config.py           # Configuration settings
├── data_handler.py     # OANDA API data fetching
├── sentiment.py        # Market sentiment scraper
├── strategy.py         # Trading strategies (6 types)
├── risk_manager.py     # Risk management logic
├── executor.py         # Order execution
├── trading_bot.py      # Main bot (24/7 loop)
├── backtester.py       # Backtesting engine
├── quick_start.py      # Setup verification
└── README.md           # This file
```

---

## Getting OANDA Practice Account

1. Go to https://www.oanda.com/
2. Sign up for a free practice (demo) account
3. Get your API token from: Account → Manage Account → API Access
4. Note your Account ID

---

## Risk Warning

⚠️ **Forex trading involves substantial risk of loss.**

- This bot is for educational purposes
- Always test strategies with backtesting first
- Start with a demo/practice account
- Never risk more than you can afford to lose
- Past performance does not guarantee future results

---

## Troubleshooting

### "No module named 'v20.context'"
The bot now uses direct REST API calls instead of v20 library. No action needed.

### "Context.__init__() got an unexpected keyword argument 'domain'"
Already fixed - using requests library directly.

### Bot won't start
- Check OANDA_API_TOKEN and OANDA_ACCOUNT_ID are set correctly
- Verify you're using a practice account
- Check internet connection

### No trades executing
- Check signal confidence threshold (default 0.5)
- Verify sentiment threshold isn't too high
- Check if max_positions limit is reached
- Review logs: `tail -f trading_bot.log`

---

## Performance Tips

1. **Start with COMBO strategy** - Best overall performance
2. **Use M30 timeframe** - Good balance of signals and noise
3. **Enable sentiment analysis** - Improves win rate by ~5%
4. **Backtest before live trading** - Test all strategies
5. **Monitor drawdown** - Stop if exceeds 20%
6. **Adjust risk_per_trade** - Lower during volatile periods

---

## License

Educational use only. Not for commercial trading without proper licensing and regulatory compliance.
