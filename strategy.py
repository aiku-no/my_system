"""
Strategy Module - Contains multiple trading strategies optimized for intraday forex
"""
import logging
from typing import Dict, Optional, Tuple, List
from enum import Enum
import pandas as pd
import numpy as np

from config import TradingConfig, Timeframe

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trade signal types"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class StrategyType(Enum):
    """Available trading strategies"""
    EMA_CROSS = "EMA_CROSS"           # Trend following
    RSI_MEAN_REVERSION = "RSI_MR"     # Mean reversion
    BOLLINGER_BREAKOUT = "BB_BREAK"   # Volatility breakout
    MACD_MOMENTUM = "MACD_MOM"        # Momentum
    STOCHASTIC_REVERSAL = "STOCH_REV" # Reversal
    COMBO_STRATEGY = "COMBO"          # Multi-signal combination


class TradingStrategy:
    """
    Main trading strategy class with multiple strategy implementations
    Optimized for intraday trading on M15, M30, and H1 timeframes
    """
    
    def __init__(self, config: TradingConfig):
        self.config = config
    
    def generate_signal(self, df: pd.DataFrame, 
                       strategy_type: StrategyType = StrategyType.COMBO_STRATEGY,
                       sentiment_score: float = 0.0) -> Dict:
        """
        Generate trading signal based on selected strategy
        
        Args:
            df: DataFrame with price data and technical indicators
            strategy_type: Which strategy to use
            sentiment_score: External sentiment score (-1 to 1)
            
        Returns:
            Dictionary with signal information
        """
        if df is None or len(df) < 50:
            return {'signal': SignalType.HOLD, 'confidence': 0.0}
        
        # Get latest candle data
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        signal_dict = {
            'signal': SignalType.HOLD,
            'confidence': 0.0,
            'strategy': strategy_type.value,
            'price': latest['close'],
            'timestamp': latest.name,
            'reason': ''
        }
        
        if strategy_type == StrategyType.EMA_CROSS:
            signal_dict = self._ema_cross_strategy(df, latest, prev, signal_dict)
        elif strategy_type == StrategyType.RSI_MEAN_REVERSION:
            signal_dict = self._rsi_mean_reversion(df, latest, prev, signal_dict)
        elif strategy_type == StrategyType.BOLLINGER_BREAKOUT:
            signal_dict = self._bollinger_breakout(df, latest, prev, signal_dict)
        elif strategy_type == StrategyType.MACD_MOMENTUM:
            signal_dict = self._macd_momentum(df, latest, prev, signal_dict)
        elif strategy_type == StrategyType.STOCHASTIC_REVERSAL:
            signal_dict = self._stochastic_reversal(df, latest, prev, signal_dict)
        elif strategy_type == StrategyType.COMBO_STRATEGY:
            signal_dict = self._combo_strategy(df, latest, prev, sentiment_score, signal_dict)
        
        # Adjust confidence based on sentiment alignment
        if sentiment_score != 0.0 and signal_dict['signal'] != SignalType.HOLD:
            sentiment_alignment = self._check_sentiment_alignment(
                signal_dict['signal'], sentiment_score
            )
            signal_dict['confidence'] *= (0.8 + 0.4 * sentiment_alignment)
            signal_dict['confidence'] = min(signal_dict['confidence'], 1.0)
            signal_dict['sentiment_aligned'] = sentiment_alignment > 0
        
        return signal_dict
    
    def _ema_cross_strategy(self, df: pd.DataFrame, latest, prev, 
                           signal_dict: Dict) -> Dict:
        """
        EMA Crossover Strategy
        Best for: Trending markets (M30, H1)
        """
        ema_fast = latest['ema_fast']
        ema_slow = latest['ema_slow']
        prev_ema_fast = prev['ema_fast']
        prev_ema_slow = prev['ema_slow']
        
        # Bullish crossover: fast EMA crosses above slow EMA
        if prev_ema_fast <= prev_ema_slow and ema_fast > ema_slow:
            signal_dict['signal'] = SignalType.BUY
            signal_dict['confidence'] = 0.7
            signal_dict['reason'] = 'EMA Bullish Crossover'
        
        # Bearish crossover: fast EMA crosses below slow EMA
        elif prev_ema_fast >= prev_ema_slow and ema_fast < ema_slow:
            signal_dict['signal'] = SignalType.SELL
            signal_dict['confidence'] = 0.7
            signal_dict['reason'] = 'EMA Bearish Crossover'
        
        # Check trend strength with ADX
        if latest.get('adx', 0) > 25:
            signal_dict['confidence'] += 0.1  # Stronger trend
        
        return signal_dict
    
    def _rsi_mean_reversion(self, df: pd.DataFrame, latest, prev,
                           signal_dict: Dict) -> Dict:
        """
        RSI Mean Reversion Strategy
        Best for: Ranging markets (M15, M30)
        """
        rsi = latest['rsi']
        
        # Oversold condition - potential buy
        if rsi < self.config.rsi_oversold:
            signal_dict['signal'] = SignalType.BUY
            signal_dict['confidence'] = 0.6
            signal_dict['reason'] = f'RSI Oversold ({rsi:.1f})'
        
        # Overbought condition - potential sell
        elif rsi > self.config.rsi_overbought:
            signal_dict['signal'] = SignalType.SELL
            signal_dict['confidence'] = 0.6
            signal_dict['reason'] = f'RSI Overbought ({rsi:.1f})'
        
        # Add divergence detection
        if rsi < self.config.rsi_oversold + 5 and rsi > prev['rsi']:
            signal_dict['confidence'] += 0.1  # RSI rising from oversold
        
        return signal_dict
    
    def _bollinger_breakout(self, df: pd.DataFrame, latest, prev,
                           signal_dict: Dict) -> Dict:
        """
        Bollinger Bands Breakout Strategy
        Best for: Volatile markets (M15, M30, H1)
        """
        price = latest['close']
        bb_upper = latest['bb_upper']
        bb_lower = latest['bb_lower']
        bb_middle = latest['bb_middle']
        
        # Breakout above upper band
        if price > bb_upper and prev['close'] <= prev['bb_upper']:
            signal_dict['signal'] = SignalType.BUY
            signal_dict['confidence'] = 0.65
            signal_dict['reason'] = 'BB Upper Breakout'
        
        # Breakout below lower band
        elif price < bb_lower and prev['close'] >= prev['bb_lower']:
            signal_dict['signal'] = SignalType.SELL
            signal_dict['confidence'] = 0.65
            signal_dict['reason'] = 'BB Lower Breakout'
        
        # Mean reversion to middle band
        elif abs(price - bb_middle) < (bb_upper - bb_lower) * 0.1:
            # Price near middle band - wait for direction
            pass
        
        return signal_dict
    
    def _macd_momentum(self, df: pd.DataFrame, latest, prev,
                      signal_dict: Dict) -> Dict:
        """
        MACD Momentum Strategy
        Best for: Trending markets (M30, H1)
        """
        macd = latest['macd']
        signal_line = latest['macd_signal']
        histogram = latest['macd_hist']
        prev_macd = prev['macd']
        prev_signal = prev['macd_signal']
        prev_hist = prev['macd_hist']
        
        # Bullish: MACD crosses above signal line
        if prev_macd <= prev_signal and macd > signal_line:
            signal_dict['signal'] = SignalType.BUY
            signal_dict['confidence'] = 0.65
            signal_dict['reason'] = 'MACD Bullish Cross'
        
        # Bearish: MACD crosses below signal line
        elif prev_macd >= prev_signal and macd < signal_line:
            signal_dict['signal'] = SignalType.SELL
            signal_dict['confidence'] = 0.65
            signal_dict['reason'] = 'MACD Bearish Cross'
        
        # Histogram momentum
        if histogram > 0 and histogram > prev_hist:
            if signal_dict['signal'] == SignalType.BUY:
                signal_dict['confidence'] += 0.1
        elif histogram < 0 and histogram < prev_hist:
            if signal_dict['signal'] == SignalType.SELL:
                signal_dict['confidence'] += 0.1
        
        return signal_dict
    
    def _stochastic_reversal(self, df: pd.DataFrame, latest, prev,
                            signal_dict: Dict) -> Dict:
        """
        Stochastic Reversal Strategy
        Best for: Ranging markets (M15, M30)
        """
        stoch_k = latest['stoch_k']
        stoch_d = latest['stoch_d']
        prev_k = prev['stoch_k']
        prev_d = prev['stoch_d']
        
        # Bullish: %K crosses above %D in oversold zone
        if stoch_k < 20 and prev_k <= prev_d and stoch_k > stoch_d:
            signal_dict['signal'] = SignalType.BUY
            signal_dict['confidence'] = 0.6
            signal_dict['reason'] = 'Stochastic Bullish Cross (Oversold)'
        
        # Bearish: %K crosses below %D in overbought zone
        elif stoch_k > 80 and prev_k >= prev_d and stoch_k < stoch_d:
            signal_dict['signal'] = SignalType.SELL
            signal_dict['confidence'] = 0.6
            signal_dict['reason'] = 'Stochastic Bearish Cross (Overbought)'
        
        return signal_dict
    
    def _combo_strategy(self, df: pd.DataFrame, latest, prev,
                       sentiment_score: float,
                       signal_dict: Dict) -> Dict:
        """
        Combined Strategy - Uses multiple indicators for confirmation
        Best overall performance for intraday trading
        
        Requires at least 2 out of 3 signals to agree:
        1. Trend (EMA + ADX)
        2. Momentum (RSI or MACD)
        3. Volatility (Bollinger Bands)
        """
        buy_signals = 0
        sell_signals = 0
        reasons = []
        
        # 1. Trend Signal (EMA + ADX)
        if latest['ema_fast'] > latest['ema_slow']:
            if latest.get('adx', 0) > 20:
                buy_signals += 1
                reasons.append('Trend:Bullish')
            else:
                buy_signals += 0.5  # Weak trend
        elif latest['ema_fast'] < latest['ema_slow']:
            if latest.get('adx', 0) > 20:
                sell_signals += 1
                reasons.append('Trend:Bearish')
            else:
                sell_signals += 0.5
        
        # 2. Momentum Signal (RSI)
        rsi = latest['rsi']
        if rsi < 40:
            buy_signals += 1
            reasons.append(f'Momentum:Oversold({rsi:.0f})')
        elif rsi > 60:
            sell_signals += 1
            reasons.append(f'Momentum:Overbought({rsi:.0f})')
        
        # 3. MACD Confirmation
        if latest['macd'] > latest['macd_signal']:
            buy_signals += 0.5
            reasons.append('MACD:Bullish')
        else:
            sell_signals += 0.5
            reasons.append('MACD:Bearish')
        
        # 4. Sentiment Alignment
        if sentiment_score > 0.3:
            buy_signals += 0.5
            reasons.append('Sentiment:Bullish')
        elif sentiment_score < -0.3:
            sell_signals += 0.5
            reasons.append('Sentiment:Bearish')
        
        # Determine final signal
        total_signals = max(buy_signals, sell_signals)
        
        if buy_signals >= 2.0 and buy_signals > sell_signals:
            signal_dict['signal'] = SignalType.BUY
            signal_dict['confidence'] = min(0.5 + (buy_signals - 2) * 0.15, 0.95)
            signal_dict['reason'] = ', '.join(reasons[:3])
        elif sell_signals >= 2.0 and sell_signals > buy_signals:
            signal_dict['signal'] = SignalType.SELL
            signal_dict['confidence'] = min(0.5 + (sell_signals - 2) * 0.15, 0.95)
            signal_dict['reason'] = ', '.join(reasons[:3])
        else:
            signal_dict['signal'] = SignalType.HOLD
            signal_dict['confidence'] = 0.0
            signal_dict['reason'] = 'No clear signal'
        
        return signal_dict
    
    def _check_sentiment_alignment(self, signal: SignalType, 
                                   sentiment_score: float) -> float:
        """Check if signal aligns with sentiment"""
        if signal == SignalType.BUY:
            return sentiment_score  # Positive if bullish
        elif signal == SignalType.SELL:
            return -sentiment_score  # Positive if bearish
        return 0.0
    
    def calculate_position_size(self, account_balance: float, 
                               stop_loss_pips: float,
                               risk_per_trade: float = None) -> float:
        """
        Calculate position size based on risk management rules
        
        Args:
            account_balance: Current account balance
            stop_loss_pips: Stop loss in pips
            risk_per_trade: Risk percentage (default from config)
            
        Returns:
            Position size in lots
        """
        if risk_per_trade is None:
            risk_per_trade = self.config.risk_per_trade
        
        risk_amount = account_balance * risk_per_trade
        
        # Standard lot = 100,000 units
        # Pip value for standard lot ≈ $10 for EUR/USD
        pip_value_per_lot = 10.0
        
        if stop_loss_pips <= 0:
            return 0.0
        
        position_size = risk_amount / (stop_loss_pips * pip_value_per_lot)
        
        # Round to 2 decimal places (minimum 0.01 lots)
        position_size = round(max(0.01, position_size), 2)
        
        return position_size
    
    def get_optimal_timeframe(self, pair: str) -> Timeframe:
        """
        Get optimal timeframe for a currency pair based on characteristics
        
        Research-backed recommendations:
        - EUR/USD: M30 (best liquidity, consistent patterns)
        - GBP/USD: M15 (higher volatility, faster moves)
        - USD/JPY: H1 (trending behavior)
        - AUD/USD: M30 (commodity-driven, moderate volatility)
        """
        recommendations = {
            'EUR_USD': Timeframe.M30,
            'GBP_USD': Timeframe.M15,
            'USD_JPY': Timeframe.H1,
            'AUD_USD': Timeframe.M30,
            'USD_CAD': Timeframe.M30,
            'USD_CHF': Timeframe.H1,
            'NZD_USD': Timeframe.M30
        }
        
        return recommendations.get(pair, Timeframe.M30)
