"""
Execution Module - Handles order placement and trade management via OANDA API
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime
import pandas as pd

import v20
from v20 import primitives

from config import OandaConfig, Timeframe
from strategy import SignalType
from risk_manager import TradeRisk

logger = logging.getLogger(__name__)


class OrderExecutor:
    """
    Handles all order execution and trade management
    Interfaces with OANDA API for live trading
    """
    
    def __init__(self, config: OandaConfig):
        self.config = config
        self.ctx = None
        self._initialize_api()
    
    def _initialize_api(self):
        """Initialize OANDA API context"""
        try:
            self.ctx = v20.Context(
                domain=self.config.hostname,
                token=self.config.api_token
            )
            logger.info("Order Executor API initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Order Executor API: {e}")
            raise
    
    def place_market_order(self, instrument: str, 
                          units: int,
                          stop_loss: float = None,
                          take_profit: float = None) -> Optional[Dict]:
        """
        Place a market order
        
        Args:
            instrument: Currency pair (e.g., "EUR_USD")
            units: Positive for buy, negative for sell
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            
        Returns:
            Order response dictionary
        """
        try:
            # Determine order type
            if units > 0:
                position = primitives.PositionFill.OPEN
            else:
                position = primitives.PositionFill.CLOSE
            
            # Create the order request
            order_request = primitives.MarketOrderRequest(
                instrument=instrument,
                units=units,
                positionFill=position,
                reason="CLIENT_REQUEST"
            )
            
            # Add stop loss if provided
            if stop_loss:
                order_request.stopLossOnFill = primitives.StopLossDetails(
                    price=stop_loss,
                    timeInForce=primitives.TimeInForce.GTC
                )
            
            # Add take profit if provided
            if take_profit:
                order_request.takeProfitOnFill = primitives.TakeProfitDetails(
                    price=take_profit
                )
            
            # Place the order
            response = self.ctx.order.market(
                accountID=self.config.account_id,
                order=order_request
            )
            
            # Parse response
            order_data = {
                'order_id': response.get('orderCreateTransaction', {}).get('id'),
                'instrument': instrument,
                'units': units,
                'direction': 'BUY' if units > 0 else 'SELL',
                'status': response.get('orderCreateTransaction', {}).get('reason'),
                'timestamp': datetime.now(),
                'success': True
            }
            
            # Get trade ID if filled
            if 'orderFillTransaction' in response:
                order_data['trade_id'] = response['orderFillTransaction'].get('tradeID')
                order_data['fill_price'] = response['orderFillTransaction'].get('price')
            
            logger.info(f"Order placed: {instrument} {units} units - {order_data['order_id']}")
            return order_data
            
        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now()
            }
    
    def place_pending_order(self, instrument: str,
                           units: int,
                           price: float,
                           order_type: str = 'LIMIT',
                           stop_loss: float = None,
                           take_profit: float = None) -> Optional[Dict]:
        """
        Place a pending order (LIMIT or STOP)
        
        Args:
            instrument: Currency pair
            units: Positive for buy, negative for sell
            price: Trigger price
            order_type: 'LIMIT' or 'STOP'
            stop_loss: Stop loss price
            take_profit: Take profit price
            
        Returns:
            Order response dictionary
        """
        try:
            if order_type.upper() == 'LIMIT':
                order_request = primitives.LimitOrderRequest(
                    instrument=instrument,
                    units=units,
                    price=price,
                    positionFill=primitives.PositionFill.OPEN,
                    timeInForce=primitives.TimeInForce.GTC
                )
            elif order_type.upper() == 'STOP':
                order_request = primitives.StopOrderRequest(
                    instrument=instrument,
                    units=units,
                    price=price,
                    positionFill=primitives.PositionFill.OPEN,
                    timeInForce=primitives.TimeInForce.GTC
                )
            else:
                raise ValueError(f"Invalid order type: {order_type}")
            
            # Add SL/TP if provided
            if stop_loss:
                order_request.stopLossOnFill = primitives.StopLossDetails(
                    price=stop_loss,
                    timeInForce=primitives.TimeInForce.GTC
                )
            
            if take_profit:
                order_request.takeProfitOnFill = primitives.TakeProfitDetails(
                    price=take_profit
                )
            
            response = self.ctx.order.pending(
                accountID=self.config.account_id,
                order=order_request
            )
            
            order_data = {
                'order_id': response.get('orderCreateTransaction', {}).get('id'),
                'instrument': instrument,
                'units': units,
                'type': order_type,
                'price': price,
                'status': 'PENDING',
                'timestamp': datetime.now(),
                'success': True
            }
            
            logger.info(f"Pending order placed: {order_type} {instrument} @ {price}")
            return order_data
            
        except Exception as e:
            logger.error(f"Failed to place pending order: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now()
            }
    
    def close_trade(self, trade_id: str, units: int = None) -> Optional[Dict]:
        """
        Close an existing trade
        
        Args:
            trade_id: Trade ID to close
            units: Number of units to close (None for full close)
            
        Returns:
            Close response dictionary
        """
        try:
            response = self.ctx.trade.close(
                accountID=self.config.account_id,
                tradeID=trade_id
            )
            
            close_data = {
                'trade_id': trade_id,
                'close_transaction_id': response.get('orderCreateTransaction', {}).get('id'),
                'pnl': response.get('orderFillTransaction', {}).get('pl'),
                'timestamp': datetime.now(),
                'success': True
            }
            
            logger.info(f"Trade closed: {trade_id}, PnL: {close_data['pnl']}")
            return close_data
            
        except Exception as e:
            logger.error(f"Failed to close trade: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now()
            }
    
    def modify_trade_stop_loss(self, trade_id: str, 
                               stop_loss: float) -> Optional[Dict]:
        """
        Modify stop loss for an existing trade
        
        Args:
            trade_id: Trade ID
            stop_loss: New stop loss price
            
        Returns:
            Modification response
        """
        try:
            response = self.ctx.trade.set_dependent_orders(
                accountID=self.config.account_id,
                tradeID=trade_id,
                stopLoss=primitives.StopLossDetails(
                    price=stop_loss,
                    timeInForce=primitives.TimeInForce.GTC
                )
            )
            
            mod_data = {
                'trade_id': trade_id,
                'new_stop_loss': stop_loss,
                'transaction_id': response.get('stopLossOrderTransaction', {}).get('id'),
                'timestamp': datetime.now(),
                'success': True
            }
            
            logger.info(f"Stop loss modified for trade {trade_id}: {stop_loss}")
            return mod_data
            
        except Exception as e:
            logger.error(f"Failed to modify stop loss: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now()
            }
    
    def get_open_trades(self) -> List[Dict]:
        """
        Get all open trades
        
        Returns:
            List of open trade dictionaries
        """
        try:
            response = self.ctx.trade.open(
                accountID=self.config.account_id
            )
            
            trades = []
            for trade in response.get('trades', []):
                trade_data = {
                    'trade_id': trade.id,
                    'instrument': trade.instrument,
                    'units': float(trade.currentUnits),
                    'avg_price': float(trade.price),
                    'unrealized_pl': float(trade.unrealizedPL),
                    'stop_loss': float(trade.stopLossOrder.price) if trade.stopLossOrder else None,
                    'take_profit': float(trade.takeProfitOrder.price) if trade.takeProfitOrder else None,
                    'open_time': trade.openTime
                }
                trades.append(trade_data)
            
            return trades
            
        except Exception as e:
            logger.error(f"Failed to get open trades: {e}")
            return []
    
    def get_pending_orders(self) -> List[Dict]:
        """
        Get all pending orders
        
        Returns:
            List of pending order dictionaries
        """
        try:
            response = self.ctx.order.pending(
                accountID=self.config.account_id
            )
            
            orders = []
            for order in response.get('orders', []):
                order_data = {
                    'order_id': order.id,
                    'instrument': order.instrument,
                    'units': float(order.units),
                    'price': float(order.price) if hasattr(order, 'price') else None,
                    'type': order.type,
                    'state': order.state
                }
                orders.append(order_data)
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get pending orders: {e}")
            return []
    
    def cancel_order(self, order_id: str) -> Optional[Dict]:
        """
        Cancel a pending order
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Cancellation response
        """
        try:
            response = self.ctx.order.cancel(
                accountID=self.config.account_id,
                orderID=order_id
            )
            
            cancel_data = {
                'order_id': order_id,
                'cancel_transaction_id': response.get('orderCancelTransaction', {}).get('id'),
                'timestamp': datetime.now(),
                'success': True
            }
            
            logger.info(f"Order cancelled: {order_id}")
            return cancel_data
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now()
            }
    
    def execute_signal(self, signal: Dict, instrument: str,
                      risk: TradeRisk, account_balance: float) -> Optional[Dict]:
        """
        Execute a trading signal
        
        Args:
            signal: Signal dictionary from strategy
            instrument: Currency pair
            risk: TradeRisk object with position sizing
            account_balance: Current account balance
            
        Returns:
            Execution result dictionary
        """
        if signal['signal'] == SignalType.HOLD:
            return None
        
        # Convert lots to units (1 lot = 100,000 units)
        units = int(risk.position_size * 100000)
        
        if signal['signal'] == SignalType.SELL:
            units = -units  # Negative for sell
        
        logger.info(f"Executing {signal['signal']} signal for {instrument}")
        logger.info(f"Units: {units}, SL: {risk.stop_loss}, TP: {risk.take_profit}")
        
        # Place market order with SL and TP
        result = self.place_market_order(
            instrument=instrument,
            units=units,
            stop_loss=risk.stop_loss,
            take_profit=risk.take_profit
        )
        
        if result and result.get('success'):
            result['signal'] = signal['signal'].value
            result['confidence'] = signal.get('confidence', 0)
            result['strategy'] = signal.get('strategy', 'unknown')
            result['reason'] = signal.get('reason', '')
            result['risk_reward'] = risk.risk_reward_ratio
            result['position_size'] = risk.position_size
        
        return result
    
    def update_trailing_stops(self, trailing_distance_pips: float):
        """
        Update trailing stops for all open trades
        
        Args:
            trailing_distance_pips: Distance in pips for trailing stop
        """
        open_trades = self.get_open_trades()
        
        for trade in open_trades:
            current_price = self._get_current_price(trade['instrument'])
            if not current_price:
                continue
            
            direction = 'BUY' if trade['units'] > 0 else 'SELL'
            entry_price = trade['avg_price']
            current_stop = trade.get('stop_loss')
            
            if current_stop is None:
                continue
            
            # Calculate new trailing stop
            pip_value = 0.01 if 'JPY' in trade['instrument'] else 0.0001
            trailing_distance = trailing_distance_pips * pip_value
            
            new_stop = None
            if direction == 'BUY':
                new_stop = current_price - trailing_distance
                if new_stop <= current_stop or new_stop <= entry_price:
                    new_stop = None
            else:  # SELL
                new_stop = current_price + trailing_distance
                if new_stop >= current_stop or new_stop >= entry_price:
                    new_stop = None
            
            # Update if better stop found
            if new_stop:
                self.modify_trade_stop_loss(trade['trade_id'], new_stop)
    
    def _get_current_price(self, instrument: str) -> Optional[float]:
        """Get current mid price for an instrument"""
        try:
            response = self.ctx.pricing.get(
                accountID=self.config.account_id,
                instruments=instrument
            )
            
            for price in response.get('prices', []):
                if price.instrument == instrument:
                    bid = float(price.bids[0].price)
                    ask = float(price.asks[0].price)
                    return (bid + ask) / 2
        except:
            pass
        
        return None
