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
"""

import os
import re
import json
import urllib.request
from typing import Optional

from dataclasses import dataclass
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import geth_poa_middleware

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
            neg_risk_adapter="0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
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
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3


def split_position_native(condition_id: str):
    """Perform native splitPosition for the given condition_id."""
    address = os.getenv("ADDRESS")
    pk = os.getenv("PK")
    chain_id = int(os.getenv("CHAIN_ID", "137"))
    is_neg_risk = os.getenv("IS_NEG_RISK_MARKET", "false").lower() == "true"
    amount_usd = float(os.getenv("AMOUNT_USD", "5"))

    if not address or not pk:
        raise RuntimeError("ADDRESS and PK are required in environment.")

    contracts = get_contract_config(chain_id)
    if not contracts:
        raise RuntimeError(f"No contract config for chain_id {chain_id}")

    # USDC 6 decimals
    amount = int(amount_usd * 1_000_000)
    parent_collection = "0x" + "00" * 32
    partition = [1, 2]

    w3 = build_web3()
    nonce = w3.eth.get_transaction_count(address)
    gas_price = w3.eth.gas_price

    if is_neg_risk:
        contract = w3.eth.contract(
            address=contracts.neg_risk_adapter, abi=NegRiskAdapterABI
        )
        tx = contract.functions.splitPosition(condition_id, amount).build_transaction(
            {
                "chainId": chain_id,
                "gas": 1_000_000,
                "gasPrice": gas_price,
                "from": address,
                "nonce": nonce,
            }
        )
    else:
        contract = w3.eth.contract(
            address=contracts.conditional_tokens, abi=ConditionalTokenABI
        )
        tx = contract.functions.splitPosition(
            contracts.collateral, parent_collection, condition_id, partition, amount
        ).build_transaction(
            {
                "chainId": chain_id,
                "gas": 1_000_000,
                "gasPrice": gas_price,
                "from": address,
                "nonce": nonce,
            }
        )

    signed = w3.eth.account.sign_transaction(tx, private_key=pk)
    tx_hash = w3.to_hex(w3.keccak(signed.rawTransaction))
    sent = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(sent, timeout=600)
    print(f"splitPosition sent: {tx_hash}")
    print(f"status: {receipt.status}, gasUsed: {receipt.gasUsed}")


def main():
    print("=" * 80)
    print("Native Split Position Test")
    print("=" * 80)

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
