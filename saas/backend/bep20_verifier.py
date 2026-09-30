import re
import json
import urllib.request
from typing import Dict, Any, Optional

TARGET_WALLET = "0x66A06fA03BE98383fe4F73a5f1783332CAC0F5A0"

BSC_RPCS = [
    "https://bsc-dataseed.binance.org/",
    "https://bsc-dataseed1.defibit.io/",
    "https://bsc-dataseed1.ninicoin.io/"
]

# Standard BEP20 Token Contracts on BNB Smart Chain
KNOWN_BEP20_TOKENS = {
    "0x55d398326f99059ff775485246999027b3197955": {"symbol": "USDT", "decimals": 18},
    "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d": {"symbol": "USDC", "decimals": 18},
    "0xe9e7cea3dedca5984780bafc599bd69add087d56": {"symbol": "BUSD", "decimals": 18},
    "0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3": {"symbol": "DAI", "decimals": 18}
}

ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Pricing & Tolerance Settings (accounting for exchange withdrawal network fees)
TIER_7D_TARGET = 19.00
TIER_7D_MIN_TOLERANCE = 17.50   # Accepts if exchange deducted up to $1.50 fee

TIER_30D_TARGET = 69.00
TIER_30D_MIN_TOLERANCE = 65.00  # Accepts if exchange deducted up to $4.00 fee


class BEP20Verifier:
    @staticmethod
    def _rpc_call(method: str, params: list) -> Optional[Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

        for rpc in BSC_RPCS:
            try:
                req = urllib.request.Request(rpc, data=data, headers=headers)
                with urllib.request.urlopen(req, timeout=5) as res:
                    resp = json.loads(res.read().decode("utf-8"))
                    if "result" in resp:
                        return resp["result"]
            except Exception:
                continue
        return None

    @staticmethod
    def _get_bnb_usd_price() -> float:
        """Fetches current BNB/USDT spot price from Binance public endpoint."""
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BNBUSDT"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as res:
                data = json.loads(res.read().decode("utf-8"))
                return float(data.get("price", 580.0))
        except Exception:
            return 580.0

    @classmethod
    def verify_transaction(cls, tx_hash: str, expected_tier: Optional[str] = None) -> Dict[str, Any]:
        """
        Queries BNB Smart Chain to verify that tx_hash exists, succeeded,
        and delivered >= required USDT/USDC/BNB to the target wallet.
        """
        clean_hash = tx_hash.strip().lower()
        if not re.match(r"^0x[0-9a-fA-F]{64}$", clean_hash):
            return {
                "success": False,
                "error": "Invalid transaction hash format. Expected a 66-character hex string starting with 0x."
            }

        # 1. Fetch Transaction Receipt from BSC
        receipt = cls._rpc_call("eth_getTransactionReceipt", [clean_hash])
        if not receipt:
            return {
                "success": False,
                "error": "Transaction not found on BNB Smart Chain. It may still be pending confirmation. Please wait 15–30 seconds and try again."
            }

        status = receipt.get("status")
        if status != "0x1":
            return {
                "success": False,
                "error": "This transaction failed or was reverted on the blockchain."
            }

        target_padded = "0x" + "0" * 24 + TARGET_WALLET[2:].lower()
        found_transfer = None

        # 2. Check Event Logs for BEP20 Transfer to TARGET_WALLET
        logs = receipt.get("logs", [])
        for log in logs:
            topics = log.get("topics", [])
            if len(topics) >= 3 and topics[0].lower() == ERC20_TRANSFER_TOPIC.lower():
                recipient_topic = topics[2].lower()
                if recipient_topic == target_padded:
                    contract_addr = log.get("address", "").lower()
                    token_info = KNOWN_BEP20_TOKENS.get(contract_addr, {"symbol": "USDT", "decimals": 18})
                    decimals = token_info["decimals"]
                    raw_data = log.get("data", "0x0")
                    raw_amount = int(raw_data, 16)
                    amount = raw_amount / (10 ** decimals)
                    sender_topic = topics[1].lower()
                    sender_address = "0x" + sender_topic[-40:]

                    found_transfer = {
                        "token_symbol": token_info["symbol"],
                        "amount": amount,
                        "sender": sender_address,
                        "contract": contract_addr
                    }
                    break

        # 3. If no BEP20 transfer in logs, check for native BNB transfer
        if not found_transfer:
            tx_data = cls._rpc_call("eth_getTransactionByHash", [clean_hash])
            if tx_data and tx_data.get("to") and tx_data["to"].lower() == TARGET_WALLET.lower():
                raw_wei = int(tx_data.get("value", "0x0"), 16)
                bnb_val = raw_wei / (10 ** 18)
                bnb_price = cls._get_bnb_usd_price()
                usd_val = bnb_val * bnb_price
                found_transfer = {
                    "token_symbol": "BNB",
                    "amount": usd_val,
                    "sender": tx_data.get("from", ""),
                    "contract": "native_bnb",
                    "bnb_amount": round(bnb_val, 4)
                }

        if not found_transfer:
            return {
                "success": False,
                "error": f"Transaction verified on BSC, but no payment to target address ({TARGET_WALLET}) was detected in this transaction."
            }

        amount = found_transfer["amount"]
        token_symbol = found_transfer["token_symbol"]
        sender = found_transfer["sender"]

        # 4. Evaluate Plan Tier & Fee Tolerances
        # If user paid >= $65, they qualify for 30-Day Pro ($69 plan)
        # If user paid >= $17.50, they qualify for 7-Day Weekly Pass ($19 plan)
        if amount >= TIER_30D_MIN_TOLERANCE:
            approved_tier = "paid_30d"
            days_granted = 30
            plan_name = "30-Day Institutional Pro ($69)"
        elif amount >= TIER_7D_MIN_TOLERANCE:
            if expected_tier == "paid_30d":
                return {
                    "success": False,
                    "error": f"Received ~${amount:.2f} {token_symbol}, which qualifies for the 7-Day Plan ($19), but 30-Day Pro ($69) was selected. Please select the 7-day plan or send the remaining balance."
                }
            approved_tier = "paid_7d"
            days_granted = 7
            plan_name = "7-Day Full Access ($19)"
        else:
            return {
                "success": False,
                "error": f"Received amount (${amount:.2f} {token_symbol}) is below the minimum required for the 7-day plan ($19.00). Minimum required with fee tolerance is ${TIER_7D_MIN_TOLERANCE:.2f}."
            }

        block_number = int(receipt.get("blockNumber", "0x0"), 16)

        return {
            "success": True,
            "tx_hash": clean_hash,
            "amount": round(amount, 2),
            "token_symbol": token_symbol,
            "sender_address": sender,
            "receiver_address": TARGET_WALLET,
            "block_number": block_number,
            "approved_tier": approved_tier,
            "days_granted": days_granted,
            "plan_name": plan_name,
            "message": f"Payment of ~${amount:.2f} {token_symbol} verified successfully on BNB Smart Chain! {days_granted} days activated."
        }
