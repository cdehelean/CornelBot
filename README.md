# Cornels Cryptobot

Automated trading bot for hourly Bitcoin markets on Polymarket.

## ⚠️ Requirements

**Python 3.9 or higher is required!**

py-clob-client does not support Python 3.8 or lower. Please upgrade if needed.

## Features

- Automated position management for hourly Bitcoin markets
- Creates split positions ($5 USD per outcome) if none exist
- Monitors positions every minute
- Closes losing positions 7 minutes before hour end if price < 0.30
- Closes all remaining positions at hour end
- Automatically updates to next hour's market
- Telegram notifications (optional)

## Setup

### Quick Setup (Windows)
1. **Double-click `install_dependencies.bat`** to install all dependencies automatically

### Manual Setup

1. **Install dependencies:**
   
   **Option A: Using the setup script**
   ```bash
   python setup.py
   ```
   
   **Option B: Manual installation**
   ```bash
   pip install python-dotenv
   pip install py-clob-client
   ```
   
   If `py-clob-client` is not available on PyPI, install from GitHub:
   ```bash
   pip install git+https://github.com/Polymarket/py-clob-client.git
   ```
   
   **Option C: Install all at once**
   ```bash
   pip install -r requirements.txt
   ```
   
   **Optional packages (for notifications and timezone):**
   ```bash
   pip install python-telegram-bot pytz
   ```

2. **Configure environment variables:**
   - Copy `env.template` to `.env`
   - Fill in your Polymarket CLOB API credentials
   - Optionally add Telegram bot credentials for notifications

3. **Run the bot:**
   ```bash
   python Cornels_Cryptobot.py
   ```

## Environment Variables

### Required
- `PK` - Your private key
- `CLOB_API_KEY` - Your CLOB API key
- `CLOB_SECRET` - Your CLOB API secret
- `CLOB_PASS_PHRASE` - Your CLOB API passphrase

### Optional
- `CLOB_API_URL` - CLOB API URL (default: https://clob.polymarket.com)
- `CHAIN_ID` - Chain ID (default: 137 for Polygon)
- `SIGNATURE_TYPE` - Signature type
- `FUNDER` - Funder address
- `BOT_TOKEN` - Telegram bot token (for notifications)
- `CHAT_ID` - Telegram chat ID (for notifications)

## Usage

1. The bot will prompt for a Polymarket market URL at startup
2. It will propose a default URL based on current Eastern Time
3. The bot will automatically:
   - Check for existing positions
   - Create split positions if none exist
   - Monitor positions every minute
   - Close losing positions 7 minutes before hour end (if price < 0.30)
   - Close all positions at hour end
   - Update to the next hour's market

## Notes

- **The bot requires Python 3.9+** (py-clob-client requirement)
- Telegram notifications are optional but recommended
- Timezone handling works best with `pytz` installed, but has fallback support

## Troubleshooting

If you encounter installation errors, see `INSTALLATION_GUIDE.md` for detailed troubleshooting steps.

Common issues:
- **Python version too low**: Upgrade to Python 3.9+
- **py-clob-client not found**: Install from GitHub: `pip install git+https://github.com/Polymarket/py-clob-client.git`
- **Build errors**: Install Visual Studio Build Tools (Windows) or build-essential (Linux)
