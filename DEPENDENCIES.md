# Dependencies and Files Overview

This document lists all files and dependencies needed for Cornels Cryptobot.

## Files in This Folder

### Core Files
- **Cornels_Cryptobot.py** - Main bot script (required)
- **requirements.txt** - Python package dependencies list
- **env.template** - Template for environment variables (copy to .env)
- **.gitignore** - Git ignore file (excludes .env and cache files)

### Installation Scripts
- **setup.py** - Python script to install dependencies (cross-platform)
- **install_dependencies.bat** - Windows batch script for easy installation
- **install_dependencies.sh** - Linux/Mac shell script for installation

### Documentation
- **README.md** - Main documentation and usage instructions
- **DEPENDENCIES.md** - This file

## Python Dependencies

### Required
1. **py-clob-client** - Polymarket CLOB API client
   - Install: `pip install py-clob-client`
   - Or from GitHub: `pip install git+https://github.com/Polymarket/py-clob-client.git`

2. **python-dotenv** - Load environment variables from .env file
   - Install: `pip install python-dotenv`

### Optional
3. **python-telegram-bot** - For Telegram notifications
   - Install: `pip install python-telegram-bot`

4. **pytz** - For timezone handling (recommended)
   - Install: `pip install pytz`
   - Note: Python 3.9+ includes zoneinfo, but pytz is more reliable

## Environment Variables (.env file)

Create a `.env` file (copy from `env.template`) with:

### Required
- `PK` - Your private key
- `CLOB_API_KEY` - Your CLOB API key
- `CLOB_SECRET` - Your CLOB API secret
- `CLOB_PASS_PHRASE` - Your CLOB API passphrase

### Optional
- `CLOB_API_URL` - CLOB API URL (default: https://clob.polymarket.com)
- `CHAIN_ID` - Chain ID (default: 137)
- `SIGNATURE_TYPE` - Signature type
- `FUNDER` - Funder address
- `BOT_TOKEN` - Telegram bot token
- `CHAT_ID` - Telegram chat ID

## Quick Start

1. **Install dependencies:**
   - Windows: Double-click `install_dependencies.bat`
   - Linux/Mac: Run `bash install_dependencies.sh`
   - Or: Run `python setup.py`

2. **Create .env file:**
   - Copy `env.template` to `.env`
   - Fill in your credentials

3. **Run the bot:**
   ```bash
   python Cornels_Cryptobot.py
   ```

## For Git Export

All necessary files are included:
- ✅ Main script (Cornels_Cryptobot.py)
- ✅ Dependencies list (requirements.txt)
- ✅ Environment template (env.template)
- ✅ Installation scripts (setup.py, *.bat, *.sh)
- ✅ Documentation (README.md, DEPENDENCIES.md)
- ✅ Git ignore (.gitignore)

**Note:** The `.env` file is excluded from git (contains sensitive credentials).

## Troubleshooting

If you get import errors:
1. Make sure Python is installed (3.7+)
2. Run the installation script or `pip install -r requirements.txt`
3. If `py-clob-client` fails, try: `pip install git+https://github.com/Polymarket/py-clob-client.git`
4. Check that you're using the correct Python interpreter
