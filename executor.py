"""
Execution Module - Handles order placement and trade management via OANDA API
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime
import pandas as pd
import requests

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
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.config.api_token}',
            'Content-Type': 'application/json',
            'Accept-Datetime-Format': 'RFC3339'
        })
        self.base_url = f"https://{self.config.hostname}/v3"
        logger.info("Order Executor initialized")
    
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
            url = f"{self.base_url}/accounts/{self.config.account_id}/orders"
            
            # Determine price precision (5 for most, 3 for JPY pairs)
            precision = 3 if 'JPY' in instrument else 5
            
            # Build order data
            order_data = {
                "order": {
                    "instrument": instrument,
                    "units": str(units),
                    "timeInForce": "GTC",
                    "positionFill": "DEFAULT",
                    "type": "MARKET"
                }
            }
            
            # Add stop loss if provided
            if stop_loss is not None:
                sl_price = round(stop_loss, precision)
                order_data["order"]["stopLossOnFill"] = {
                    "price": str(sl_price),
                    "timeInForce": "GTC"
                }
            
            # Add take profit if provided
            if take_profit is not None:
                tp_price = round(take_profit, precision)
                order_data["order"]["takeProfitOnFill"] = {
                    "price": str(tp_price),
                    "timeInForce": "GTC"
                }
            
            logger.info(f"Sending order to OANDA: {order_data}")
            
            response = self.session.post(url, json=order_data, timeout=10)
            
            # Log full response for debugging
            if response.status_code != 201:
                logger.error(f"OANDA API Error {response.status_code}: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            order_response = {
                'order_id': result.get('orderCreateTransaction', {}).get('id'),
                'instrument': instrument,
                'units': units,
                'direction': 'BUY' if units > 0 else 'SELL',
                'status': result.get('orderCreateTransaction', {}).get('reason'),
                'timestamp': datetime.now(),
                'success': True
            }
            
            # Get trade ID if filled
            if 'orderFillTransaction' in result:
                order_response['trade_id'] = result['orderFillTransaction'].get('tradeID')
                order_response['fill_price'] = float(result['orderFillTransaction'].get('price', 0))
            
            logger.info(f"Order placed: {instrument} {units} units - {order_response['order_id']}")
            return order_response
            
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
            url = f"{self.base_url}/accounts/{self.config.account_id}/orders"
            
            if order_type.upper() == 'LIMIT':
                oanda_type = 'LIMIT'
            elif order_type.upper() == 'STOP':
                oanda_type = 'STOP'
            else:
                raise ValueError(f"Invalid order type: {order_type}")
            
            order_data = {
                "order": {
                    "instrument": instrument,
                    "units": str(units),
                    "price": str(price),
                    "timeInForce": "GTC",
                    "positionFill": "OPEN",
                    "type": oanda_type
                }
            }
            
            # Add SL/TP if provided
            if stop_loss:
                order_data["order"]["stopLossOnFill"] = {
                    "price": str(stop_loss),
                    "timeInForce": "GTC"
                }
            
            if take_profit:
                order_data["order"]["takeProfitOnFill"] = {
                    "price": str(take_profit)
                }
            
            response = self.session.post(url, json=order_data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            order_response = {
                'order_id': result.get('orderCreateTransaction', {}).get('id'),
                'instrument': instrument,
                'units': units,
                'type': order_type,
                'price': price,
                'status': 'PENDING',
                'timestamp': datetime.now(),
                'success': True
            }
            
            logger.info(f"Pending order placed: {order_type} {instrument} @ {price}")
            return order_response
            
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
            url = f"{self.base_url}/accounts/{self.config.account_id}/trades/{trade_id}/close"
            
            response = self.session.put(url, json={}, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            close_data = {
                'trade_id': trade_id,
                'close_transaction_id': result.get('orderCreateTransaction', {}).get('id'),
                'pnl': result.get('orderFillTransaction', {}).get('pl'),
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
            url = f"{self.base_url}/accounts/{self.config.account_id}/trades/{trade_id}/orders"
            
            order_data = {
                "order": {
                    "tradeID": trade_id,
                    "price": str(stop_loss),
                    "type": "STOP_LOSS",
                    "timeInForce": "GTC"
                }
            }
            
            response = self.session.post(url, json=order_data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            mod_data = {
                'trade_id': trade_id,
                'new_stop_loss': stop_loss,
                'transaction_id': result.get('stopLossOrderTransaction', {}).get('id'),
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
            url = f"{self.base_url}/accounts/{self.config.account_id}/openTrades"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            trades = []
            for trade in data.get('trades', []):
                sl_order = trade.get('stopLossOrder', {})
                tp_order = trade.get('takeProfitOrder', {})
                
                trade_data = {
                    'trade_id': trade.get('id'),
                    'instrument': trade.get('instrument'),
                    'units': float(trade.get('currentUnits', 0)),
                    'avg_price': float(trade.get('price', 0)),
                    'unrealized_pl': float(trade.get('unrealizedPL', 0)),
                    'stop_loss': float(sl_order.get('price', 0)) if sl_order else None,
                    'take_profit': float(tp_order.get('price', 0)) if tp_order else None,
                    'open_time': trade.get('openTime')
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
            url = f"{self.base_url}/accounts/{self.config.account_id}/pendingOrders"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            orders = []
            for order in data.get('orders', []):
                order_data = {
                    'order_id': order.get('id'),
                    'instrument': order.get('instrument'),
                    'units': float(order.get('units', 0)),
                    'price': float(order.get('price', 0)) if order.get('price') else None,
                    'type': order.get('type'),
                    'state': order.get('state')
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
            url = f"{self.base_url}/accounts/{self.config.account_id}/orders/{order_id}/cancel"
            
            response = self.session.put(url, json={}, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            cancel_data = {
                'order_id': order_id,
                'cancel_transaction_id': result.get('orderCancelTransaction', {}).get('id'),
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
            url = f"{self.base_url}/accounts/{self.config.account_id}/pricing"
            params = {'instruments': instrument}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for price in data.get('prices', []):
                if price.get('instrument') == instrument:
                    bids = price.get('bids', [{}])
                    asks = price.get('asks', [{}])
                    if bids and asks:
                        bid = float(bids[0].get('price', 0))
                        ask = float(asks[0].get('price', 0))
                        return (bid + ask) / 2
        except Exception as e:
            logger.error(f"Error getting current price: {e}")
        return None
