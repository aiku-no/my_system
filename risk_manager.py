"""
Risk Management Module - Handles position sizing, stop losses, and portfolio risk
"""
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import pandas as pd

from config import TradingConfig

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for trades"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class TradeRisk:
    """Trade risk parameters"""
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float  # in lots
    risk_reward_ratio: float
    risk_amount: float  # in account currency
    potential_profit: float


class RiskManager:
    """
    Comprehensive risk management system
    Implements professional risk controls for forex trading
    """
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.max_daily_loss = 0.05  # 5% max daily loss
        self.max_weekly_loss = 0.10  # 10% max weekly loss
        self.max_drawdown = 0.15  # 15% max drawdown
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.peak_balance = 0.0
        self.current_balance = 0.0
    
    def calculate_stop_loss(self, df: pd.DataFrame, 
                           direction: str,
                           atr_multiplier: float = 1.5) -> float:
        """
        Calculate dynamic stop loss based on ATR (Average True Range)
        
        Args:
            df: DataFrame with ATR indicator
            direction: 'BUY' or 'SELL'
            atr_multiplier: Multiplier for ATR (default 1.5)
            
        Returns:
            Stop loss price level
        """
        if df is None or 'atr' not in df.columns:
            # Fallback to fixed stop loss
            return None
        
        latest = df.iloc[-1]
        atr = latest['atr']
        current_price = latest['close']
        
        if direction == 'BUY':
            stop_loss = current_price - (atr * atr_multiplier)
        else:  # SELL
            stop_loss = current_price + (atr * atr_multiplier)
        
        return round(stop_loss, 5)
    
    def calculate_take_profit(self, entry_price: float,
                             stop_loss: float,
                             direction: str,
                             risk_reward_ratio: float = 2.0) -> float:
        """
        Calculate take profit based on risk-reward ratio
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            direction: 'BUY' or 'SELL'
            risk_reward_ratio: Desired R:R ratio (default 2:1)
            
        Returns:
            Take profit price level
        """
        risk = abs(entry_price - stop_loss)
        
        if direction == 'BUY':
            take_profit = entry_price + (risk * risk_reward_ratio)
        else:  # SELL
            take_profit = entry_price - (risk * risk_reward_ratio)
        
        return round(take_profit, 5)
    
    def calculate_position_size(self, account_balance: float,
                               entry_price: float,
                               stop_loss: float,
                               risk_per_trade: float = None) -> float:
        """
        Calculate position size based on risk parameters
        
        Uses proper lot sizing based on stop loss distance
        """
        if risk_per_trade is None:
            risk_per_trade = self.config.risk_per_trade
        
        risk_amount = account_balance * risk_per_trade
        stop_loss_pips = abs(entry_price - stop_loss) * 10000  # Convert to pips
        
        if stop_loss_pips <= 0:
            return 0.0
        
        # Pip value per standard lot (approximate)
        pip_value = 10.0  # $10 per pip for EUR/USD standard lot
        
        position_size = risk_amount / (stop_loss_pips * pip_value)
        
        # Ensure minimum position size
        position_size = max(0.01, position_size)
        
        # Round to 2 decimal places
        return round(position_size, 2)
    
    def assess_trade_risk(self, df: pd.DataFrame,
                         direction: str,
                         entry_price: float,
                         account_balance: float) -> Optional[TradeRisk]:
        """
        Complete risk assessment for a potential trade
        
        Returns:
            TradeRisk object with all risk parameters
        """
        # Calculate stop loss
        stop_loss = self.calculate_stop_loss(df, direction)
        if stop_loss is None:
            # Use fixed stop loss
            pip_value = 0.0001 if 'JPY' not in str(df) else 0.01
            if direction == 'BUY':
                stop_loss = entry_price - (self.config.stop_loss_pips * pip_value)
            else:
                stop_loss = entry_price + (self.config.stop_loss_pips * pip_value)
        
        # Calculate take profit
        take_profit = self.calculate_take_profit(
            entry_price, stop_loss, direction
        )
        
        # Calculate position size
        position_size = self.calculate_position_size(
            account_balance, entry_price, stop_loss
        )
        
        # Calculate risk-reward ratio
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        # Calculate actual risk amount
        risk_pips = abs(entry_price - stop_loss) * 10000
        risk_amount = position_size * risk_pips * 10  # $10 per pip per lot
        
        # Calculate potential profit
        profit_pips = abs(take_profit - entry_price) * 10000
        potential_profit = position_size * profit_pips * 10
        
        return TradeRisk(
            entry_price=entry_price,
            stop_loss=round(stop_loss, 5),
            take_profit=round(take_profit, 5),
            position_size=position_size,
            risk_reward_ratio=round(rr_ratio, 2),
            risk_amount=risk_amount,
            potential_profit=potential_profit
        )
    
    def should_allow_trade(self, account_info: Dict,
                          new_risk_amount: float) -> tuple:
        """
        Check if a new trade should be allowed based on risk limits
        
        Returns:
            (allowed: bool, reason: str)
        """
        if not account_info:
            return False, "No account info available"
        
        balance = float(account_info.get('balance', 0))
        nav = float(account_info.get('nav', 0))
        margin_used = float(account_info.get('margin_used', 0))
        margin_available = float(account_info.get('margin_available', 0))
        open_trades = int(account_info.get('open_trade_count', 0))
        
        # Check maximum positions
        if open_trades >= self.config.max_positions:
            return False, f"Max positions reached ({self.config.max_positions})"
        
        # Check margin availability
        if new_risk_amount > margin_available * 0.5:
            return False, "Insufficient margin available"
        
        # Check daily loss limit
        if self.daily_pnl < -balance * self.max_daily_loss:
            return False, "Daily loss limit reached"
        
        # Check weekly loss limit
        if self.weekly_pnl < -balance * self.max_weekly_loss:
            return False, "Weekly loss limit reached"
        
        # Check drawdown
        if self.peak_balance > 0:
            current_drawdown = (self.peak_balance - nav) / self.peak_balance
            if current_drawdown > self.max_drawdown:
                return False, "Maximum drawdown reached"
        
        # Update peak balance
        if nav > self.peak_balance:
            self.peak_balance = nav
        
        return True, "Trade approved"
    
    def update_pnl(self, pnl: float):
        """Update daily and weekly PnL"""
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
        self.current_balance += pnl
    
    def reset_daily_pnl(self):
        """Reset daily PnL (call at start of new trading day)"""
        self.daily_pnl = 0.0
    
    def reset_weekly_pnl(self):
        """Reset weekly PnL (call at start of new week)"""
        self.weekly_pnl = 0.0
    
    def get_risk_level(self, signal_confidence: float,
                      market_volatility: float) -> RiskLevel:
        """
        Determine overall risk level for a trade
        
        Args:
            signal_confidence: Strategy signal confidence (0-1)
            market_volatility: Current market volatility (ATR-based)
            
        Returns:
            RiskLevel enum
        """
        # High confidence + low volatility = LOW risk
        # Low confidence + high volatility = HIGH risk
        
        risk_score = 0
        
        # Signal confidence factor (lower confidence = higher risk)
        if signal_confidence < 0.5:
            risk_score += 2
        elif signal_confidence < 0.7:
            risk_score += 1
        
        # Volatility factor (higher volatility = higher risk)
        if market_volatility > 0.001:  # High ATR
            risk_score += 2
        elif market_volatility > 0.0005:
            risk_score += 1
        
        # Determine risk level
        if risk_score >= 3:
            return RiskLevel.HIGH
        elif risk_score >= 1:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def trailing_stop_update(self, current_price: float,
                            entry_price: float,
                            current_stop: float,
                            direction: str,
                            trailing_distance_pips: float = None) -> float:
        """
        Update trailing stop loss
        
        Args:
            current_price: Current market price
            entry_price: Trade entry price
            current_stop: Current stop loss
            direction: 'BUY' or 'SELL'
            trailing_distance_pips: Distance in pips (default from config)
            
        Returns:
            New stop loss level
        """
        if trailing_distance_pips is None:
            trailing_distance_pips = self.config.trailing_stop_distance
        
        pip_value = 0.0001
        trailing_distance = trailing_distance_pips * pip_value
        
        if direction == 'BUY':
            # For buy trades, only move stop up
            new_stop = current_price - trailing_distance
            if new_stop > current_stop and new_stop > entry_price:
                return new_stop
        else:  # SELL
            # For sell trades, only move stop down
            new_stop = current_price + trailing_distance
            if new_stop < current_stop and new_stop < entry_price:
                return new_stop
        
        return current_stop
    
    def get_portfolio_risk_summary(self, account_info: Dict,
                                   open_positions: List) -> Dict:
        """
        Get comprehensive portfolio risk summary
        
        Returns:
            Dictionary with risk metrics
        """
        if not account_info:
            return {}
        
        balance = float(account_info.get('balance', 0))
        nav = float(account_info.get('nav', 0))
        
        total_risk = sum(pos.get('risk_amount', 0) for pos in open_positions)
        total_exposure = sum(pos.get('notional', 0) for pos in open_positions)
        
        return {
            'account_balance': balance,
            'nav': nav,
            'total_risk': total_risk,
            'risk_percentage': (total_risk / balance * 100) if balance > 0 else 0,
            'total_exposure': total_exposure,
            'exposure_percentage': (total_exposure / balance * 100) if balance > 0 else 0,
            'daily_pnl': self.daily_pnl,
            'weekly_pnl': self.weekly_pnl,
            'current_drawdown': ((self.peak_balance - nav) / self.peak_balance * 100) if self.peak_balance > 0 else 0,
            'max_daily_loss_limit': balance * self.max_daily_loss,
            'positions_count': len(open_positions),
            'max_positions': self.config.max_positions
        }
