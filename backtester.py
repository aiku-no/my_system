"""
Backtesting Module - Test strategies on historical data
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure

from config import TradingConfig, Timeframe, CurrencyPair, BacktestConfig, OandaConfig
from data_handler import DataHandler
from strategy import TradingStrategy, StrategyType, SignalType
from risk_manager import RiskManager

# Combine configs for backtester
class CombinedConfig:
    def __init__(self):
        self.trading = TradingConfig()
        self.oanda = OandaConfig()
        # Merge attributes
        for attr in dir(self.trading):
            if not attr.startswith('_'):
                setattr(self, attr, getattr(self.trading, attr))
        for attr in dir(self.oanda):
            if not attr.startswith('_'):
                setattr(self, attr, getattr(self.oanda, attr))

Config = CombinedConfig

logger = logging.getLogger(__name__)


class Trade:
    """Represents a single trade in backtesting"""
    
    def __init__(self, entry_price: float, entry_time: str, 
                 direction: str, size: float, pair: str):
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.direction = direction  # 'BUY' or 'SELL'
        self.size = size
        self.pair = pair
        self.exit_price: Optional[float] = None
        self.exit_time: Optional[str] = None
        self.stop_loss: Optional[float] = None
        self.take_profit: Optional[float] = None
        self.pnl: float = 0.0
        self.pnl_pips: float = 0.0
        self.max_drawdown: float = 0.0
        self.max_profit: float = 0.0
        
    def close(self, exit_price: float, exit_time: str):
        """Close the trade and calculate P&L"""
        self.exit_price = exit_price
        self.exit_time = exit_time
        
        if self.direction == 'BUY':
            self.pnl_pips = (exit_price - self.entry_price) * 10000
        else:
            self.pnl_pips = (self.entry_price - exit_price) * 10000
        
        # Standard lot pip value ≈ $10
        self.pnl = self.pnl_pips * self.size * 10
        
    def update_metrics(self, current_price: float):
        """Update max profit and drawdown during trade"""
        if self.direction == 'BUY':
            unrealized_pips = (current_price - self.entry_price) * 10000
        else:
            unrealized_pips = (self.entry_price - current_price) * 10000
            
        unrealized_pnl = unrealized_pips * self.size * 10
        
        if unrealized_pnl > self.max_profit:
            self.max_profit = unrealized_pnl
            
        if unrealized_pnl < self.max_drawdown:
            self.max_drawdown = unrealized_pnl


class Backtester:
    """
    Backtesting engine for testing trading strategies on historical data
    """
    
    def __init__(self, config: TradingConfig, backtest_config: BacktestConfig,
                 strategy_type: StrategyType = StrategyType.COMBO_STRATEGY):
        self.config = config
        self.backtest_config = backtest_config
        self.strategy_type = strategy_type
        self.strategy = TradingStrategy(config)
        self.risk_manager = RiskManager(config)
        
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.equity_times: List[datetime] = []
        self.current_capital = backtest_config.initial_capital
        
    def run_backtest(self, pair: CurrencyPair, timeframe: Timeframe,
                    use_sentiment: bool = False) -> Dict:
        """
        Run backtest for a specific pair and timeframe
        
        Args:
            pair: Currency pair to test
            timeframe: Timeframe to test
            use_sentiment: Whether to include sentiment analysis
            
        Returns:
            Dictionary with backtest results
        """
        logger.info(f"Starting backtest: {pair.value} on {timeframe.value}")
        logger.info(f"Strategy: {self.strategy_type.value}")
        logger.info(f"Period: {self.backtest_config.start_date} to {self.backtest_config.end_date}")
        
        # Get historical data
        config = Config()
        data_handler = DataHandler(config)
        df = data_handler.get_candles(
            pair.value, 
            timeframe,
            count=5000  # Get enough data for backtesting
        )
        
        if df is None or len(df) < 100:
            logger.error("Insufficient data for backtesting")
            return self._empty_results()
        
        # Filter by date range
        df = self._filter_by_date_range(df)
        
        if len(df) < 100:
            logger.error("Insufficient data after date filtering")
            return self._empty_results()
        
        logger.info(f"Testing on {len(df)} candles")
        
        # Reset state
        self.trades = []
        self.equity_curve = [self.backtest_config.initial_capital]
        self.equity_times = [df.index[0]]
        self.current_capital = self.backtest_config.initial_capital
        
        active_trades: List[Trade] = []
        
        # Iterate through data (skip first 50 candles for indicator warmup)
        for i in range(50, len(df)):
            current_idx = i
            current_candle = df.iloc[current_idx]
            current_time = current_candle.name
            current_price = current_candle['close']
            
            # Get historical data up to this point for signal generation
            historical_df = df.iloc[:current_idx+1].copy()
            
            # Generate signal
            sentiment_score = 0.0
            if use_sentiment:
                # For backtesting, we'll use a simplified sentiment model
                # In real trading, this would fetch actual sentiment
                sentiment_score = self._simulate_sentiment(historical_df)
            
            signal = self.strategy.generate_signal(
                historical_df,
                self.strategy_type,
                sentiment_score
            )
            
            # Check for existing trades to manage
            for trade in active_trades[:]:
                # Update trade metrics
                trade.update_metrics(current_price)
                
                # Check stop loss
                if trade.direction == 'BUY':
                    if trade.stop_loss and current_price <= trade.stop_loss:
                        trade.close(trade.stop_loss, current_time)
                        self._close_trade(trade, active_trades, "Stop Loss")
                        continue
                    if trade.take_profit and current_price >= trade.take_profit:
                        trade.close(trade.take_profit, current_time)
                        self._close_trade(trade, active_trades, "Take Profit")
                        continue
                else:  # SELL
                    if trade.stop_loss and current_price >= trade.stop_loss:
                        trade.close(trade.stop_loss, current_time)
                        self._close_trade(trade, active_trades, "Stop Loss")
                        continue
                    if trade.take_profit and current_price <= trade.take_profit:
                        trade.close(trade.take_profit, current_time)
                        self._close_trade(trade, active_trades, "Take Profit")
                        continue
            
            # Check for new signals (only if no active trades for this pair)
            if signal['signal'] != SignalType.HOLD and len(active_trades) < self.config.max_positions:
                if len([t for t in active_trades if t.pair == pair.value]) == 0:
                    self._open_trade(signal, current_price, current_time, pair.value)
            
            # Record equity
            total_pnl = sum(t.pnl for t in self.trades)
            current_equity = self.backtest_config.initial_capital + total_pnl
            self.equity_curve.append(current_equity)
            self.equity_times.append(current_time)
        
        # Close any remaining open trades at the last price
        last_price = df.iloc[-1]['close']
        last_time = df.index[-1]
        for trade in active_trades[:]:
            trade.close(last_price, last_time)
            self.trades.append(trade)
            active_trades.remove(trade)
        
        # Calculate results
        results = self._calculate_results(pair, timeframe)
        
        logger.info(f"Backtest complete. Total trades: {len(self.trades)}")
        logger.info(f"Net P&L: ${results['total_pnl']:.2f}")
        logger.info(f"Win rate: {results['win_rate']:.1f}%")
        
        return results
    
    def _open_trade(self, signal: Dict, price: float, time: str, pair: str):
        """Open a new trade based on signal"""
        # Calculate position size
        stop_loss_pips = self.config.stop_loss_pips
        position_size = self.strategy.calculate_position_size(
            self.current_capital,
            stop_loss_pips
        )
        
        if position_size <= 0:
            return
        
        # Create trade
        trade = Trade(
            entry_price=price,
            entry_time=time,
            direction=signal['signal'].value,
            size=position_size,
            pair=pair
        )
        
        # Set SL and TP
        if signal['signal'] == SignalType.BUY:
            trade.stop_loss = price - (stop_loss_pips / 10000)
            trade.take_profit = price + (self.config.take_profit_pips / 10000)
        else:
            trade.stop_loss = price + (stop_loss_pips / 10000)
            trade.take_profit = price - (self.config.take_profit_pips / 10000)
        
        logger.debug(f"Opening {signal['signal'].value} trade at {price} for {pair}")
        
    def _close_trade(self, trade: Trade, active_trades: List, reason: str):
        """Close a trade and record it"""
        self.trades.append(trade)
        active_trades.remove(trade)
        logger.debug(f"Closed trade: {reason}, P&L: ${trade.pnl:.2f}")
    
    def _calculate_results(self, pair: CurrencyPair, timeframe: Timeframe) -> Dict:
        """Calculate comprehensive backtest statistics"""
        if not self.trades:
            return self._empty_results()
        
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]
        
        total_pnl = sum(t.pnl for t in self.trades)
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        
        win_rate = (len(winning_trades) / len(self.trades)) * 100 if self.trades else 0
        
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Calculate maximum drawdown
        max_drawdown = 0
        peak = self.backtest_config.initial_capital
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Calculate Sharpe ratio (simplified)
        if len(self.equity_curve) > 1:
            returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Calculate largest win and loss
        largest_win = max([t.pnl for t in self.trades]) if self.trades else 0
        largest_loss = min([t.pnl for t in self.trades]) if self.trades else 0
        
        # Average trade duration (in candles)
        avg_duration = 0
        durations = []
        for t in self.trades:
            if t.entry_time and t.exit_time:
                try:
                    entry_dt = pd.Timestamp(t.entry_time)
                    exit_dt = pd.Timestamp(t.exit_time)
                    duration = (exit_dt - entry_dt).total_seconds() / 3600  # hours
                    durations.append(duration)
                except:
                    pass
        if durations:
            avg_duration = np.mean(durations)
        
        return {
            'pair': pair.value,
            'timeframe': timeframe.value,
            'strategy': self.strategy_type.value,
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'avg_trade_duration_hours': avg_duration,
            'final_capital': self.backtest_config.initial_capital + total_pnl,
            'return_pct': (total_pnl / self.backtest_config.initial_capital) * 100,
            'equity_curve': self.equity_curve,
            'equity_times': self.equity_times
        }
    
    def _empty_results(self) -> Dict:
        """Return empty results dictionary"""
        return {
            'pair': '',
            'timeframe': '',
            'strategy': self.strategy_type.value,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'gross_profit': 0,
            'gross_loss': 0,
            'profit_factor': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'largest_win': 0,
            'largest_loss': 0,
            'avg_trade_duration_hours': 0,
            'final_capital': self.backtest_config.initial_capital,
            'return_pct': 0,
            'equity_curve': [],
            'equity_times': []
        }
    
    def _filter_by_date_range(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter DataFrame by backtest date range"""
        start = pd.Timestamp(self.backtest_config.start_date)
        end = pd.Timestamp(self.backtest_config.end_date)
        return df[(df.index >= start) & (df.index <= end)]
    
    def _simulate_sentiment(self, df: pd.DataFrame) -> float:
        """
        Simulate sentiment for backtesting
        In real trading, this would fetch actual sentiment data
        """
        # Simple momentum-based sentiment simulation
        if len(df) < 50:
            return 0.0
        
        recent_returns = df['close'].pct_change(10).iloc[-1]
        
        if recent_returns > 0.005:
            return 0.7
        elif recent_returns > 0.002:
            return 0.4
        elif recent_returns < -0.005:
            return -0.7
        elif recent_returns < -0.002:
            return -0.4
        else:
            return 0.0
    
    def plot_equity_curve(self, results: Dict, save_path: str = 'backtest_equity.png'):
        """Plot the equity curve from backtest results"""
        if not results.get('equity_curve') or len(results['equity_curve']) < 2:
            logger.warning("No equity curve data to plot")
            return
        
        fig, ax = plt.subplots(figsize=(14, 7))
        
        times = results['equity_times']
        equity = results['equity_curve']
        
        # Convert times to matplotlib format if needed
        if isinstance(times[0], pd.Timestamp):
            times = [t.to_pydatetime() for t in times]
        
        ax.plot(times, equity, linewidth=1.5, label='Equity Curve')
        ax.axhline(y=self.backtest_config.initial_capital, color='gray', 
                   linestyle='--', label='Initial Capital')
        
        ax.set_title(f"Backtest Results: {results['pair']} ({results['timeframe']})\n"
                    f"Strategy: {results['strategy']} | Return: {results['return_pct']:.1f}%")
        ax.set_xlabel('Date')
        ax.set_ylabel('Equity ($)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close()
        
        logger.info(f"Equity curve saved to {save_path}")
    
    def print_report(self, results: Dict):
        """Print detailed backtest report"""
        print("\n" + "="*70)
        print("BACKTEST REPORT")
        print("="*70)
        print(f"Pair:              {results['pair']}")
        print(f"Timeframe:         {results['timeframe']}")
        print(f"Strategy:          {results['strategy']}")
        print("-"*70)
        print(f"Total Trades:      {results['total_trades']}")
        print(f"Winning Trades:    {results['winning_trades']}")
        print(f"Losing Trades:     {results['losing_trades']}")
        print(f"Win Rate:          {results['win_rate']:.1f}%")
        print("-"*70)
        print(f"Total P&L:         ${results['total_pnl']:,.2f}")
        print(f"Gross Profit:      ${results['gross_profit']:,.2f}")
        print(f"Gross Loss:        ${results['gross_loss']:,.2f}")
        print(f"Profit Factor:     {results['profit_factor']:.2f}")
        print(f"Average Win:       ${results['avg_win']:,.2f}")
        print(f"Average Loss:      ${results['avg_loss']:,.2f}")
        print("-"*70)
        print(f"Max Drawdown:      {results['max_drawdown']:.1f}%")
        print(f"Sharpe Ratio:      {results['sharpe_ratio']:.2f}")
        print(f"Largest Win:       ${results['largest_win']:,.2f}")
        print(f"Largest Loss:      ${results['largest_loss']:,.2f}")
        print(f"Avg Duration:      {results['avg_trade_duration_hours']:.1f} hours")
        print("-"*70)
        print(f"Initial Capital:   ${self.backtest_config.initial_capital:,.2f}")
        print(f"Final Capital:     ${results['final_capital']:,.2f}")
        print(f"Return:            {results['return_pct']:.1f}%")
        print("="*70 + "\n")


def run_all_strategies_backtest():
    """
    Run backtests for all strategies on all pairs and timeframes
    This helps identify the best performing combination
    """
    config = TradingConfig()
    backtest_config = BacktestConfig(
        start_date="2024-06-01",
        end_date="2024-12-31",
        initial_capital=10000.0
    )
    
    all_results = []
    
    print("\n" + "="*70)
    print("COMPREHENSIVE BACKTEST - ALL STRATEGIES")
    print("="*70)
    
    for strategy_type in StrategyType:
        print(f"\nTesting Strategy: {strategy_type.value}")
        print("-"*70)
        
        backtester = Backtester(config, backtest_config, strategy_type)
        
        for pair in CurrencyPair:
            for timeframe in [Timeframe.M15, Timeframe.M30, Timeframe.H1]:
                results = backtester.run_backtest(pair, timeframe, use_sentiment=False)
                
                if results['total_trades'] > 0:
                    all_results.append(results)
                    print(f"{pair.value:10} | {timeframe.value:3} | "
                          f"Trades: {results['total_trades']:3} | "
                          f"Win%: {results['win_rate']:5.1f} | "
                          f"P&L: ${results['total_pnl']:8.2f} | "
                          f"PF: {results['profit_factor']:.2f}")
    
    # Sort by profit factor
    all_results.sort(key=lambda x: x['profit_factor'], reverse=True)
    
    print("\n" + "="*70)
    print("TOP 10 RESULTS BY PROFIT FACTOR")
    print("="*70)
    
    for i, r in enumerate(all_results[:10], 1):
        print(f"{i}. {r['pair']} | {r['timeframe']} | {r['strategy']} | "
              f"PF: {r['profit_factor']:.2f} | Win%: {r['win_rate']:.1f} | "
              f"P&L: ${r['total_pnl']:.2f}")
    
    return all_results


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    config = TradingConfig()
    backtest_config = BacktestConfig(
        start_date="2024-09-01",
        end_date="2024-12-31",
        initial_capital=10000.0
    )
    
    # Test COMBO strategy on EUR/USD M30
    backtester = Backtester(config, backtest_config, StrategyType.COMBO_STRATEGY)
    results = backtester.run_backtest(CurrencyPair.EUR_USD, Timeframe.M30)
    
    backtester.print_report(results)
    backtester.plot_equity_curve(results)
    
    # To test all strategies, uncomment:
    # run_all_strategies_backtest()
