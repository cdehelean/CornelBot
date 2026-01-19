# Setting Up Your .env File

## Quick Setup

1. **Copy the template:**
   ```bash
   copy env.template .env
   ```
   (On Linux/Mac: `cp env.template .env`)

2. **Edit `.env` file** and fill in your credentials:

### Required for Native Split Test

```env
# Your wallet address (0x...)
ADDRESS=0xYourWalletAddressHere

# Your private key (0x...)
PK=0xYourPrivateKeyHere

# Polygon RPC endpoint
RPC_URL=https://polygon-rpc.com
```

### Optional (with defaults)

```env
# Chain ID (default: 137 for Polygon)
CHAIN_ID=137

# Use neg risk adapter? (default: false)
IS_NEG_RISK_MARKET=false

# Amount in USD to split (default: 5)
AMOUNT_USD=5
```

## Example .env File

```env
# Wallet credentials
ADDRESS=0x1234567890123456789012345678901234567890
PK=0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
RPC_URL=https://polygon-rpc.com

# Chain configuration
CHAIN_ID=137
IS_NEG_RISK_MARKET=false
AMOUNT_USD=5

# CLOB API (for main bot)
CLOB_API_KEY=your_key_here
CLOB_SECRET=your_secret_here
CLOB_PASS_PHRASE=your_passphrase_here
```

## Security Note

⚠️ **Never commit your `.env` file to git!**

The `.gitignore` file already excludes `.env` from version control. Keep your private keys and secrets safe.

## Verify Setup

After creating your `.env` file, run:
```bash
python native_split_test.py
```

The script will check for required variables and show helpful error messages if anything is missing.
