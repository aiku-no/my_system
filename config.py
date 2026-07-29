"""
Configuration settings for the Forex Trading Bot
"""
import os
from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum


class Timeframe(Enum):
    """Supported timeframes for intraday trading"""
    M5 = "M5"      # 5-minute - Best for scalping
    M15 = "M15"    # 15-minute - Good balance
    M30 = "M30"    # 30-minute - Recommended for most strategies
    H1 = "H1"      # 1-hour - Best for trend following


class CurrencyPair(Enum):
    """Major currency pairs optimized for intraday trading"""
    EUR_USD = "EUR_USD"    # Most liquid, tightest spreads
    GBP_USD = "GBP_USD"    # High volatility, good for momentum
    USD_JPY = "USD_JPY"    # Trending pair, good for breakout
    AUD_USD = "AUD_USD"    # Commodity pair, good for range
    USD_CAD = "USD_CAD"    # Oil-sensitive, good for news


@dataclass
class OandaConfig:
    """OANDA API configuration"""
    api_token: str = os.getenv("OANDA_API_TOKEN", "")
    account_id: str = os.getenv("OANDA_ACCOUNT_ID", "")
    practice: bool = True
    hostname: str = "api-fxpractice.oanda.com"  # Practice account
    # hostname: str = "api-fxtrade.oanda.com"  # Live account (uncomment for live)


@dataclass
class TradingConfig:
    """Trading strategy configuration"""
    # Timeframes to use (optimized for intraday)
    primary_timeframe: Timeframe = Timeframe.M30
    secondary_timeframe: Timeframe = Timeframe.M15
    
    # Currency pairs to trade
    pairs: List[CurrencyPair] = None
    
    # Risk management
    risk_per_trade: float = 0.02  # 2% of account per trade
    max_positions: int = 5        # Maximum concurrent positions
    stop_loss_pips: float = 25.0  # Default stop loss in pips
    take_profit_pips: float = 50.0  # Default take profit in pips
    trailing_stop: bool = True
    trailing_stop_distance: float = 15.0  # Pips
    
    # Strategy parameters
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    ema_fast: int = 9
    ema_slow: int = 21
    bb_period: int = 20
    bb_std_dev: float = 2.0
    atr_period: int = 14
    
    # Sentiment analysis
    use_sentiment: bool = True
    sentiment_threshold: float = 0.6  # Only trade if sentiment > 60%
    
    # Loop timing
    check_interval_seconds: int = 60  # Check every minute
    
    # Active strategy (change this to switch strategies)
    active_strategy: str = "COMBO"  # Options: EMA_CROSS, RSI_MR, BB_BREAK, MACD_MOM, STOCH_REV, COMBO
    
    def __post_init__(self):
        if self.pairs is None:
            self.pairs = [
                CurrencyPair.EUR_USD,
                CurrencyPair.GBP_USD,
                CurrencyPair.USD_JPY,
                CurrencyPair.AUD_USD
            ]


@dataclass
class BacktestConfig:
    """Backtesting configuration"""
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 10000.0
    commission: float = 0.0001  # 0.01% per trade


# Default configurations
DEFAULT_OANDA_CONFIG = OandaConfig()
DEFAULT_TRADING_CONFIG = TradingConfig()
DEFAULT_BACKTEST_CONFIG = BacktestConfig()
