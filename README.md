# Forex Trading Bot

A complete automated forex trading system using the OANDA API (practice account) with multiple trading strategies, risk management, and sentiment analysis.

## Features

### Complete Trading System Components

1. **Data Handler** (`data_handler.py`)
   - Fetches candlestick data from OANDA API
   - Calculates technical indicators (RSI, EMA, Bollinger Bands, MACD, Stochastic, ADX, ATR, CCI)
   - Supports multiple timeframes (M5, M15, M30, H1)
   - Real-time price fetching

2. **Sentiment Analyzer** (`sentiment.py`)
   - Fetches market sentiment from Investing.com (web scraping, no NLP)
   - Combines multiple sentiment sources
   - Returns sentiment scores (-1 to 1)
   - Filters trades based on sentiment alignment

3. **Trading Strategies** (`strategy.py`)
   - **EMA Crossover**: Trend following strategy
   - **RSI Mean Reversion**: For ranging markets
   - **Bollinger Bands Breakout**: Volatility-based
   - **MACD Momentum**: Momentum confirmation
   - **Stochastic Reversal**: Reversal patterns
   - **Combo Strategy** (Recommended): Multi-indicator confirmation

4. **Risk Manager** (`risk_manager.py`)
   - Dynamic position sizing based on ATR
   - Stop loss and take profit calculation
   - Maximum daily/weekly loss limits
   - Maximum drawdown protection
   - Trailing stop support
   - Portfolio risk monitoring

5. **Order Executor** (`executor.py`)
   - Market order execution
   - Pending orders (LIMIT/STOP)
   - Trade modification (stop loss updates)
   - Position closing
   - Trailing stop updates

6. **Main Bot** (`trading_bot.py`)
   - 24/7 continuous operation
   - Graceful shutdown handling
   - Automatic trade logging
   - Performance tracking
   - Daily counter resets

## Optimal Configuration

### Recommended Timeframes (Research-Based)
- **EUR/USD**: M30 (30-minute) - Best liquidity, consistent patterns
- **GBP/USD**: M15 (15-minute) - Higher volatility, faster moves
- **USD/JPY**: H1 (1-hour) - Trending behavior
- **AUD/USD**: M30 (30-minute) - Commodity-driven

### Why These Timeframes?
- **M15-M30**: Best balance between signal quality and trade frequency for intraday
- **H1**: Better for trending pairs, fewer false signals
- Avoids M5 (too much noise) and lower timeframes

### Recommended Currency Pairs
1. **EUR/USD** - Most liquid, tightest spreads
2. **GBP/USD** - High volatility, good for momentum
3. **USD/JPY** - Strong trends, good for breakout strategies
4. **AUD/USD** - Commodity-sensitive, range-bound tendencies

## Installation

```bash
pip install v20 requests beautifulsoup4 lxml pandas numpy ta-lib
```

## Configuration

Set environment variables:

```bash
export OANDA_API_TOKEN="your_practice_account_token"
export OANDA_ACCOUNT_ID="your_practice_account_id"
```

Or edit `config.py` directly.

## Usage

### Start the Bot

```bash
python trading_bot.py
```

The bot will:
1. Initialize all components
2. Connect to OANDA practice API
3. Start the 24/7 trading loop
4. Check all configured pairs every 60 seconds
5. Execute trades when conditions are met

### Stop the Bot

Press `Ctrl+C` to gracefully stop the bot.

## Configuration Options

Edit `config.py` to customize:

```python
@dataclass
class TradingConfig:
    # Timeframes
    primary_timeframe: Timeframe = Timeframe.M30
    secondary_timeframe: Timeframe = Timeframe.M15
    
    # Risk Management
    risk_per_trade: float = 0.02  # 2% per trade
    max_positions: int = 5
    stop_loss_pips: float = 25.0
    take_profit_pips: float = 50.0
    trailing_stop: bool = True
    
    # Strategy Parameters
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    ema_fast: int = 9
    ema_slow: int = 21
    
    # Sentiment
    use_sentiment: bool = True
    sentiment_threshold: float = 0.6
    
    # Loop Timing
    check_interval_seconds: int = 60
```

## Trading Logic

The Combo Strategy (default) requires:
1. **Trend confirmation** (EMA + ADX)
2. **Momentum signal** (RSI or MACD)
3. **Sentiment alignment** (optional boost)

A trade is executed when:
- At least 2 out of 3 signals agree
- Confidence > 50%
- Risk checks pass
- No existing position in the pair
- Sentiment doesn't contradict (if enabled)

## Risk Management

- **Position Sizing**: Based on ATR and account balance
- **Stop Loss**: Dynamic (ATR-based) or fixed
- **Take Profit**: 2:1 risk-reward ratio minimum
- **Daily Loss Limit**: 5% maximum
- **Weekly Loss Limit**: 10% maximum
- **Max Drawdown**: 15% protection
- **Max Concurrent Positions**: 5

## Logging

All activity is logged to:
- Console (real-time)
- `trading_bot.log` file (persistent)

Log levels:
- INFO: Trade executions, account status
- DEBUG: Signal generation details
- WARNING: Data issues, skipped trades
- ERROR: Execution failures

## Files Structure

```
/workspace/
├── config.py           # Configuration settings
├── data_handler.py     # Market data and indicators
├── sentiment.py        # Sentiment analysis
├── strategy.py         # Trading strategies
├── risk_manager.py     # Risk management
├── executor.py         # Order execution
├── trading_bot.py      # Main bot orchestration
└── README.md           # This file
```

## Important Notes

1. **Practice Account Only**: This bot is configured for OANDA practice accounts by default
2. **No Financial Advice**: Use at your own risk
3. **Test Thoroughly**: Run in practice mode before considering live trading
4. **Monitor Regularly**: Even automated systems need supervision
5. **API Limits**: OANDA has rate limits; the bot respects these

## Getting OANDA Practice Account

1. Visit https://www.oanda.com
2. Create a free practice (demo) account
3. Get your API token from account settings
4. Note your account ID

## Strategies Explained

### Combo Strategy (Recommended)
Combines multiple indicators for higher confidence:
- EMA crossover for trend direction
- ADX for trend strength (>20 confirms trend)
- RSI for momentum (<40 oversold, >60 overbought)
- MACD for additional confirmation
- Sentiment score for market bias

Best for: All market conditions, most reliable

### EMA Crossover
Simple trend-following:
- Buy when fast EMA crosses above slow EMA
- Sell when fast EMA crosses below slow EMA
- ADX filter avoids choppy markets

Best for: Trending markets (M30, H1)

### RSI Mean Reversion
Counter-trend strategy:
- Buy when RSI < 30 (oversold)
- Sell when RSI > 70 (overbought)
- Works best in ranging markets

Best for: Ranging markets (M15, M30)

## Performance Optimization

The bot is optimized for:
- Low latency (minimal API calls)
- Memory efficiency (pandas DataFrames)
- Error resilience (continues on failures)
- Clean shutdown (signal handlers)

## Troubleshooting

**Bot won't start:**
- Check API token and account ID
- Verify internet connection
- Check OANDA API status

**No trades executing:**
- Lower confidence threshold in config
- Check if markets are open (forex is 24/5)
- Verify sentiment isn't filtering all trades
- Check risk limits aren't too restrictive

**Too many trades:**
- Increase confidence threshold
- Reduce check frequency
- Add more filters to strategy

## License

This code is provided for educational purposes only. Use at your own risk.
