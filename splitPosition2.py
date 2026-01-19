"""
CTF (Conditional Token Framework) Operations for Polymarket

Demonstrates on-chain CTF operations:
- Split: USDC.e → YES + NO tokens
- Merge: YES + NO → USDC.e (for arbitrage)
- Redeem: Winning tokens → USDC.e (after resolution)
- Balance queries and gas estimation

⚠️ CRITICAL: Polymarket CTF uses USDC.e (bridged), NOT native USDC!

| Token         | Address                                    | CTF Compatible |
|---------------|--------------------------------------------|----------------|
| USDC.e        | 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174 | ✅ Yes         |
| Native USDC   | 0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359 | ❌ No          |

Environment variables required:
- ADDRESS:     Your wallet address
- PK:          Private key for signing
- RPC_URL:     HTTPS RPC endpoint (e.g., Polygon)
- CHAIN_ID:    Chain ID (default 137 for Polygon)

Optional:
- AMOUNT_USD:  Dollar amount for operations (default 100)

Run:
    python splitPosition2.py
"""

import os
import re
import json
import time
import urllib.request
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

load_dotenv()

# CTF Contract ABI (Conditional Token Framework)
CTF_ABI = """[
    {
        "constant": false,
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "partition", "type": "uint256[]"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "splitPosition",
        "outputs": [],
        "payable": false,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "partition", "type": "uint256[]"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "mergePositions",
        "outputs": [],
        "payable": false,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "partition", "type": "uint256[]"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "redeemPositions",
        "outputs": [],
        "payable": false,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "collectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSet", "type": "uint256"}
        ],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": false,
        "stateMutability": "view",
        "type": "function"
    }
]"""

# USDC.e ERC20 ABI (for balance checks)
USDC_ABI = """[
    {
        "constant": true,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]"""

# Contract addresses (Polygon Mainnet)
CTF_CONTRACT = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_E_CONTRACT = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC.e (bridged)
USDC_NATIVE_CONTRACT = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Native USDC (NOT usable)


def rpc_call_with_retry(w3, func, *args, max_retries=5, initial_delay=10, **kwargs):
    """Execute RPC call with retry logic for rate limits."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_str = str(e)
            if "rate limit" in error_str.lower() or "too many requests" in error_str.lower():
                retry_time = initial_delay
                if "retry in" in error_str.lower():
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
                raise
    raise RuntimeError(f"Failed after {max_retries} attempts")


def build_web3() -> Web3:
    """Build and return Web3 instance with POA middleware."""
    rpc_url = os.getenv("RPC_URL")
    if not rpc_url:
        raise RuntimeError("RPC_URL is required in environment.")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


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
            url, headers={"User-Agent": "ctf-operations/0.1"}
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
    """Generate default URL based on current Eastern Time (copied from Cornels_Cryptobot)."""
    from datetime import datetime, timedelta
    
    try:
        # Try to use timezone libraries
        try:
            import pytz
            et_tz = pytz.timezone('US/Eastern')
            et_now = datetime.now(et_tz)
        except ImportError:
            try:
                from zoneinfo import ZoneInfo
                et_tz = ZoneInfo('America/New_York')
                et_now = datetime.now(et_tz)
            except:
                # Fallback: Calculate ET from UTC
                utc_now = datetime.utcnow()
                et_offset = timedelta(hours=-5)
                et_now = utc_now + et_offset
        
        month_names = {
            1: 'january', 2: 'february', 3: 'march', 4: 'april',
            5: 'may', 6: 'june', 7: 'july', 8: 'august',
            9: 'september', 10: 'october', 11: 'november', 12: 'december'
        }
        month_text = month_names[et_now.month]
        day = et_now.day
        hour_12 = et_now.hour % 12
        if hour_12 == 0:
            hour_12 = 12
        am_pm = 'am' if et_now.hour < 12 else 'pm'
        
        url_slug = f"bitcoin-up-or-down-{month_text}-{day}-{hour_12}{am_pm}-et"
        return f"https://polymarket.com/event/{url_slug}"
    except Exception as e:
        print(f"Error generating default URL: {e}")
        return "https://polymarket.com/event/bitcoin-up-or-down-january-16-8am-et"


def check_ctf_readiness(w3: Web3, address: str, min_usdc: float = 10.0) -> Dict:
    """Check if wallet is ready for CTF operations."""
    usdc_e = w3.eth.contract(address=USDC_E_CONTRACT, abi=USDC_ABI)
    usdc_native = w3.eth.contract(address=USDC_NATIVE_CONTRACT, abi=USDC_ABI)
    
    try:
        usdc_e_balance_wei = rpc_call_with_retry(w3, usdc_e.functions.balanceOf(address).call)
        usdc_e_balance = usdc_e_balance_wei / 1e6  # USDC has 6 decimals
        
        usdc_native_balance_wei = rpc_call_with_retry(w3, usdc_native.functions.balanceOf(address).call)
        usdc_native_balance = usdc_native_balance_wei / 1e6
        
        matic_balance_wei = rpc_call_with_retry(w3, w3.eth.get_balance, address)
        matic_balance = matic_balance_wei / 1e18
        
        ready = usdc_e_balance >= min_usdc and matic_balance >= 0.01
        
        suggestion = None
        if usdc_e_balance < min_usdc:
            suggestion = f"Need at least ${min_usdc} USDC.e (you have ${usdc_e_balance:.2f})"
        elif usdc_native_balance > 0 and usdc_e_balance < min_usdc:
            suggestion = f"You have ${usdc_native_balance:.2f} native USDC (not usable). Swap to USDC.e first."
        elif matic_balance < 0.01:
            suggestion = f"Need at least 0.01 MATIC for gas (you have {matic_balance:.4f})"
        
        return {
            "usdcEBalance": usdc_e_balance,
            "nativeUsdcBalance": usdc_native_balance,
            "maticBalance": matic_balance,
            "ready": ready,
            "suggestion": suggestion
        }
    except Exception as e:
        return {
            "usdcEBalance": 0,
            "nativeUsdcBalance": 0,
            "maticBalance": 0,
            "ready": False,
            "suggestion": f"Error checking balances: {e}"
        }


def get_position_balance(w3: Web3, address: str, condition_id: str) -> Dict:
    """Get YES and NO token balances for a condition."""
    ctf = w3.eth.contract(address=CTF_CONTRACT, abi=CTF_ABI)
    
    # Partition: [1, 2] for binary markets (YES=1, NO=2)
    # Collection ID: 0x00...00 for root collection
    parent_collection = "0x" + "00" * 32
    
    try:
        yes_balance = rpc_call_with_retry(w3, ctf.functions.balanceOf(address, parent_collection, condition_id, 1).call)
        no_balance = rpc_call_with_retry(w3, ctf.functions.balanceOf(address, parent_collection, condition_id, 2).call)
        
        # Calculate position IDs (token IDs)
        # Position ID = keccak256(abi.encodePacked(parentCollectionId, conditionId, indexSet))
        # For simplicity, we'll use placeholder values - actual position IDs are complex to calculate
        yes_position_id = "0x" + "0" * 64  # Placeholder
        no_position_id = "0x" + "0" * 64  # Placeholder
        
        return {
            "yesBalance": yes_balance,
            "noBalance": no_balance,
            "yesPositionId": w3.to_hex(yes_position_id),
            "noPositionId": w3.to_hex(no_position_id)
        }
    except Exception as e:
        print(f"Error getting position balance: {e}")
        return {
            "yesBalance": 0,
            "noBalance": 0,
            "yesPositionId": "0x0",
            "noPositionId": "0x0"
        }


def estimate_gas(w3: Web3, tx_params: dict) -> int:
    """Estimate gas for a transaction."""
    try:
        return rpc_call_with_retry(w3, w3.eth.estimate_gas, tx_params)
    except Exception as e:
        print(f"Gas estimation failed: {e}")
        return 500_000  # Default fallback


def ctf_split(w3: Web3, address: str, pk: str, condition_id: str, amount_usd: float, chain_id: int = 137) -> Dict:
    """Split USDC.e into YES + NO tokens."""
    print(f"\n{'='*80}")
    print("CTF SPLIT Operation")
    print(f"{'='*80}")
    print(f"Splitting ${amount_usd:.2f} USDC.e into YES + NO tokens")
    print(f"Condition ID: {condition_id}")
    
    # Convert USD to wei (USDC has 6 decimals)
    amount = int(amount_usd * 1_000_000)
    parent_collection = "0x" + "00" * 32
    partition = [1, 2]  # YES=1, NO=2
    
    ctf = w3.eth.contract(address=CTF_CONTRACT, abi=CTF_ABI)
    
    # Get nonce and gas fees
    print("Fetching nonce and gas fees...")
    nonce = rpc_call_with_retry(w3, w3.eth.get_transaction_count, address)
    
    try:
        fee_history = rpc_call_with_retry(w3, w3.eth.fee_history, 1, "latest")
        base_fee = fee_history["baseFeePerGas"][0]
        priority_fee = max(int(base_fee * 1.5), 30_000_000_000)
        max_fee = base_fee + priority_fee
    except Exception as e:
        print(f"⚠️  Could not fetch fee history: {e}")
        gas_price = rpc_call_with_retry(w3, lambda: w3.eth.gas_price)
        max_fee = gas_price
        priority_fee = int(gas_price * 0.1)
    
    # Build transaction
    tx_params = {
        "chainId": chain_id,
        "gas": 500_000,
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": priority_fee,
        "from": address,
        "nonce": nonce,
    }
    
    # Estimate gas
    try:
        estimated_gas = estimate_gas(w3, {
            **tx_params,
            "to": CTF_CONTRACT,
            "data": ctf.encodeABI(fn_name="splitPosition", args=[
                USDC_E_CONTRACT,
                parent_collection,
                condition_id,
                partition,
                amount
            ])
        })
        tx_params["gas"] = int(estimated_gas * 1.2)  # Add 20% buffer
        print(f"Estimated gas: {estimated_gas:,}, using {tx_params['gas']:,}")
    except Exception as e:
        print(f"⚠️  Gas estimation failed, using default: {e}")
    
    # Simulate transaction
    print("Simulating transaction...")
    try:
        ctf.functions.splitPosition(
            USDC_E_CONTRACT, parent_collection, condition_id, partition, amount
        ).call({"from": address})
        print("✓ Simulation successful")
    except Exception as sim_error:
        print(f"⚠️  Simulation failed: {sim_error}")
        print("Transaction may fail. Continuing anyway...")
    
    # Build and sign transaction
    tx = ctf.functions.splitPosition(
        USDC_E_CONTRACT, parent_collection, condition_id, partition, amount
    ).build_transaction(tx_params)
    
    signed = w3.eth.account.sign_transaction(tx, private_key=pk)
    tx_hash = w3.to_hex(w3.keccak(signed.raw_transaction))
    
    print(f"\nTransaction hash: {tx_hash}")
    print("Sending transaction...")
    sent = rpc_call_with_retry(w3, w3.eth.send_raw_transaction, signed.raw_transaction)
    
    print("Waiting for receipt...")
    receipt = rpc_call_with_retry(w3, w3.eth.wait_for_transaction_receipt, sent, timeout=600)
    
    # Check status
    status = receipt.get("status") if isinstance(receipt, dict) else getattr(receipt, "status", None)
    gas_used = receipt.get("gasUsed") if isinstance(receipt, dict) else getattr(receipt, "gasUsed", None)
    
    if status == 0:
        raise RuntimeError(f"Transaction failed! View: https://polygonscan.com/tx/{tx_hash}")
    
    print(f"\n✅ SPLIT successful!")
    print(f"   Transaction: https://polygonscan.com/tx/{tx_hash}")
    print(f"   Gas used: {gas_used:,}")
    print(f"   Created {amount:,} YES + {amount:,} NO tokens")
    
    return {
        "txHash": tx_hash,
        "yesTokens": amount,
        "noTokens": amount,
        "gasUsed": gas_used
    }


def ctf_merge(w3: Web3, address: str, pk: str, condition_id: str, amount: int, chain_id: int = 137) -> Dict:
    """Merge YES + NO tokens back into USDC.e."""
    print(f"\n{'='*80}")
    print("CTF MERGE Operation")
    print(f"{'='*80}")
    print(f"Merging {amount:,} YES + {amount:,} NO tokens → USDC.e")
    print(f"Condition ID: {condition_id}")
    
    parent_collection = "0x" + "00" * 32
    partition = [1, 2]
    
    ctf = w3.eth.contract(address=CTF_CONTRACT, abi=CTF_ABI)
    
    nonce = rpc_call_with_retry(w3, w3.eth.get_transaction_count, address)
    
    try:
        fee_history = rpc_call_with_retry(w3, w3.eth.fee_history, 1, "latest")
        base_fee = fee_history["baseFeePerGas"][0]
        priority_fee = max(int(base_fee * 1.5), 30_000_000_000)
        max_fee = base_fee + priority_fee
    except Exception as e:
        gas_price = rpc_call_with_retry(w3, lambda: w3.eth.gas_price)
        max_fee = gas_price
        priority_fee = int(gas_price * 0.1)
    
    tx_params = {
        "chainId": chain_id,
        "gas": 500_000,
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": priority_fee,
        "from": address,
        "nonce": nonce,
    }
    
    try:
        estimated_gas = estimate_gas(w3, {
            **tx_params,
            "to": CTF_CONTRACT,
            "data": ctf.encodeABI(fn_name="mergePositions", args=[
                USDC_E_CONTRACT,
                parent_collection,
                condition_id,
                partition,
                amount
            ])
        })
        tx_params["gas"] = int(estimated_gas * 1.2)
    except:
        pass
    
    # Simulate
    try:
        ctf.functions.mergePositions(
            USDC_E_CONTRACT, parent_collection, condition_id, partition, amount
        ).call({"from": address})
        print("✓ Simulation successful")
    except Exception as e:
        print(f"⚠️  Simulation failed: {e}")
    
    tx = ctf.functions.mergePositions(
        USDC_E_CONTRACT, parent_collection, condition_id, partition, amount
    ).build_transaction(tx_params)
    
    signed = w3.eth.account.sign_transaction(tx, private_key=pk)
    tx_hash = w3.to_hex(w3.keccak(signed.raw_transaction))
    
    print(f"Transaction hash: {tx_hash}")
    sent = rpc_call_with_retry(w3, w3.eth.send_raw_transaction, signed.raw_transaction)
    receipt = rpc_call_with_retry(w3, w3.eth.wait_for_transaction_receipt, sent, timeout=600)
    
    status = receipt.get("status") if isinstance(receipt, dict) else getattr(receipt, "status", None)
    if status == 0:
        raise RuntimeError(f"Transaction failed! View: https://polygonscan.com/tx/{tx_hash}")
    
    usdc_received = amount  # 1:1 ratio
    print(f"\n✅ MERGE successful!")
    print(f"   Transaction: https://polygonscan.com/tx/{tx_hash}")
    print(f"   Received {usdc_received:,} USDC.e")
    
    return {
        "txHash": tx_hash,
        "usdcReceived": usdc_received,
        "gasUsed": receipt.get("gasUsed") if isinstance(receipt, dict) else getattr(receipt, "gasUsed", 0)
    }


def main():
    print("=" * 80)
    print("Polymarket CTF Operations")
    print("=" * 80)
    print()
    
    # Check environment
    address = os.getenv("ADDRESS")
    pk = os.getenv("PK")
    rpc_url = os.getenv("RPC_URL")
    chain_id = int(os.getenv("CHAIN_ID", "137"))
    amount_usd = float(os.getenv("AMOUNT_USD", "100"))
    
    if not address or not pk or not rpc_url:
        print("❌ ERROR: Missing required environment variables")
        print("Required: ADDRESS, PK, RPC_URL")
        print("Optional: CHAIN_ID (default 137), AMOUNT_USD (default 100)")
        return
    
    w3 = build_web3()
    
    print(f"Wallet: {address}")
    print(f"CTF Contract: {CTF_CONTRACT}")
    print(f"USDC.e Contract: {USDC_E_CONTRACT}")
    print()
    
    # Check CTF readiness
    print("1. Checking CTF readiness...")
    readiness = check_ctf_readiness(w3, address, min_usdc=amount_usd)
    print(f"   USDC.e Balance: ${readiness['usdcEBalance']:.2f}")
    print(f"   Native USDC:    ${readiness['nativeUsdcBalance']:.2f} (NOT usable for CTF)")
    print(f"   MATIC Balance:  {readiness['maticBalance']:.4f}")
    print(f"   CTF Ready:      {'✅ Yes' if readiness['ready'] else '❌ No'}")
    if readiness['suggestion']:
        print(f"\n   ⚠️  {readiness['suggestion']}")
        if not readiness['ready']:
            print("\n   Please fix the issues above before continuing.")
            return
    
    # Get market URL
    print("\n2. Getting market information...")
    default_url = get_eastern_time_slug()
    print(f"   Proposed URL: {default_url}")
    url = input("   Enter Polymarket market URL (or press Enter for default): ").strip()
    if not url:
        url = default_url
    
    condition_id = get_condition_id_from_url(url)
    if not condition_id:
        print("❌ ERROR: Could not resolve condition_id from URL")
        return
    
    print(f"   Condition ID: {condition_id}")
    
    # Check balances
    print("\n3. Checking token balances...")
    balances = get_position_balance(w3, address, condition_id)
    print(f"   YES Balance: {balances['yesBalance']:,}")
    print(f"   NO Balance:  {balances['noBalance']:,}")
    
    # Menu
    print("\n4. Select operation:")
    print("   1. Split (USDC.e → YES + NO)")
    print("   2. Merge (YES + NO → USDC.e)")
    print("   3. Check balances only")
    
    choice = input("   Choice (1-3): ").strip()
    
    try:
        if choice == "1":
            result = ctf_split(w3, address, pk, condition_id, amount_usd, chain_id)
            print(f"\n✅ Split completed: {result['yesTokens']:,} YES + {result['noTokens']:,} NO")
        elif choice == "2":
            # Use minimum of YES and NO balances
            merge_amount = min(balances['yesBalance'], balances['noBalance'])
            if merge_amount == 0:
                print("❌ ERROR: No tokens to merge (need both YES and NO)")
                return
            print(f"\n   Merging {merge_amount:,} pairs (min of YES/NO balances)")
            result = ctf_merge(w3, address, pk, condition_id, merge_amount, chain_id)
            print(f"\n✅ Merge completed: Received {result['usdcReceived']:,} USDC.e")
        elif choice == "3":
            print("\n✅ Balance check complete")
        else:
            print("Invalid choice")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Operation complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
