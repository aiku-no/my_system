"""
Data Handler Module - Fetches and processes market data from OANDA API
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
import talib

from config import OandaConfig, Timeframe, CurrencyPair


logger = logging.getLogger(__name__)


class DataHandler:
    """Handles all data fetching and processing from OANDA API"""
    
    def __init__(self, config: OandaConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.config.api_token}',
            'Content-Type': 'application/json',
            'Accept-Datetime-Format': 'RFC3339'
        })
        self.base_url = f"https://{self.config.hostname}/v3"
        logger.info(f"DataHandler initialized for {self.config.hostname}")
    
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
            url = f"{self.base_url}/instruments/{instrument}/candles"
            params = {
                'granularity': timeframe.value,
                'count': count
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            candles = []
            for candle in data.get("candles", []):
                if candle.get("complete", True):  # Only complete candles
                    mid = candle.get("mid", {})
                    candles.append({
                        'timestamp': pd.to_datetime(candle.get("time")),
                        'open': float(mid.get("o", 0)),
                        'high': float(mid.get("h", 0)),
                        'low': float(mid.get("l", 0)),
                        'close': float(mid.get("c", 0)),
                        'volume': int(candle.get("volume", 0))
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
            url = f"{self.base_url}/accounts/{self.config.account_id}/pricing"
            params = {'instruments': instrument}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for price in data.get("prices", []):
                if price.get("instrument") == instrument:
                    bids = price.get("bids", [{}])
                    asks = price.get("asks", [{}])
                    if bids and asks:
                        bid = float(bids[0].get("price", 0))
                        ask = float(asks[0].get("price", 0))
                        return {
                            'bid': bid,
                            'ask': ask,
                            'spread': ask - bid,
                            'timestamp': pd.to_datetime(price.get("time"))
                        }
            return None
            
        except Exception as e:
            logger.error(f"Error fetching price for {instrument}: {e}")
            return None
    
    def get_account_info(self) -> Optional[Dict]:
        """Get current account information"""
        try:
            url = f"{self.base_url}/accounts/{self.config.account_id}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            account = data.get("account", {})
            return {
                'balance': float(account.get("balance", 0)),
                'nav': float(account.get("nav", 0)),
                'margin_used': float(account.get("marginUsed", 0)),
                'margin_available': float(account.get("marginAvailable", 0)),
                'position_count': len(account.get("positions", [])),
                'open_trade_count': int(account.get("openTradeCount", 0))
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
