"""
Sentiment Analysis Module - Fetches market sentiment from external sources
Uses web scraping and free APIs (no NLP)
"""
import logging
from typing import Dict, Optional, Tuple
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """
    Analyzes market sentiment using external data sources
    Does NOT use NLP - uses numerical sentiment data only
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_investing_sentiment(self, pair: str) -> Optional[Dict]:
        """
        Get sentiment from Investing.com technical analysis
        
        Args:
            pair: Currency pair (e.g., "EURUSD")
            
        Returns:
            Dictionary with sentiment scores
        """
        # Mapping for Investing.com URLs
        pair_mapping = {
            'EUR_USD': 'eur-usd',
            'GBP_USD': 'gbp-usd',
            'USD_JPY': 'usd-jpy',
            'AUD_USD': 'aud-usd',
            'USD_CAD': 'usd-cad',
            'USD_CHF': 'usd-chf',
            'NZD_USD': 'nzd-usd'
        }
        
        try:
            investing_pair = pair_mapping.get(pair, pair.replace('_', '').lower())
            url = f"https://www.investing.com/currencies/{investing_pair}-technical"
            
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find technical summary
            sentiment_data = {}
            
            # Look for the technical summary table
            tech_table = soup.find('table', {'class': 'technicalIndicatorsTbl'})
            if tech_table:
                # Extract buy/sell/neutral counts
                summary_row = tech_table.find('tr', {'class': 'summary'})
                if summary_row:
                    spans = summary_row.find_all('span')
                    for span in spans:
                        text = span.get_text().strip().lower()
                        if 'strong buy' in text or 'buy' in text:
                            sentiment_data['signal'] = 'BUY'
                        elif 'strong sell' in text or 'sell' in text:
                            sentiment_data['signal'] = 'SELL'
                        elif 'neutral' in text:
                            sentiment_data['signal'] = 'NEUTRAL'
            
            # Try to find percentage breakdown
            percent_spans = soup.find_all('span', class_='pairTechPercent')
            if len(percent_spans) >= 3:
                try:
                    sentiment_data['buy_percent'] = float(percent_spans[0].get_text().replace('%', '')) / 100
                    sentiment_data['sell_percent'] = float(percent_spans[1].get_text().replace('%', '')) / 100
                    sentiment_data['neutral_percent'] = float(percent_spans[2].get_text().replace('%', '')) / 100
                except (ValueError, IndexError):
                    pass
            
            if sentiment_data:
                sentiment_data['source'] = 'investing.com'
                sentiment_data['timestamp'] = datetime.now()
                return sentiment_data
                
        except Exception as e:
            logger.warning(f"Failed to fetch Investing.com sentiment: {e}")
        
        return None
    
    def get_myfxbook_sentiment(self, pair: str) -> Optional[Dict]:
        """
        Get retail sentiment from MyFxBook (if available)
        
        Note: MyFxBook requires authentication for API access
        This is a placeholder for when you have API credentials
        """
        # This would require API key from MyFxBook
        # For now, return None and rely on other sources
        logger.debug("MyFxBook sentiment requires API key - skipping")
        return None
    
    def calculate_sentiment_score(self, pair: str) -> Optional[float]:
        """
        Calculate overall sentiment score from multiple sources
        
        Args:
            pair: Currency pair
            
        Returns:
            Sentiment score between -1 (very bearish) and 1 (very bullish)
        """
        scores = []
        weights = []
        
        # Get Investing.com sentiment
        investing_data = self.get_investing_sentiment(pair)
        if investing_data:
            if 'buy_percent' in investing_data and 'sell_percent' in investing_data:
                # Calculate score from percentages
                score = investing_data['buy_percent'] - investing_data['sell_percent']
                scores.append(score)
                weights.append(0.7)  # Higher weight for percentage-based data
            
            # Also consider signal direction
            if 'signal' in investing_data:
                signal_score = {
                    'BUY': 0.5,
                    'STRONG_BUY': 0.8,
                    'NEUTRAL': 0.0,
                    'SELL': -0.5,
                    'STRONG_SELL': -0.8
                }.get(investing_data['signal'].upper(), 0.0)
                scores.append(signal_score)
                weights.append(0.3)
        
        if not scores:
            return None
        
        # Calculate weighted average
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        
        return weighted_score
    
    def get_sentiment_for_pairs(self, pairs: list) -> Dict[str, Dict]:
        """
        Get sentiment for multiple currency pairs
        
        Args:
            pairs: List of currency pairs
            
        Returns:
            Dictionary mapping pairs to sentiment data
        """
        results = {}
        
        for pair in pairs:
            try:
                score = self.calculate_sentiment_score(pair)
                
                if score is not None:
                    results[pair] = {
                        'score': score,
                        'bullish': score > 0.2,
                        'bearish': score < -0.2,
                        'neutral': abs(score) <= 0.2,
                        'strength': abs(score)
                    }
                else:
                    results[pair] = {
                        'score': 0.0,
                        'bullish': False,
                        'bearish': False,
                        'neutral': True,
                        'strength': 0.0,
                        'available': False
                    }
                    
            except Exception as e:
                logger.error(f"Error getting sentiment for {pair}: {e}")
                results[pair] = {
                    'score': 0.0,
                    'bullish': False,
                    'bearish': False,
                    'neutral': True,
                    'strength': 0.0,
                    'error': str(e)
                }
        
        return results
    
    def should_trade_based_on_sentiment(self, pair: str, 
                                        direction: str,
                                        threshold: float = 0.6) -> bool:
        """
        Determine if we should trade based on sentiment alignment
        
        Args:
            pair: Currency pair
            direction: 'BUY' or 'SELL'
            threshold: Minimum sentiment strength required
            
        Returns:
            True if sentiment supports the trade
        """
        sentiment_data = self.calculate_sentiment_score(pair)
        
        if sentiment_data is None:
            return True  # No sentiment data, allow trade
        
        if direction == 'BUY':
            return sentiment_data >= threshold
        elif direction == 'SELL':
            return sentiment_data <= -threshold
        
        return False
