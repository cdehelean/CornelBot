"""
Cornels_Cryptobot - Automated trading bot for hourly Bitcoin markets.

Usage:
    python Cornels_Cryptobot.py

The bot:
1. Asks for a market URL at start
2. Checks for positions, creates split positions if none exist ($5 USD)
3. Monitors positions every minute
4. 7 minutes before hour end: closes losing position if price < 0.90
5. At hour end: closes all remaining positions
6. Updates URL to next hour and restarts

Requirements:
    Python 3.9 or higher
"""

import os
import sys

# Check Python version
if sys.version_info < (3, 9):
    print("=" * 80)
    print("ERROR: Python 3.9 or higher is required!")
    print("=" * 80)
    print(f"Current Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print("")
    print("py-clob-client requires Python 3.9+")
    print("")
    print("Please upgrade Python:")
    print("  - Download from: https://www.python.org/downloads/")
    print("  - Or use pyenv: https://github.com/pyenv/pyenv")
    print("")
    sys.exit(1)
import re
import json
import time
import base64
import urllib.request
import asyncio
import threading
import queue
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, List

# Telegram imports
try:
    from telegram import Bot
    TELEGRAM_AVAILABLE = True
except ImportError as e:
    TELEGRAM_AVAILABLE = False
    print(f"Warning: python-telegram-bot not available. Telegram notifications disabled.")
    print(f"  Error: {e}")
    print(f"  To install: pip install python-telegram-bot")

# Try to use timezone libraries, fallback to manual calculation
ET_TZ = None
USE_ZONEINFO = False
USE_PYTZ = False

try:
    import pytz
    ET_TZ = pytz.timezone('US/Eastern')
    USE_PYTZ = True
except ImportError:
    try:
        from zoneinfo import ZoneInfo
        ET_TZ = ZoneInfo('America/New_York')
        USE_ZONEINFO = True
    except (ImportError, Exception):
        # Fallback: will use UTC offset calculation
        ET_TZ = None

# Required dependencies - check if installed
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds, MarketOrderArgs, OrderType, TradeParams, RequestArgs
    from py_clob_client.order_builder.constants import BUY, SELL
    from py_clob_client.headers.headers import create_level_2_headers, POLY_ADDRESS, POLY_API_KEY, POLY_PASSPHRASE, POLY_SIGNATURE, POLY_TIMESTAMP
    from py_clob_client.constants import POLYGON
    CLOB_CLIENT_AVAILABLE = True
except ImportError as e:
    CLOB_CLIENT_AVAILABLE = False
    print("=" * 80)
    print("ERROR: Required dependency 'py-clob-client' is not installed.")
    print("=" * 80)
    print("Please install dependencies by running:")
    print("  pip install -r requirements.txt")
    print("")
    print("Or install manually:")
    print("  pip install py-clob-client python-dotenv")
    print("")
    print(f"Import error: {e}")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("=" * 80)
    print("ERROR: Required dependency 'python-dotenv' is not installed.")
    print("=" * 80)
    print("Please install dependencies by running:")
    print("  pip install -r requirements.txt")
    print("")
    print("Or install manually:")
    print("  pip install python-dotenv")
    sys.exit(1)

from collections import defaultdict

if DOTENV_AVAILABLE:
    load_dotenv()

# Telegram configuration (from .env file)
TELEGRAM_BOT_TOKEN = os.getenv('BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID', '')


def initialize_client() -> Optional[ClobClient]:
    """Initialize and return ClobClient."""
    key = os.getenv("PK")
    api_key = os.getenv("CLOB_API_KEY")
    api_secret = os.getenv("CLOB_SECRET")
    api_passphrase = os.getenv("CLOB_PASS_PHRASE")
    
    if not all([key, api_key, api_secret, api_passphrase]):
        print("Error: Missing required environment variables.")
        print("Please set the following in your .env file:")
        print("  PK=your_private_key")
        print("  CLOB_API_KEY=your_api_key")
        print("  CLOB_SECRET=your_api_secret")
        print("  CLOB_PASS_PHRASE=your_passphrase")
        return None
    
    api_secret = api_secret.strip()
    
    host = os.getenv("CLOB_API_URL", "https://clob.polymarket.com")
    creds = ApiCreds(
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase,
    )
    chain_id = int(os.getenv("CHAIN_ID", POLYGON))
    
    signature_type = os.getenv("SIGNATURE_TYPE")
    funder = os.getenv("FUNDER")
    
    if signature_type:
        signature_type = int(signature_type)
    elif funder:
        signature_type = 2
    
    try:
        client_kwargs = {
            "host": host,
            "key": key,
            "chain_id": chain_id,
            "creds": creds,
        }
        if signature_type is not None:
            client_kwargs["signature_type"] = signature_type
        if funder:
            client_kwargs["funder"] = funder
        
        return ClobClient(**client_kwargs)
    except Exception as e:
        print(f"Error initializing client: {e}")
        return None


def extract_market_id_from_url(url: str) -> Optional[str]:
    """Extract market ID (condition_id or slug) from Polymarket URL."""
    if not url:
        return None
    
    if re.match(r'^0x[a-fA-F0-9]+$', url.strip()):
        return url.strip()
    
    patterns = [
        r'polymarket\.com/(?:event|market)/([a-zA-Z0-9_-]+)',
        r'polymarket\.com/(?:event|market)/(0x[a-fA-F0-9]+)',
        r'/([a-zA-Z0-9_-]+)(?:\?|$)',
        r'/(0x[a-fA-F0-9]+)(?:\?|$)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return url.strip() if url.strip() else None


def get_market_from_gamma_api(slug: str) -> Optional[Dict]:
    """Get market information from Gamma API using slug."""
    if not slug:
        return None
    
    try:
        url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
        req = urllib.request.Request(url, headers={"User-Agent": "py-clob-client/Cornels_Cryptobot"})
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data
    except Exception as e:
        print(f"Error fetching from Gamma API: {e}")
        return None


def get_market_info(client: ClobClient, market_identifier: str) -> Optional[Dict]:
    """Get market information by condition_id or slug."""
    if not market_identifier:
        return None
    
    is_condition_id = market_identifier.startswith("0x") and len(market_identifier) > 10
    
    if is_condition_id:
        try:
            market = client.get_market(market_identifier)
            return market
        except Exception as e:
            print(f"Error fetching market {market_identifier}: {e}")
            return None
    else:
        gamma_data = get_market_from_gamma_api(market_identifier)
        
        if gamma_data:
            condition_id = gamma_data.get("conditionId")
            if condition_id:
                try:
                    market = client.get_market(condition_id)
                    return market
                except Exception as e:
                    print(f"Error fetching market from CLOB API: {e}")
                    return gamma_data
            else:
                return gamma_data
        else:
            try:
                market = client.get_market(market_identifier)
                return market
            except Exception:
                return None


def get_token_ids_from_market(market: Dict) -> List[Tuple[str, str]]:
    """Extract token IDs and outcomes from market."""
    tokens = market.get("tokens") or market.get("clobTokenIds") or []
    result = []
    
    for token in tokens:
        token_id = token if isinstance(token, str) else token.get("token_id") or token.get("tokenId") or str(token)
        outcome = token.get("outcome") if isinstance(token, dict) else None
        if not outcome and isinstance(token, dict):
            outcome = token.get("outcome") or token.get("label") or "Unknown"
        result.append((token_id, outcome or "Unknown"))
    
    return result


def get_positions_from_trades(client: ClobClient) -> Dict[str, Dict]:
    """Get positions by aggregating trades."""
    try:
        address = os.getenv("FUNDER") or client.get_address()
        trades = client.get_trades()
        
        user_trades = []
        for trade in trades:
            maker = trade.get("maker") or trade.get("maker_address")
            taker = trade.get("taker") or trade.get("taker_address")
            if maker and maker.lower() == address.lower():
                user_trades.append(trade)
            elif taker and taker.lower() == address.lower():
                user_trades.append(trade)
        
        positions = defaultdict(lambda: {
            "total_shares": 0.0,
            "total_cost": 0.0,
            "token_id": None,
            "market": None,
        })
        
        for trade in user_trades:
            token_id = trade.get("token_id") or trade.get("asset_id") or trade.get("token")
            if not token_id:
                continue
            
            side = (trade.get("side") or trade.get("order_side") or "").upper()
            size = float(trade.get("size") or trade.get("amount") or trade.get("shares") or 0)
            price = float(trade.get("price") or trade.get("execution_price") or 0)
            
            if side == "BUY" or side == "MAKER_BUY" or (not side and size > 0):
                positions[token_id]["total_shares"] += size
                positions[token_id]["total_cost"] += size * price
            elif side == "SELL" or side == "MAKER_SELL":
                positions[token_id]["total_shares"] -= size
                positions[token_id]["total_cost"] -= size * price
            
            if not positions[token_id]["token_id"]:
                positions[token_id]["token_id"] = token_id
                positions[token_id]["market"] = trade.get("market") or trade.get("condition_id")
        
        result = {
            token_id: pos for token_id, pos in positions.items()
            if pos["total_shares"] > 0
        }
        
        return result
    except Exception as e:
        print(f"Error fetching positions: {e}")
        return {}


def get_market_positions(client: ClobClient, market: Dict) -> List[Dict]:
    """Get active positions for the current market."""
    if not client:
        return []
    
    all_positions = get_positions_from_trades(client)
    
    if not all_positions:
        return []
    
    condition_id = market.get("condition_id") or market.get("conditionId")
    market_token_ids = []
    
    if market.get("tokens"):
        for token in market.get("tokens", []):
            if isinstance(token, dict):
                tid = token.get("token_id") or token.get("tokenId")
                if tid:
                    market_token_ids.append(str(tid))
    
    clob_token_ids = market.get("clobTokenIds") or []
    for tid in clob_token_ids:
        if tid:
            market_token_ids.append(str(tid))
    
    token_outcomes = get_token_ids_from_market(market)
    for tid, _ in token_outcomes:
        if tid and str(tid) not in market_token_ids:
            market_token_ids.append(str(tid))
    
    market_positions = []
    
    for token_id, pos in all_positions.items():
        pos_condition_id = pos.get("market")
        
        matches_by_condition = False
        if pos_condition_id and condition_id:
            if str(pos_condition_id) == str(condition_id) or str(pos_condition_id).lower() == str(condition_id).lower():
                matches_by_condition = True
        
        matches_by_token = str(token_id) in market_token_ids
        
        if matches_by_condition or matches_by_token:
            current_price = 0
            # Try get_midpoint first (returns {'mid': '0.55'})
            try:
                midpoint = client.get_midpoint(token_id)
                if midpoint and isinstance(midpoint, dict):
                    # API returns 'mid' key, not 'midpoint'
                    current_price = float(midpoint.get("mid", midpoint.get("midpoint", 0)))
                elif isinstance(midpoint, (int, float)):
                    current_price = float(midpoint)
            except Exception as e:
                # Fallback to get_price if get_midpoint fails
                try:
                    price_resp = client.get_price(token_id, "BUY")
                    if price_resp and isinstance(price_resp, dict):
                        current_price = float(price_resp.get("price", 0))
                except Exception as e2:
                    print(f"    Warning: Could not get price for token {token_id}: {e}, {e2}")
                    current_price = 0
            
            shares = pos["total_shares"]
            
            # Skip positions with less than 1 share
            if shares < 1.0:
                continue
            
            total_cost = pos["total_cost"]
            avg_price = total_cost / shares if shares > 0 else 0
            current_value = shares * current_price if current_price > 0 else 0
            pnl = current_value - total_cost
            pnl_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            
            outcome = None
            for tid, out in get_token_ids_from_market(market):
                if str(tid) == str(token_id):
                    outcome = out
                    break
            
            market_positions.append({
                "token_id": token_id,
                "outcome": outcome or "Unknown",
                "shares": shares,
                "avg_price": avg_price,
                "current_price": current_price,
                "current_value": current_value,
                "total_cost": total_cost,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            })
    
    return market_positions


def create_split_position(client: ClobClient, market: Dict, amount_usd: float = 5.0) -> bool:
    """Create split positions by buying equal dollar amounts of all outcomes."""
    token_outcomes = get_token_ids_from_market(market)
    
    if len(token_outcomes) < 2:
        print(f"Error: Split position requires at least 2 outcomes, found {len(token_outcomes)}")
        return False
    
    print(f"\nCreating split positions: Buying ${amount_usd:.2f} worth of each outcome...")
    
    success_count = 0
    orders_placed = []
    
    for token_id, outcome in token_outcomes:
        try:
            print(f"Placing order for {outcome}...")
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount_usd,
                side=BUY,
            )
            
            signed_order = client.create_market_order(order_args)
            resp = client.post_order(signed_order, OrderType.FOK)
            
            order_id = resp.get('id', 'N/A')
            print(f"  ✅ Order placed: {order_id}")
            success_count += 1
            orders_placed.append(f"{outcome}: Order {order_id}")
            
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ Error placing order for {outcome}: {error_msg}")
    
    print(f"\nSplit positions created: {success_count}/{len(token_outcomes)} orders placed")
    
    # Send Telegram notification
    if success_count > 0:
        market_name = market.get("question") or market.get("title") or "Market"
        message = f"🟢 *Position Opened*\n\n"
        message += f"Market: {market_name}\n"
        message += f"Amount: ${amount_usd:.2f} per outcome\n"
        message += f"Orders placed: {success_count}/{len(token_outcomes)}\n\n"
        message += "\n".join(orders_placed)
        send_telegram_notification(message)
    
    return success_count == len(token_outcomes)


def close_position_with_retry(client: ClobClient, token_id: str, shares: float, outcome: str = "Unknown", max_retries: int = 10, position_info: Optional[Dict] = None) -> bool:
    """Close a position by selling all shares, with retry logic."""
    # Skip positions with less than 1 share
    if shares < 1.0:
        print(f"⚠️ Skipping position ({outcome}): Shares ({shares:.4f}) is below 1.0")
        return False
    
    for attempt in range(1, max_retries + 1):
        try:
            if attempt == 1:
                print(f"\nClosing position ({outcome}): Selling {shares:.4f} shares...")
            else:
                print(f"\nRetry attempt {attempt}/{max_retries}: Closing position ({outcome})...")
            
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=shares,
                side=SELL,
            )
            
            signed_order = client.create_market_order(order_args)
            resp = client.post_order(signed_order, OrderType.FOK)
            
            order_id = resp.get('id', 'N/A')
            print(f"✅ Position closed successfully! Order ID: {order_id}")
            
            # Send Telegram notification
            if position_info:
                pnl = position_info.get("pnl", 0)
                pnl_pct = position_info.get("pnl_pct", 0)
                pnl_sign = "📈" if pnl >= 0 else "📉"
                message = f"🔴 *Position Closed*\n\n"
                message += f"Outcome: *{outcome}*\n"
                message += f"Shares: {shares:.4f}\n"
                message += f"Order ID: {order_id}\n"
                message += f"P&L: {pnl_sign} ${pnl:.2f} ({pnl_pct:.2f}%)"
                send_telegram_notification(message)
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error on attempt {attempt}: {error_msg}")
            
            if attempt < max_retries:
                wait_time = min(2 ** attempt, 10)
                print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                print(f"\n❌ Failed to close position after {max_retries} attempts.")
                return False
    
    return False


def get_market_end_time(market: Dict) -> Optional[datetime]:
    """Get the market end time from market data. Returns timezone-naive datetime."""
    end_date = market.get("end_date_iso") or market.get("endDate") or market.get("endDateISO")
    if not end_date:
        return None
    
    try:
        # Parse ISO format datetime
        if 'T' in end_date:
            # Handle timezone-aware datetime
            if end_date.endswith('Z'):
                # UTC timezone
                dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                # Convert to naive UTC (remove timezone info)
                dt = dt.replace(tzinfo=None)
            elif '+' in end_date or end_date.count('-') > 2:
                # Has timezone offset
                dt = datetime.fromisoformat(end_date)
                # Convert to naive by removing timezone
                dt = dt.replace(tzinfo=None)
            else:
                # No timezone, parse as naive
                dt = datetime.fromisoformat(end_date)
        else:
            dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        return dt
    except Exception as e:
        print(f"Error parsing end date '{end_date}': {e}")
        return None


def update_url_to_next_hour(url: str) -> Optional[str]:
    """Update the URL to the next hour (e.g., 8am -> 9am, 11am -> 12pm)."""
    # Pattern: bitcoin-up-or-down-january-16-8am-et
    # Handle various hour formats
    
    def increment_am_hour(match):
        hour = int(match.group(1))
        if hour == 11:
            return "12pm-et"
        elif hour == 12:
            return "1pm-et"
        else:
            return f"{hour + 1}am-et"
    
    def increment_pm_hour(match):
        hour = int(match.group(1))
        if hour == 11:
            return "12am-et"
        elif hour == 12:
            return "1am-et"
        else:
            return f"{hour + 1}pm-et"
    
    patterns = [
        (r'(\d+)am-et', increment_am_hour),
        (r'(\d+)pm-et', increment_pm_hour),
        (r'(\d{1,2}):(\d{2})', lambda m: f"{(int(m.group(1)) + 1) % 24}:{m.group(2)}"),
    ]
    
    for pattern, replacer in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            new_hour = replacer(match)
            new_url = url[:match.start()] + new_hour + url[match.end():]
            return new_url
    
    # If no hour pattern found, try to increment date
    # This is a fallback - might need adjustment based on actual URL format
    return None


def send_telegram_notification(message: str):
    """Send a notification to Telegram (synchronous wrapper)."""
    if not TELEGRAM_AVAILABLE:
        print("⚠️ Telegram not available (python-telegram-bot not installed)")
        return
    
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ Telegram BOT_TOKEN not set in .env")
        return
    
    if not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram CHAT_ID not set in .env")
        return
    
    try:
        print(f"📤 Sending Telegram notification...")
        
        # Use threading to avoid event loop conflicts
        import threading
        import queue
        
        result_queue = queue.Queue()
        error_queue = queue.Queue()
        
        def run_telegram():
            try:
                async def send_async():
                    bot = Bot(token=TELEGRAM_BOT_TOKEN)
                    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
                
                asyncio.run(send_async())
                result_queue.put(True)
            except Exception as e:
                error_queue.put(e)
        
        thread = threading.Thread(target=run_telegram, daemon=False)
        thread.start()
        thread.join(timeout=10)  # Wait max 10 seconds
        
        if thread.is_alive():
            print("⚠️ Telegram send timed out")
            return
        
        if not error_queue.empty():
            error = error_queue.get()
            raise error
        
        if not result_queue.empty():
            print(f"✅ Telegram notification sent")
        else:
            print("⚠️ Telegram send completed but no confirmation")
            
    except Exception as e:
        print(f"⚠️ Warning: Failed to send Telegram notification: {e}")
        import traceback
        traceback.print_exc()


def format_positions_for_telegram(positions: List[Dict]) -> str:
    """Format positions for Telegram message."""
    if not positions:
        return "No positions found."
    
    lines = ["📊 *Current Positions:*\n"]
    total_pnl = 0
    total_value = 0
    
    for i, pos in enumerate(positions, 1):
        pnl_sign = "📈" if pos["pnl"] >= 0 else "📉"
        lines.append(f"{pnl_sign} *{pos['outcome']}*")
        lines.append(f"  Shares: {pos['shares']:.4f}")
        lines.append(f"  Price: ${pos['current_price']:.4f}")
        lines.append(f"  Value: ${pos['current_value']:.2f}")
        lines.append(f"  P&L: ${pos['pnl']:.2f} ({pos['pnl_pct']:.2f}%)")
        lines.append("")
        total_pnl += pos["pnl"]
        total_value += pos["current_value"]
    
    lines.append(f"*Total Value:* ${total_value:.2f}")
    lines.append(f"*Total P&L:* ${total_pnl:.2f}")
    
    return "\n".join(lines)


def display_positions(positions: List[Dict]):
    """Display current positions."""
    print("\n" + "=" * 80)
    print("CURRENT POSITIONS")
    print("=" * 80)
    
    if not positions:
        print("No positions found.")
        return
    
    for i, pos in enumerate(positions, 1):
        pnl_sign = "+" if pos["pnl"] >= 0 else ""
        print(f"\nPosition {i}: {pos['outcome']}")
        print(f"  Shares: {pos['shares']:.4f}")
        print(f"  Avg Buy Price: ${pos['avg_price']:.4f}")
        print(f"  Current Price: ${pos['current_price']:.4f}")
        print(f"  Current Value: ${pos['current_value']:.2f}")
        print(f"  Total Cost: ${pos['total_cost']:.2f}")
        print(f"  P&L: {pnl_sign}${pos['pnl']:.2f} ({pnl_sign}{pos['pnl_pct']:.2f}%)")
    
    print("=" * 80)


def get_eastern_time() -> datetime:
    """Get current time in Eastern Time zone."""
    if USE_PYTZ and ET_TZ:
        return datetime.now(ET_TZ)
    elif USE_ZONEINFO and ET_TZ:
        return datetime.now(ET_TZ)
    else:
        # Fallback: Calculate ET from UTC
        # ET is UTC-5 (EST) or UTC-4 (EDT)
        # Simple approach: use UTC-5 (EST) - this is approximate
        # For more accuracy, you'd need to handle DST
        utc_now = datetime.utcnow()
        # EST is UTC-5, but we'll use a simple offset
        # Note: This doesn't handle DST, but is close enough for the URL generation
        et_offset = timedelta(hours=-5)
        et_now = utc_now + et_offset
        return et_now.replace(tzinfo=None)


def generate_default_url() -> str:
    """Generate default URL based on current Eastern Time."""
    try:
        # Get current time in Eastern Time zone
        et_now = get_eastern_time()
        
        # Month as text (lowercase)
        month_names = {
            1: 'january', 2: 'february', 3: 'march', 4: 'april',
            5: 'may', 6: 'june', 7: 'july', 8: 'august',
            9: 'september', 10: 'october', 11: 'november', 12: 'december'
        }
        month_text = month_names[et_now.month]
        
        # Day as number
        day = et_now.day
        
        # Hour in 12-hour format with am/pm
        hour_12 = et_now.hour % 12
        if hour_12 == 0:
            hour_12 = 12
        am_pm = 'am' if et_now.hour < 12 else 'pm'
        
        # Construct URL
        url_slug = f"bitcoin-up-or-down-{month_text}-{day}-{hour_12}{am_pm}-et"
        url = f"https://polymarket.com/event/{url_slug}"
        
        return url
    except Exception as e:
        print(f"Error generating default URL: {e}")
        return "https://polymarket.com/event/bitcoin-up-or-down-january-16-8am-et"


def main():
    """Main bot loop."""
    print("=" * 80)
    print("CORNELS_CRYPTOBOT")
    print("=" * 80)
    
    # Send startup notification
    send_telegram_notification("🚀 *Cornels Cryptobot Started*\n\nBot is initializing...")
    
    client = initialize_client()
    if not client:
        print("Error: Failed to initialize client")
        send_telegram_notification("❌ *Bot Error*\n\nFailed to initialize client. Check credentials.")
        return
    
    # Generate and propose default URL
    default_url = generate_default_url()
    print(f"\nProposed URL (based on current Eastern Time):")
    print(f"  {default_url}")
    print("\nEnter the Polymarket URL for the market (or press Enter to use proposed URL):")
    url = input("URL: ").strip()
    
    if not url:
        url = default_url
        print(f"Using proposed URL: {url}")
    
    if not url:
        print("Error: No URL provided")
        send_telegram_notification("❌ *Bot Error*\n\nNo URL provided. Bot stopped.")
        return
    
    # Send notification with starting URL
    send_telegram_notification(f"🟢 *Bot Running*\n\nStarting with market:\n{url}")
    
    # Main loop
    while True:
        try:
            print(f"\n{'='*80}")
            print(f"Processing market: {url}")
            print(f"{'='*80}")
            
            # Extract market identifier
            market_identifier = extract_market_id_from_url(url)
            if not market_identifier:
                print(f"Error: Could not extract market identifier from: {url}")
                break
            
            # Get market info
            print("\nFetching market information...")
            market = get_market_info(client, market_identifier)
            
            if not market:
                print(f"Error: Could not fetch market information for: {market_identifier}")
                break
            
            market_question = market.get("question") or market.get("title") or "Unknown"
            print(f"Market: {market_question}")
            
            # Calculate end time as the next full hour from now
            current_time = datetime.now().replace(tzinfo=None)
            # Round up to next hour: add 1 hour, then set minutes/seconds to 0
            next_hour = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            end_time = next_hour
            
            print(f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"End time (next full hour): {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Wait 1 minute before checking positions (for new cycle)
            print("\n⏳ Waiting 1 minute before checking positions...")
            for remaining in range(60, 0, -10):
                print(f"  {remaining} seconds remaining...", end='\r', flush=True)
                time.sleep(10)
            print("  Checking positions now...                    ")  # Clear the line
            
            # Check for existing positions
            print("\nChecking for existing positions...")
            positions = get_market_positions(client, market)
            
            if not positions:
                print("No positions found. Creating split positions...")
                if not create_split_position(client, market, amount_usd=5.0):
                    print("Error: Failed to create split positions")
                    break
                # Wait a bit for orders to fill
                time.sleep(5)
                positions = get_market_positions(client, market)
            
            if len(positions) < 2:
                print(f"Warning: Expected 2 positions, found {len(positions)}")
            
            # Monitoring loop
            print("\nStarting monitoring loop (checking every minute)...")
            last_telegram_update = time.time()
            telegram_update_interval = 300  # 5 minutes in seconds
            
            while True:
                # Get current time as timezone-naive
                current_time = datetime.now().replace(tzinfo=None)
                time_until_end = (end_time - current_time).total_seconds()
                
                if time_until_end <= 0:
                    print("\n⏰ Market hour ended! Closing all positions...")
                    break
                
                minutes_until_end = time_until_end / 60
                
                # Refresh positions
                positions = get_market_positions(client, market)
                display_positions(positions)
                
                print(f"\n⏱️  Time until end: {int(minutes_until_end)} minutes ({int(time_until_end)} seconds)")
                
                # Send Telegram update every 5 minutes
                current_timestamp = time.time()
                if current_timestamp - last_telegram_update >= telegram_update_interval:
                    if positions:
                        message = f"⏰ *Status Update*\n\n"
                        message += f"Time until end: {int(minutes_until_end)} minutes\n\n"
                        message += format_positions_for_telegram(positions)
                        send_telegram_notification(message)
                    last_telegram_update = current_timestamp
                
                # 7 minutes before end: close losing position if price < 0.90
                if 7 <= minutes_until_end < 8:
                    print("\n🔔 7 minutes before end - checking for losing positions...")
                    
                    if len(positions) >= 2:
                        # Find losing position
                        losing_pos = min(positions, key=lambda p: p["pnl"])
                        
                        if losing_pos["current_price"] < 0.30:
                            print(f"\nClosing losing position: {losing_pos['outcome']} (Price: ${losing_pos['current_price']:.4f})")
                            close_position_with_retry(
                                client,
                                losing_pos["token_id"],
                                losing_pos["shares"],
                                losing_pos["outcome"],
                                position_info=losing_pos
                            )
                            # Remove from positions list
                            positions = [p for p in positions if p["token_id"] != losing_pos["token_id"]]
                        else:
                            print(f"Losing position price (${losing_pos['current_price']:.4f}) is >= 0.90, not closing")
                
                # At hour end: close all remaining positions
                if minutes_until_end <= 1:
                    print("\n⏰ Hour ending! Closing all remaining positions...")
                    for pos in positions:
                        close_position_with_retry(
                            client,
                            pos["token_id"],
                            pos["shares"],
                            pos["outcome"],
                            position_info=pos
                        )
                    break
                
                # Wait 1 minute before next check (with progress indicator)
                print("\nWaiting 60 seconds until next check...")
                for remaining in range(60, 0, -10):
                    print(f"  {remaining} seconds remaining...", end='\r', flush=True)
                    time.sleep(10)
                print("  Checking now...                    ")  # Clear the line
            
            # Update URL to next hour
            print("\n🔄 Updating URL to next hour...")
            new_url = update_url_to_next_hour(url)
            
            if new_url:
                url = new_url
                print(f"New URL: {url}")
            else:
                print("Error: Could not update URL to next hour")
                print("Please enter the next hour's URL manually:")
                url = input("URL: ").strip()
                if not url:
                    break
            
            # Wait a bit before starting next cycle
            print("\nWaiting 10 seconds before starting next cycle...")
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\n\nBot stopped by user.")
            send_telegram_notification("⏹️ *Bot Stopped*\n\nBot stopped by user.")
            break
        except Exception as e:
            print(f"\nError in main loop: {e}")
            import traceback
            traceback.print_exc()
            send_telegram_notification(f"⚠️ *Bot Error*\n\nError: {str(e)}\n\nRetrying in 30 seconds...")
            print("\nWaiting 30 seconds before retrying...")
            time.sleep(30)
    
    # Send shutdown notification
    send_telegram_notification("🔴 *Bot Shutdown*\n\nCornels Cryptobot has stopped.")


if __name__ == "__main__":
    main()
