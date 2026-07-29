"""
Main Trading Bot - Orchestrates all components for 24/7 automated forex trading
"""
import logging
import time
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

from config import (
    OandaConfig, TradingConfig, CurrencyPair, Timeframe,
    DEFAULT_OANDA_CONFIG, DEFAULT_TRADING_CONFIG
)
from data_handler import DataHandler
from sentiment import SentimentAnalyzer
from strategy import TradingStrategy, StrategyType, SignalType
from risk_manager import RiskManager
from executor import OrderExecutor


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ForexTradingBot:
    """
    Complete automated forex trading system
    Runs 24/7 with proper risk management and multiple strategies
    """
    
    def __init__(self, 
                 oanda_config: OandaConfig = None,
                 trading_config: TradingConfig = None):
        """Initialize the trading bot with all components"""
        
        self.oanda_config = oanda_config or DEFAULT_OANDA_CONFIG
        self.trading_config = trading_config or DEFAULT_TRADING_CONFIG
        
        # Validate configuration
        self._validate_config()
        
        # Initialize components
        logger.info("Initializing trading bot components...")
        self.data_handler = DataHandler(self.oanda_config)
        self.sentiment_analyzer = SentimentAnalyzer()
        self.strategy = TradingStrategy(self.trading_config)
        self.risk_manager = RiskManager(self.trading_config)
        self.executor = OrderExecutor(self.oanda_config)
        
        # Trading state
        self.running = False
        self.last_check = None
        self.trades_today = 0
        self.daily_start_balance = 0.0
        
        # Performance tracking
        self.trade_log = []
        self.signals_generated = 0
        self.trades_executed = 0
        
        logger.info("Trading bot initialized successfully")
    
    def _validate_config(self):
        """Validate API credentials"""
        if not self.oanda_config.api_token:
            raise ValueError("OANDA API token not provided. Set OANDA_API_TOKEN environment variable.")
        if not self.oanda_config.account_id:
            raise ValueError("OANDA account ID not provided. Set OANDA_ACCOUNT_ID environment variable.")
        logger.info(f"Using OANDA practice account: {self.oanda_config.hostname}")
    
    def start(self):
        """Start the trading bot"""
        logger.info("=" * 60)
        logger.info("FOREX TRADING BOT STARTING")
        logger.info("=" * 60)
        logger.info(f"Configuration:")
        logger.info(f"  - Pairs: {[p.value for p in self.trading_config.pairs]}")
        logger.info(f"  - Primary Timeframe: {self.trading_config.primary_timeframe.value}")
        logger.info(f"  - Secondary Timeframe: {self.trading_config.secondary_timeframe.value}")
        logger.info(f"  - Risk per trade: {self.trading_config.risk_per_trade * 100}%")
        logger.info(f"  - Max positions: {self.trading_config.max_positions}")
        logger.info(f"  - Use sentiment: {self.trading_config.use_sentiment}")
        logger.info("=" * 60)
        
        self.running = True
        self._setup_signal_handlers()
        
        # Get initial account balance
        account_info = self.data_handler.get_account_info()
        if account_info:
            self.daily_start_balance = float(account_info['balance'])
            logger.info(f"Starting balance: ${self.daily_start_balance:.2f}")
        
        # Main trading loop
        self._run_trading_loop()
    
    def stop(self):
        """Stop the trading bot gracefully"""
        logger.info("Stopping trading bot...")
        self.running = False
    
    def _setup_signal_handlers(self):
        """Setup handlers for graceful shutdown"""
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _run_trading_loop(self):
        """Main trading loop - runs 24/7"""
        logger.info("Entering main trading loop...")
        
        while self.running:
            try:
                # Check if new day (reset daily counters)
                self._check_day_reset()
                
                # Get current account info
                account_info = self.data_handler.get_account_info()
                
                if not account_info:
                    logger.warning("Could not fetch account info, waiting...")
                    time.sleep(self.trading_config.check_interval_seconds)
                    continue
                
                # Log account status periodically
                if self.signals_generated % 10 == 0:
                    self._log_account_status(account_info)
                
                # Process each currency pair
                for pair in self.trading_config.pairs:
                    self._process_pair(pair, account_info)
                
                # Update trailing stops for open trades
                if self.trading_config.trailing_stop:
                    self.executor.update_trailing_stops(
                        self.trading_config.trailing_stop_distance
                    )
                
                # Update last check time
                self.last_check = datetime.now()
                
                # Wait for next iteration
                logger.debug(f"Sleeping for {self.trading_config.check_interval_seconds}s...")
                time.sleep(self.trading_config.check_interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                self.stop()
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                # Continue running despite errors
                time.sleep(self.trading_config.check_interval_seconds)
        
        # Shutdown
        logger.info("Trading bot stopped")
        self._generate_final_report()
    
    def _check_day_reset(self):
        """Check if it's a new trading day and reset counters"""
        now = datetime.now()
        if self.last_check and now.date() > self.last_check.date():
            logger.info("New trading day detected - resetting daily counters")
            self.risk_manager.reset_daily_pnl()
            self.trades_today = 0
            self.daily_start_balance = self.risk_manager.current_balance
    
    def _process_pair(self, pair: CurrencyPair, account_info: Dict):
        """Process a single currency pair"""
        instrument = pair.value
        
        # Check if we already have a position in this pair
        open_trades = self.executor.get_open_trades()
        existing_position = any(
            t['instrument'] == instrument for t in open_trades
        )
        
        if existing_position:
            logger.debug(f"Already have position in {instrument}, skipping")
            return
        
        # Get optimal timeframe for this pair
        timeframe = self.strategy.get_optimal_timeframe(instrument)
        
        # Fetch market data
        df = self.data_handler.get_candles(
            instrument, timeframe, count=100
        )
        
        if df is None or len(df) < 50:
            logger.warning(f"Insufficient data for {instrument}")
            return
        
        # Calculate technical indicators
        df = self.data_handler.calculate_technical_indicators(df, self.trading_config)
        
        # Get sentiment score
        sentiment_score = 0.0
        if self.trading_config.use_sentiment:
            try:
                sentiment_score = self.sentiment_analyzer.calculate_sentiment_score(instrument)
                if sentiment_score is None:
                    sentiment_score = 0.0
            except Exception as e:
                logger.warning(f"Could not get sentiment for {instrument}: {e}")
                sentiment_score = 0.0
        
        # Generate trading signal based on configured strategy
        strategy_type = self._get_strategy_type_from_config()
        signal = self.strategy.generate_signal(
            df, 
            strategy_type,
            sentiment_score
        )
        
        self.signals_generated += 1
        
        # Check if we have a valid signal
        if signal['signal'] == SignalType.HOLD:
            return
        
        # Check signal confidence threshold
        if signal['confidence'] < 0.5:
            logger.debug(f"Signal confidence too low for {instrument}: {signal['confidence']:.2f}")
            return
        
        # Get current price
        current_price_data = self.data_handler.get_current_price(instrument)
        if not current_price_data:
            return
        
        entry_price = current_price_data['ask'] if signal['signal'] == SignalType.BUY else current_price_data['bid']
        
        # Assess trade risk
        balance = float(account_info['balance'])
        trade_risk = self.risk_manager.assess_trade_risk(
            df, 
            signal['signal'].value,
            entry_price,
            balance
        )
        
        if not trade_risk:
            logger.error(f"Could not calculate risk for {instrument}")
            return
        
        # Check if trade is allowed by risk manager
        allowed, reason = self.risk_manager.should_allow_trade(
            account_info,
            trade_risk.risk_amount
        )
        
        if not allowed:
            logger.info(f"Trade not allowed for {instrument}: {reason}")
            return
        
        # Check sentiment alignment (optional filter)
        if self.trading_config.use_sentiment and abs(sentiment_score) > 0.3:
            if signal['signal'] == SignalType.BUY and sentiment_score < 0:
                logger.info(f"Skipping BUY for {instrument} - negative sentiment")
                return
            elif signal['signal'] == SignalType.SELL and sentiment_score > 0:
                logger.info(f"Skipping SELL for {instrument} - positive sentiment")
                return
        
        # Execute the trade
        logger.info(f"EXECUTING TRADE: {signal['signal'].value} {instrument}")
        logger.info(f"  Confidence: {signal['confidence']:.2f}")
        logger.info(f"  Entry: {entry_price:.5f}")
        logger.info(f"  Stop Loss: {trade_risk.stop_loss:.5f}")
        logger.info(f"  Take Profit: {trade_risk.take_profit:.5f}")
        logger.info(f"  Position Size: {trade_risk.position_size} lots")
        logger.info(f"  Risk/Reward: {trade_risk.risk_reward_ratio:.2f}")
        logger.info(f"  Reason: {signal['reason']}")
        
        result = self.executor.execute_signal(signal, instrument, trade_risk, balance)
        
        if result and result.get('success'):
            self.trades_executed += 1
            self.trades_today += 1
            
            # Log the trade
            trade_record = {
                'timestamp': datetime.now().isoformat(),
                'instrument': instrument,
                'direction': signal['signal'].value,
                'entry_price': entry_price,
                'stop_loss': trade_risk.stop_loss,
                'take_profit': trade_risk.take_profit,
                'position_size': trade_risk.position_size,
                'confidence': signal['confidence'],
                'strategy': signal['strategy'],
                'reason': signal['reason'],
                'sentiment_score': sentiment_score,
                'order_id': result.get('order_id'),
                'trade_id': result.get('trade_id')
            }
            self.trade_log.append(trade_record)
            
            logger.info(f"Trade executed successfully: {result.get('order_id')}")
        else:
            logger.error(f"Trade execution failed: {result}")
    
    def _log_account_status(self, account_info: Dict):
        """Log current account status"""
        balance = float(account_info['balance'])
        nav = float(account_info['nav'])
        equity = nav
        pnl = balance - self.daily_start_balance
        pnl_percent = (pnl / self.daily_start_balance * 100) if self.daily_start_balance > 0 else 0
        
        logger.info("-" * 40)
        logger.info(f"Account Status:")
        logger.info(f"  Balance: ${balance:.2f}")
        logger.info(f"  Equity: ${equity:.2f}")
        logger.info(f"  Daily P&L: ${pnl:.2f} ({pnl_percent:.2f}%)")
        logger.info(f"  Open Trades: {account_info['open_trade_count']}")
        logger.info(f"  Signals Today: {self.signals_generated}")
        logger.info(f"  Trades Executed: {self.trades_executed}")
        logger.info("-" * 40)
    
    def _generate_final_report(self):
        """Generate final trading report"""
        logger.info("=" * 60)
        logger.info("TRADING REPORT")
        logger.info("=" * 60)
        logger.info(f"Total signals generated: {self.signals_generated}")
        logger.info(f"Total trades executed: {self.trades_executed}")
        logger.info(f"Win rate: {self._calculate_win_rate():.1f}%")
        
        if self.trade_log:
            logger.info("\nRecent Trades:")
            for trade in self.trade_log[-10:]:
                logger.info(f"  {trade['timestamp'][:19]} | {trade['instrument']} | "
                          f"{trade['direction']} | {trade['entry_price']:.5f}")
        
        logger.info("=" * 60)
    
    def _calculate_win_rate(self) -> float:
        """Calculate win rate from closed trades"""
        # This would need to fetch closed trades from OANDA
        # For now, return 0
        return 0.0
    
    def _get_strategy_type_from_config(self) -> StrategyType:
        """Convert config strategy string to StrategyType enum"""
        strategy_map = {
            "EMA_CROSS": StrategyType.EMA_CROSS,
            "RSI_MR": StrategyType.RSI_MEAN_REVERSION,
            "BB_BREAK": StrategyType.BOLLINGER_BREAKOUT,
            "MACD_MOM": StrategyType.MACD_MOMENTUM,
            "STOCH_REV": StrategyType.STOCHASTIC_REVERSAL,
            "COMBO": StrategyType.COMBO_STRATEGY
        }
        return strategy_map.get(self.trading_config.active_strategy, StrategyType.COMBO_STRATEGY)
    
    def get_status(self) -> Dict:
        """Get current bot status"""
        account_info = self.data_handler.get_account_info()
        
        return {
            'running': self.running,
            'uptime': str(datetime.now() - self.last_check) if self.last_check else 'N/A',
            'signals_generated': self.signals_generated,
            'trades_executed': self.trades_executed,
            'trades_today': self.trades_today,
            'account_info': account_info,
            'last_check': self.last_check.isoformat() if self.last_check else None
        }


def main():
    """Main entry point"""
    print("=" * 60)
    print("FOREX TRADING BOT")
    print("=" * 60)
    print()
    print("This bot will run 24/7 until stopped.")
    print("Press Ctrl+C to stop.")
    print()
    
    # Create and start the bot
    try:
        bot = ForexTradingBot()
        bot.start()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"\nError starting bot: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
