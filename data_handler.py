"""
Data Handler Module - Fetches and processes market data from OANDA API
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import talib

from config import OandaConfig, Timeframe, CurrencyPair


logger = logging.getLogger(__name__)


class DataHandler:
    """Handles all data fetching and processing from OANDA API"""
    
    def __init__(self, config: OandaConfig):
        self.config = config
        self.ctx = None
        self._initialize_api()
    
    def _initialize_api(self):
        """Initialize OANDA API context"""
        try:
            from v20.context import Context
            self.ctx = Context(
                domain=self.config.hostname,
                token=self.config.api_token
            )
            logger.info("OANDA API context initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OANDA API: {e}")
            raise
    
    def get_candles(self, instrument: str, timeframe: Timeframe, 
                    count: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetch candlestick data from OANDA
        
        Args:
            instrument: Currency pair (e.g., "EUR_USD")
            timeframe: Timeframe enum
            count: Number of candles to fetch
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            response = self.ctx.instrument.candles(
                instrument=instrument,
                granularity=timeframe.value,
                count=count
            )
            
            candles = []
            for candle in response.get("candles", []):
                if candle.type == "MID":
                    candles.append({
                        'timestamp': pd.to_datetime(candle.time),
                        'open': float(candle.mid.o),
                        'high': float(candle.mid.h),
                        'low': float(candle.mid.l),
                        'close': float(candle.mid.c),
                        'volume': int(candle.volume)
                    })
            
            if not candles:
                return None
                
            df = pd.DataFrame(candles)
            df.set_index('timestamp', inplace=True)
            return df
            
        except Exception as e:
            logger.error(f"Error fetching candles for {instrument}: {e}")
            return None
    
    def get_current_price(self, instrument: str) -> Optional[Dict]:
        """Get current bid/ask prices for an instrument"""
        try:
            response = self.ctx.pricing.get(
                accountID=self.config.account_id,
                instruments=instrument
            )
            
            for price in response.get("prices", []):
                if price.instrument == instrument:
                    return {
                        'bid': float(price.bids[0].price),
                        'ask': float(price.asks[0].price),
                        'spread': float(price.asks[0].price) - float(price.bids[0].price),
                        'timestamp': pd.to_datetime(price.time)
                    }
            return None
            
        except Exception as e:
            logger.error(f"Error fetching price for {instrument}: {e}")
            return None
    
    def get_account_info(self) -> Optional[Dict]:
        """Get current account information"""
        try:
            response = self.ctx.account.get(
                accountID=self.config.account_id
            )
            account = response.get("account", {})
            return {
                'balance': float(account.balance),
                'nav': float(account.nav),
                'margin_used': float(account.marginUsed),
                'margin_available': float(account.marginAvailable),
                'position_count': len(account.positions),
                'open_trade_count': account.openTradeCount
            }
        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
            return None
    
    def calculate_technical_indicators(self, df: pd.DataFrame, 
                                       config) -> pd.DataFrame:
        """
        Calculate technical indicators on price data
        
        Args:
            df: DataFrame with OHLCV data
            config: Trading configuration
            
        Returns:
            DataFrame with added technical indicators
        """
        if df is None or len(df) < config.bb_period + config.atr_period:
            return df
        
        # Extract arrays for TA-Lib
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        open_price = df['open'].values
        
        # RSI
        df['rsi'] = talib.RSI(close, timeperiod=config.rsi_period)
        
        # EMAs
        df['ema_fast'] = talib.EMA(close, timeperiod=config.ema_fast)
        df['ema_slow'] = talib.EMA(close, timeperiod=config.ema_slow)
        
        # Bollinger Bands
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
            close, 
            timeperiod=config.bb_period,
            nbdevup=config.bb_std_dev,
            nbdevdn=config.bb_std_dev
        )
        
        # ATR (Average True Range)
        df['atr'] = talib.ATR(high, low, close, timeperiod=config.atr_period)
        
        # MACD
        df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
            close,
            fastperiod=12,
            slowperiod=26,
            signalperiod=9
        )
        
        # Stochastic
        df['stoch_k'], df['stoch_d'] = talib.STOCH(
            high, low, close,
            fastk_period=14,
            slowk_period=3,
            slowd_period=3
        )
        
        # ADX (Trend strength)
        df['adx'] = talib.ADX(high, low, close, timeperiod=14)
        
        # CCI (Commodity Channel Index)
        df['cci'] = talib.CCI(high, low, close, timeperiod=20)
        
        return df
    
    def get_multiple_timeframes(self, instrument: str, 
                                timeframes: List[Timeframe]) -> Dict:
        """Fetch data for multiple timeframes"""
        data = {}
        for tf in timeframes:
            df = self.get_candles(instrument, tf)
            if df is not None:
                data[tf] = df
        return data
    
    def get_pip_value(self, instrument: str) -> float:
        """Get pip value for an instrument"""
        # Major pairs pip calculation
        if 'JPY' in instrument:
            return 0.01
        else:
            return 0.0001
