#!/usr/bin/env python3
"""
Quick Start Script for Forex Trading Bot

This script helps you get started with the trading bot quickly.
"""
import os
import sys


def check_dependencies():
    """Check if all required packages are installed"""
    print("Checking dependencies...")
    required = ['v20', 'requests', 'bs4', 'lxml', 'pandas', 'numpy', 'talib']
    missing = []
    
    for package in required:
        try:
            if package == 'bs4':
                __import__('bs4')
            elif package == 'talib':
                __import__('talib')
            else:
                __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - MISSING")
            missing.append(package)
    
    if missing:
        print(f"\nMissing packages: {missing}")
        print("Install with: pip install " + " ".join(missing))
        return False
    
    print("\nAll dependencies installed!\n")
    return True


def check_credentials():
    """Check if OANDA credentials are set"""
    print("Checking OANDA credentials...")
    
    token = os.getenv('OANDA_API_TOKEN')
    account_id = os.getenv('OANDA_ACCOUNT_ID')
    
    if token and account_id:
        print(f"  ✓ API Token: {token[:10]}...{token[-5:]}")
        print(f"  ✓ Account ID: {account_id}")
        print("\nCredentials found!\n")
        return True
    else:
        print("\n⚠ Credentials not set!")
        print("\nTo set credentials, use:")
        print("  export OANDA_API_TOKEN='your_token_here'")
        print("  export OANDA_ACCOUNT_ID='your_account_id_here'")
        print("\nOr edit config.py directly.\n")
        return False


def show_config():
    """Show current configuration"""
    from config import DEFAULT_TRADING_CONFIG, Timeframe
    
    print("Current Configuration:")
    print(f"  Primary Timeframe: {DEFAULT_TRADING_CONFIG.primary_timeframe.value}")
    print(f"  Secondary Timeframe: {DEFAULT_TRADING_CONFIG.secondary_timeframe.value}")
    print(f"  Currency Pairs: {[p.value for p in DEFAULT_TRADING_CONFIG.pairs]}")
    print(f"  Risk per Trade: {DEFAULT_TRADING_CONFIG.risk_per_trade * 100}%")
    print(f"  Max Positions: {DEFAULT_TRADING_CONFIG.max_positions}")
    print(f"  Stop Loss: {DEFAULT_TRADING_CONFIG.stop_loss_pips} pips")
    print(f"  Take Profit: {DEFAULT_TRADING_CONFIG.take_profit_pips} pips")
    print(f"  Use Sentiment: {DEFAULT_TRADING_CONFIG.use_sentiment}")
    print(f"  Check Interval: {DEFAULT_TRADING_CONFIG.check_interval_seconds}s\n")


def main():
    print("=" * 60)
    print("FOREX TRADING BOT - QUICK START")
    print("=" * 60)
    print()
    
    # Check dependencies
    deps_ok = check_dependencies()
    if not deps_ok:
        sys.exit(1)
    
    # Show configuration
    show_config()
    
    # Check credentials (warning only, not fatal)
    creds_ok = check_credentials()
    
    print("=" * 60)
    print("READY TO START")
    print("=" * 60)
    print()
    print("To start the bot:")
    print("  python trading_bot.py")
    print()
    print("To stop the bot:")
    print("  Press Ctrl+C")
    print()
    
    if not creds_ok:
        print("⚠ WARNING: You need to set OANDA credentials before running!")
        print()
    
    # Optionally start the bot
    if len(sys.argv) > 1 and sys.argv[1] == '--start':
        if creds_ok:
            print("Starting bot...\n")
            from trading_bot import main as bot_main
            bot_main()
        else:
            print("Cannot start without credentials!")
            sys.exit(1)


if __name__ == "__main__":
    main()
