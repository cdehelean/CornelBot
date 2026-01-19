"""
Native split-position test script for Polymarket conditional tokens.

What it does:
- Reuses the URL handling logic from Cornels_Cryptobot to fetch the market.
- Extracts the condition_id from the Polymarket Gamma API.
- Performs a native splitPosition on-chain for $5 USDC (6 decimals) per outcome.

Environment variables required:
- ADDRESS:     Your wallet address
- PK:          Private key for signing
- RPC_URL:     HTTPS RPC endpoint (e.g., Polygon)
- CHAIN_ID:    Chain ID (default 137 for Polygon)
- IS_NEG_RISK_MARKET: "true"/"false" to switch adapter paths (default false)

Optional:
- AMOUNT_USD:  Dollar amount to split (default 5)

Run:
    python native_split_test.py

Note: If you get ModuleNotFoundError in VS Code Debug Console:
- Select the correct Python interpreter: Ctrl+Shift+P > "Python: Select Interpreter"
- Or run in VS Code terminal instead: Ctrl+` then run the script
- See VS_CODE_SETUP.md for details
"""

import os
import re
import json
import time
import urllib.request
from typing import Optional

from dataclasses import dataclass
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

load_dotenv()


NegRiskAdapterABI = """[{"inputs":[{"internalType":"bytes32","name":"_conditionId","type":"bytes32"},{"internalType":"uint256","name":"_amount","type":"uint256"}],"name":"splitPosition","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"bytes32","name":"_conditionId","type":"bytes32"},{"internalType":"uint256","name":"_amount","type":"uint256"}],"name":"mergePositions","outputs":[],"stateMutability":"nonpayable","type":"function"}]"""
ConditionalTokenABI = """[{"constant":"false","inputs":[{"name":"collateralToken","type":"address"},{"name":"parentCollectionId","type":"bytes32"},{"name":"CONDITION_ID","type":"bytes32"},{"name":"partition","type":"uint256[]"},{"name":"amount","type":"uint256"}],"name":"splitPosition","outputs":[],"payable":"false","stateMutability":"nonpayable","type":"function"},{"constant":"false","inputs":[{"name":"collateralToken","type":"address"},{"name":"parentCollectionId","type":"bytes32"},{"name":"CONDITION_ID","type":"bytes32"},{"name":"partition","type":"uint256[]"},{"name":"amount","type":"uint256"}],"name":"mergePositions","outputs":[],"payable":"false","stateMutability":"nonpayable","type":"function"}]"""


@dataclass
class ContractConfig:
    neg_risk_adapter: str
    conditional_tokens: str
    collateral: str


def get_contract_config(chain_id: int) -> Optional[ContractConfig]:
    """Return contract addresses for supported chains."""
    config = {
        137: ContractConfig(
            # Updated neg_risk_adapter to the working address from successful transaction
            neg_risk_adapter="0x1e625399251CbC18Bd9F82cfa021EE7AFdD7d66a",
            collateral="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # USDC.e on Polygon (6 decimals)
            conditional_tokens="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        ),
        80002: ContractConfig(
            neg_risk_adapter="",
            collateral="0x9c4e1703476e875070ee25b56a58b008cfb8fa78",
            conditional_tokens="0x69308FB512518e39F9b16112fA8d994F4e2Bf8bB",
        ),
    }
    return config.get(chain_id)


def extract_market_id_from_url(url: str) -> Optional[str]:
    """Extract market slug or condition_id from Polymarket URL."""
    if not url:
        return None
    if re.match(r"^0x[a-fA-F0-9]+$", url.strip()):
        return url.strip()
    patterns = [
        r"polymarket\.com/(?:event|market)/([a-zA-Z0-9_-]+)",
        r"polymarket\.com/(?:event|market)/(0x[a-fA-F0-9]+)",
        r"/([a-zA-Z0-9_-]+)(?:\?|$)",
        r"/(0x[a-fA-F0-9]+)(?:\?|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return url.strip() if url.strip() else None


def get_market_from_gamma_api(slug: str) -> Optional[dict]:
    """Fetch market data from Gamma API using slug."""
    if not slug:
        return None
    try:
        url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "native-split-test/0.1"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data
    except Exception as exc:
        print(f"Error fetching market from Gamma API: {exc}")
        return None


def get_condition_id_from_url(url: str) -> Optional[str]:
    """Resolve condition_id from a Polymarket URL or condition_id string."""
    market_identifier = extract_market_id_from_url(url)
    if not market_identifier:
        return None

    # If it's already a hex condition_id
    if market_identifier.startswith("0x") and len(market_identifier) > 10:
        return market_identifier

    gamma_data = get_market_from_gamma_api(market_identifier)
    if gamma_data:
        condition_id = gamma_data.get("conditionId")
        if condition_id:
            return condition_id
    return None


def get_eastern_time_slug() -> str:
    """Generate default Polymarket BTC hourly slug based on current ET (approx)."""
    from datetime import datetime, timedelta

    utc_now = datetime.utcnow()
    et_now = utc_now + timedelta(hours=-5)  # approximate ET without DST
    month_names = {
        1: "january",
        2: "february",
        3: "march",
        4: "april",
        5: "may",
        6: "june",
        7: "july",
        8: "august",
        9: "september",
        10: "october",
        11: "november",
        12: "december",
    }
    month_text = month_names[et_now.month]
    day = et_now.day
    hour_12 = et_now.hour % 12
    if hour_12 == 0:
        hour_12 = 12
    am_pm = "am" if et_now.hour < 12 else "pm"
    slug = f"bitcoin-up-or-down-{month_text}-{day}-{hour_12}{am_pm}-et"
    return f"https://polymarket.com/event/{slug}"


def build_web3() -> Web3:
    rpc_url = os.getenv("RPC_URL")
    if not rpc_url:
        raise RuntimeError("RPC_URL is required in environment.")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def rpc_call_with_retry(w3, func, *args, max_retries=5, initial_delay=10, **kwargs):
    """Execute RPC call with retry logic for rate limits."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_str = str(e)
            # Check if it's a rate limit error
            if "rate limit" in error_str.lower() or "too many requests" in error_str.lower():
                # Try to extract retry time from error message
                retry_time = initial_delay
                if "retry in" in error_str.lower():
                    import re
                    match = re.search(r"retry in (\d+)s?", error_str.lower())
                    if match:
                        retry_time = int(match.group(1))
                
                if attempt < max_retries - 1:
                    print(f"⚠️  Rate limit hit. Waiting {retry_time} seconds before retry {attempt + 1}/{max_retries}...")
                    time.sleep(retry_time)
                    continue
                else:
                    raise RuntimeError(f"Rate limit error after {max_retries} retries: {error_str}")
            else:
                # Not a rate limit error, re-raise immediately
                raise
    raise RuntimeError(f"Failed after {max_retries} attempts")


def split_position_native(condition_id: str):
    """Perform native splitPosition for the given condition_id."""
    address = os.getenv("ADDRESS")
    pk = os.getenv("PK")
    chain_id = int(os.getenv("CHAIN_ID", "137"))
    # Default to using neg_risk_adapter since that's what works on Polygon
    is_neg_risk = os.getenv("IS_NEG_RISK_MARKET", "true").lower() == "true"
    amount_usd = float(os.getenv("AMOUNT_USD", "5"))

    if not address or not pk:
        error_msg = "ADDRESS and PK are required in environment.\n\n"
        error_msg += "Please add them to your .env file:\n"
        error_msg += "  1. Copy 'env.template' to '.env' if you haven't already\n"
        error_msg += "  2. Add these lines to your .env file:\n"
        error_msg += "     ADDRESS=your_wallet_address_here\n"
        error_msg += "     PK=your_private_key_here\n"
        error_msg += "     RPC_URL=https://polygon-rpc.com\n"
        if not os.path.exists(".env"):
            error_msg += "\n  Note: .env file not found. Create it from env.template\n"
        raise RuntimeError(error_msg)

    contracts = get_contract_config(chain_id)
    if not contracts:
        raise RuntimeError(f"No contract config for chain_id {chain_id}")

    # USDC 6 decimals - convert USD to wei (6 decimals)
    # $5 = 5 * 10^6 = 5,000,000 (6 decimals for USDC)
    amount = int(amount_usd * 1_000_000)
    parent_collection = "0x" + "00" * 32
    partition = [1, 2]
    
    print(f"Split parameters:")
    print(f"  Condition ID: {condition_id}")
    print(f"  Amount: {amount:,} (${amount_usd:.2f} USD)")
    print(f"  Partition: {partition}")
    print(f"  Parent collection: {parent_collection}")

    w3 = build_web3()
    
    # Use retry logic for RPC calls
    print("Fetching nonce and gas fees...")
    nonce = rpc_call_with_retry(w3, w3.eth.get_transaction_count, address)
    
    # Polygon uses EIP-1559, so we need maxFeePerGas and maxPriorityFeePerGas
    try:
        fee_history = rpc_call_with_retry(w3, w3.eth.fee_history, 1, "latest")
        base_fee = fee_history["baseFeePerGas"][0]
        # Use a multiplier for priority fee (1.5x base fee as priority, or minimum 30 gwei)
        priority_fee = max(int(base_fee * 1.5), 30_000_000_000)  # 30 gwei minimum
        max_fee = base_fee + priority_fee
    except Exception as e:
        print(f"⚠️  Could not fetch fee history, using fallback gas pricing: {e}")
        # Fallback to legacy gas price if EIP-1559 fails
        gas_price = rpc_call_with_retry(w3, lambda: w3.eth.gas_price)
        max_fee = gas_price
        priority_fee = int(gas_price * 0.1)  # 10% of gas price as priority

    # Build transaction with EIP-1559 gas pricing (Polygon standard)
    tx_params = {
        "chainId": chain_id,
        "gas": 1_000_000,
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": priority_fee,
        "from": address,
        "nonce": nonce,
    }
    
    if is_neg_risk:
        contract = w3.eth.contract(
            address=contracts.neg_risk_adapter, abi=NegRiskAdapterABI
        )
        tx = contract.functions.splitPosition(condition_id, amount).build_transaction(tx_params)
    else:
        contract = w3.eth.contract(
            address=contracts.conditional_tokens, abi=ConditionalTokenABI
        )
        tx = contract.functions.splitPosition(
            contracts.collateral, parent_collection, condition_id, partition, amount
        ).build_transaction(tx_params)
    
    print(f"Transaction parameters:")
    print(f"  Gas limit: {tx_params['gas']}")
    print(f"  Max fee per gas: {max_fee / 1e9:.2f} gwei")
    print(f"  Max priority fee: {priority_fee / 1e9:.2f} gwei")

    # Try to simulate the transaction first to catch errors early
    print("Simulating transaction (dry run)...")
    try:
        if is_neg_risk:
            contract.functions.splitPosition(condition_id, amount).call({"from": address})
        else:
            contract.functions.splitPosition(
                contracts.collateral, parent_collection, condition_id, partition, amount
            ).call({"from": address})
        print("✓ Simulation successful - transaction should work")
    except Exception as sim_error:
        error_msg = str(sim_error)
        print(f"⚠️  Simulation failed: {error_msg}")
        print("This transaction will likely fail. Continuing anyway...")
        print()
    
    signed = w3.eth.account.sign_transaction(tx, private_key=pk)
    tx_hash = w3.to_hex(w3.keccak(signed.raw_transaction))
    
    print(f"Transaction hash: {tx_hash}")
    print("Sending transaction...")
    sent = rpc_call_with_retry(w3, w3.eth.send_raw_transaction, signed.raw_transaction)
    
    print("Waiting for transaction receipt...")
    receipt = rpc_call_with_retry(w3, w3.eth.wait_for_transaction_receipt, sent, timeout=600)
    
    # Comprehensive error checking
    print()
    print("=" * 80)
    print("Transaction Receipt Analysis")
    print("=" * 80)
    
    # Check transaction status
    status = receipt.get("status") if isinstance(receipt, dict) else getattr(receipt, "status", None)
    gas_used = receipt.get("gasUsed") if isinstance(receipt, dict) else getattr(receipt, "gasUsed", None)
    gas_limit = tx_params.get("gas", 0)
    
    print(f"Transaction Hash: {tx_hash}")
    print(f"Block Number: {receipt.get('blockNumber') if isinstance(receipt, dict) else getattr(receipt, 'blockNumber', 'N/A')}")
    print(f"Status: {status} ({'✅ SUCCESS' if status == 1 else '❌ FAILED'})")
    print(f"Gas Used: {gas_used:,} / {gas_limit:,}")
    
    if status == 0:
        # Transaction failed - try to get more details
        print()
        print("❌ TRANSACTION FAILED!")
        print()
        
        # Check if out of gas
        if gas_used and gas_limit and gas_used >= gas_limit:
            print("⚠️  Possible cause: OUT OF GAS")
            print(f"   Gas used ({gas_used:,}) equals or exceeds gas limit ({gas_limit:,})")
            print("   Consider increasing gas limit")
        
        # Try to get revert reason
        print("Attempting to get revert reason...")
        try:
            # Try to call the transaction again to get the error
            if is_neg_risk:
                contract.functions.splitPosition(condition_id, amount).call({"from": address})
            else:
                contract.functions.splitPosition(
                    contracts.collateral, parent_collection, condition_id, partition, amount
                ).call({"from": address})
        except Exception as call_error:
            error_str = str(call_error)
            print(f"   Error message: {error_str}")
            
            # Try to extract more specific error info
            if "execution reverted" in error_str.lower():
                print("   Type: Execution reverted (contract logic rejected the call)")
            elif "insufficient funds" in error_str.lower() or "balance" in error_str.lower():
                print("   Type: Insufficient funds")
            elif "nonce" in error_str.lower():
                print("   Type: Nonce issue")
        
        # Check transaction on block explorer
        explorer_url = f"https://polygonscan.com/tx/{tx_hash}"
        print()
        print(f"View transaction details: {explorer_url}")
        print()
        print("Common failure reasons:")
        print("  - Insufficient USDC balance for the split amount")
        print("  - Contract logic rejected the transaction")
        print("  - Wrong contract address or ABI")
        print("  - Invalid condition_id or parameters")
        print("  - Out of gas (gas limit too low)")
        
        raise RuntimeError(f"Transaction failed. Status: {status}. See details above.")
    
    # Success
    print()
    print("✅ TRANSACTION SUCCESSFUL!")
    print(f"   View on Polygonscan: https://polygonscan.com/tx/{tx_hash}")
    print(f"   Gas used: {gas_used:,} ({gas_used/gas_limit*100:.1f}% of limit)")
    print("=" * 80)


def main():
    print("=" * 80)
    print("Native Split Position Test")
    print("=" * 80)
    print()

    # Check if .env file exists
    if not os.path.exists(".env"):
        print("⚠️  WARNING: .env file not found!")
        print()
        print("Please create a .env file:")
        print("  1. Copy 'env.template' to '.env'")
        print("  2. Fill in your credentials (ADDRESS, PK, RPC_URL, etc.)")
        print()
        print("Required variables for native split test:")
        print("  - ADDRESS: Your wallet address")
        print("  - PK: Your private key")
        print("  - RPC_URL: Polygon RPC endpoint (e.g., https://polygon-rpc.com)")
        print()
        response = input("Continue anyway? (y/n): ").strip().lower()
        if response != 'y':
            print("Exiting. Please set up your .env file first.")
            return
        print()

    # Check required environment variables
    address = os.getenv("ADDRESS")
    pk = os.getenv("PK")
    rpc_url = os.getenv("RPC_URL")

    missing = []
    if not address:
        missing.append("ADDRESS")
    if not pk:
        missing.append("PK")
    if not rpc_url:
        missing.append("RPC_URL")

    if missing:
        print("❌ ERROR: Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print()
        print("Please add them to your .env file:")
        print("  ADDRESS=your_wallet_address_here")
        print("  PK=your_private_key_here")
        print("  RPC_URL=https://polygon-rpc.com")
        print()
        print("Then restart the script.")
        return

    print("✓ Environment variables loaded")
    print()

    default_url = get_eastern_time_slug()
    print(f"Proposed URL: {default_url}")
    url = input("Enter Polymarket market URL (or press Enter for default): ").strip()
    if not url:
        url = default_url
        print(f"Using default URL: {url}")

    condition_id = get_condition_id_from_url(url)
    if not condition_id:
        print("Error: could not resolve condition_id from the provided URL.")
        return

    print(f"Condition ID: {condition_id}")
    try:
        split_position_native(condition_id)
    except Exception as exc:
        print(f"Error during splitPosition: {exc}")


if __name__ == "__main__":
    main()
