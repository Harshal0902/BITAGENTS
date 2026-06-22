import json
import requests
from datetime import datetime
from typing import Any

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1"

ETHERSCAN_API   = "https://api.etherscan.io/api"
ETHERSCAN_KEY   = "YourApiKeyToken"          # ToDo: free key → https://etherscan.io/apis
COINGECKO_API   = "https://api.coingecko.com/api/v3"
ETH_RPC         = "https://eth.llamarpc.com"

DEFI_AUDIT_API  = "https://api.de.fi/v1/audit"

def get_contract_audit_status(contract_address: str) -> dict:
    """
    Check if a contract has been audited.
    Queries De.Fi's public audit registry and falls back to
    checking Etherscan source-code verification status.
    """
    result = {
        "contract_address": contract_address,
        "source_verified": False,
        "is_proxy": False,
        "audits_found": [],
        "risk_flags": []
    }

    try:
        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": contract_address,
            "apikey": ETHERSCAN_KEY
        }
        r = requests.get(ETHERSCAN_API, params=params, timeout=10)
        data = r.json()
        if data.get("status") == "1" and data["result"]:
            info = data["result"][0]
            result["source_verified"] = bool(info.get("SourceCode"))
            result["compiler_version"] = info.get("CompilerVersion", "unknown")
            result["contract_name"] = info.get("ContractName", "unknown")
            result["is_proxy"] = info.get("Proxy", "0") == "1"
            result["license"] = info.get("LicenseType", "None")
            if not result["source_verified"]:
                result["risk_flags"].append("⚠️ Source code NOT verified on Etherscan")
            if result["is_proxy"]:
                result["risk_flags"].append("⚠️ Proxy contract - implementation can be upgraded")
    except Exception as e:
        result["risk_flags"].append(f"Etherscan lookup failed: {e}")

    try:
        r = requests.get(f"{DEFI_AUDIT_API}/{contract_address}", timeout=10)
        if r.status_code == 200:
            audit_data = r.json()
            if audit_data.get("audits"):
                for a in audit_data["audits"]:
                    result["audits_found"].append({
                        "auditor": a.get("auditor", "unknown"),
                        "date": a.get("date", "unknown"),
                        "critical_issues": a.get("critical", 0),
                        "high_issues": a.get("high", 0),
                    })
    except Exception:
        pass

    if not result["audits_found"]:
        result["risk_flags"].append("⚠️ No audit records found in De.Fi registry")

    return result


def get_holder_concentration(contract_address: str, top_n: int = 10) -> dict:
    """
    Fetch top token holders and calculate concentration risk.
    Uses Etherscan token holder endpoint.
    """
    try:
        params = {
            "module": "token",
            "action": "tokenholderlist",
            "contractaddress": contract_address,
            "page": 1,
            "offset": top_n,
            "apikey": ETHERSCAN_KEY
        }
        r = requests.get(ETHERSCAN_API, params=params, timeout=10)
        data = r.json()

        if data.get("status") == "1" and data["result"]:
            holders = data["result"]
            total_supply_raw = sum(int(h["TokenHolderQuantity"]) for h in holders)

            top_holders = []
            concentration = 0.0
            for h in holders[:top_n]:
                qty = int(h["TokenHolderQuantity"])
                pct = (qty / total_supply_raw * 100) if total_supply_raw else 0
                concentration += pct
                top_holders.append({
                    "address": h["TokenHolderAddress"],
                    "percentage": round(pct, 2)
                })

            risk_flags = []
            if top_holders and top_holders[0]["percentage"] > 20:
                risk_flags.append(f"🔴 Top holder owns {top_holders[0]['percentage']}% - whale risk")
            elif top_holders and top_holders[0]["percentage"] > 10:
                risk_flags.append(f"🟡 Top holder owns {top_holders[0]['percentage']}% - moderate concentration")

            if concentration > 70:
                risk_flags.append(f"🔴 Top {top_n} holders own {round(concentration, 1)}% of supply")
            elif concentration > 50:
                risk_flags.append(f"🟡 Top {top_n} holders own {round(concentration, 1)}% of supply")

            return {
                "contract_address": contract_address,
                "top_holders": top_holders,
                f"top_{top_n}_concentration_pct": round(concentration, 2),
                "risk_flags": risk_flags
            }

        return {
            "contract_address": contract_address,
            "top_holders": [],
            "risk_flags": ["⚠️ Could not fetch holder data - may need Etherscan Pro API"],
            "note": data.get("message", "No data")
        }
    except Exception as e:
        return {"error": str(e), "contract_address": contract_address}


def get_token_info_coingecko(token_id: str) -> dict:
    """
    Fetch token metadata from CoinGecko: team info, links, genesis date,
    market data, and community metrics. token_id is the CoinGecko slug
    (e.g. 'uniswap', 'chainlink', 'aave').
    """
    try:
        r = requests.get(
            f"{COINGECKO_API}/coins/{token_id}",
            params={"localization": "false", "tickers": "false",
                    "community_data": "true", "developer_data": "true"},
            timeout=15
        )
        if r.status_code != 200:
            return {"error": f"CoinGecko returned {r.status_code} for '{token_id}'"}

        d = r.json()
        links = d.get("links", {})
        dev   = d.get("developer_data", {})
        comm  = d.get("community_data", {})
        mkt   = d.get("market_data", {})

        risk_flags = []
        if not links.get("whitepaper"):
            risk_flags.append("⚠️ No whitepaper link found")
        if not links.get("repos_url", {}).get("github"):
            risk_flags.append("⚠️ No public GitHub repository")
        if dev.get("commit_count_4_weeks", 0) == 0:
            risk_flags.append("🟡 No GitHub commits in last 4 weeks - low dev activity")

        return {
            "name": d.get("name"),
            "symbol": d.get("symbol", "").upper(),
            "genesis_date": d.get("genesis_date"),
            "description_snippet": (d.get("description", {}).get("en", "") or "")[:300],
            "whitepaper": links.get("whitepaper"),
            "homepage": (links.get("homepage") or [""])[0],
            "github_repos": links.get("repos_url", {}).get("github", []),
            "twitter_followers": comm.get("twitter_followers"),
            "reddit_subscribers": comm.get("reddit_subscribers"),
            "github_commits_4w": dev.get("commit_count_4_weeks"),
            "github_stars": dev.get("stars"),
            "market_cap_usd": mkt.get("market_cap", {}).get("usd"),
            "fully_diluted_valuation": mkt.get("fully_diluted_valuation", {}).get("usd"),
            "circulating_supply": mkt.get("circulating_supply"),
            "total_supply": mkt.get("total_supply"),
            "all_time_high_usd": mkt.get("ath", {}).get("usd"),
            "price_change_90d_pct": mkt.get("price_change_percentage_90d_in_currency", {}).get("usd"),
            "risk_flags": risk_flags
        }
    except Exception as e:
        return {"error": str(e)}


def get_treasury_health(contract_address: str) -> dict:
    """
    Estimate treasury/protocol health by checking ETH balance
    and recent large outflows from the contract address.
    """
    try:
        payload = {
            "jsonrpc": "2.0", "method": "eth_getBalance",
            "params": [contract_address, "latest"], "id": 1
        }
        r = requests.post(ETH_RPC, json=payload, timeout=10)
        result = r.json()
        eth_balance = int(result["result"], 16) / 1e18 if "result" in result else 0

        params = {
            "module": "account", "action": "txlist",
            "address": contract_address,
            "startblock": 0, "endblock": 99999999,
            "page": 1, "offset": 20, "sort": "desc",
            "apikey": ETHERSCAN_KEY
        }
        r2 = requests.get(ETHERSCAN_API, params=params, timeout=10)
        tx_data = r2.json()

        outflows = []
        risk_flags = []

        if tx_data.get("status") == "1":
            for tx in tx_data["result"]:
                val = int(tx["value"]) / 1e18
                if tx["from"].lower() == contract_address.lower() and val > 1:
                    outflows.append({
                        "to": tx["to"],
                        "value_eth": round(val, 4),
                        "date": datetime.fromtimestamp(int(tx["timeStamp"])).strftime("%Y-%m-%d")
                    })

        if eth_balance < 1:
            risk_flags.append("🔴 Treasury ETH balance very low (< 1 ETH)")
        elif eth_balance < 10:
            risk_flags.append("🟡 Treasury ETH balance low (< 10 ETH)")

        if len(outflows) >= 5:
            risk_flags.append(f"🟡 {len(outflows)} large ETH outflows detected recently")

        return {
            "contract_address": contract_address,
            "treasury_eth_balance": round(eth_balance, 4),
            "recent_large_outflows": outflows[:5],
            "risk_flags": risk_flags
        }
    except Exception as e:
        return {"error": str(e)}


def check_honeypot_and_permissions(contract_address: str) -> dict:
    """
    Check for common security risks:
    - Honeypot detection via honeypot.is API
    - Mint / pause / blacklist function existence via Etherscan ABI
    """
    result = {
        "contract_address": contract_address,
        "is_honeypot": None,
        "honeypot_reason": None,
        "dangerous_functions": [],
        "risk_flags": []
    }

    try:
        r = requests.get(
            f"https://api.honeypot.is/v2/IsHoneypot?address={contract_address}",
            timeout=10
        )
        if r.status_code == 200:
            hp = r.json()
            result["is_honeypot"] = hp.get("isHoneypot", False)
            result["honeypot_reason"] = hp.get("honeypotReason")
            result["buy_tax_pct"]  = hp.get("simulationResult", {}).get("buyTax")
            result["sell_tax_pct"] = hp.get("simulationResult", {}).get("sellTax")

            if result["is_honeypot"]:
                result["risk_flags"].append(f"🔴 HONEYPOT DETECTED: {result['honeypot_reason']}")
            if result.get("sell_tax_pct") and result["sell_tax_pct"] > 10:
                result["risk_flags"].append(f"🔴 High sell tax: {result['sell_tax_pct']}%")
            elif result.get("sell_tax_pct") and result["sell_tax_pct"] > 5:
                result["risk_flags"].append(f"🟡 Elevated sell tax: {result['sell_tax_pct']}%")
    except Exception as e:
        result["risk_flags"].append(f"Honeypot check failed: {e}")

    try:
        params = {
            "module": "contract", "action": "getabi",
            "address": contract_address, "apikey": ETHERSCAN_KEY
        }
        r2 = requests.get(ETHERSCAN_API, params=params, timeout=10)
        abi_data = r2.json()
        if abi_data.get("status") == "1":
            abi = json.loads(abi_data["result"])
            danger_names = {"mint", "pause", "unpause", "blacklist", "whitelist",
                            "setFee", "excludeFromFee", "updateFee", "renounceOwnership",
                            "transferOwnership", "setMaxTxAmount", "setSwapAndLiquify"}
            for item in abi:
                if item.get("type") == "function" and item["name"].lower() in {d.lower() for d in danger_names}:
                    result["dangerous_functions"].append(item["name"])

            if result["dangerous_functions"]:
                result["risk_flags"].append(
                    f"⚠️ Privileged functions found: {', '.join(result['dangerous_functions'])}"
                )
    except Exception:
        pass

    return result


def get_vesting_and_unlock_schedule(token_id: str) -> dict:
    """
    Fetch token unlock / vesting data from CoinGecko developer data
    and supply metrics (circulating vs total vs max supply ratio).
    A large gap between circulating and total supply often indicates
    significant locked/vesting supply yet to be released.
    """
    try:
        r = requests.get(
            f"{COINGECKO_API}/coins/{token_id}",
            params={"localization": "false", "tickers": "false"},
            timeout=15
        )
        if r.status_code != 200:
            return {"error": f"CoinGecko returned {r.status_code}"}

        d   = r.json()
        mkt = d.get("market_data", {})
        circ  = mkt.get("circulating_supply") or 0
        total = mkt.get("total_supply") or 0
        max_s = mkt.get("max_supply") or 0

        risk_flags = []
        unlock_ratio = round(circ / total * 100, 1) if total else None

        if unlock_ratio and unlock_ratio < 30:
            risk_flags.append(
                f"🔴 Only {unlock_ratio}% of total supply circulating - large unlock risk"
            )
        elif unlock_ratio and unlock_ratio < 60:
            risk_flags.append(
                f"🟡 {unlock_ratio}% of total supply circulating - moderate unlock pressure possible"
            )

        return {
            "token": token_id,
            "circulating_supply": circ,
            "total_supply": total,
            "max_supply": max_s,
            "circulating_pct_of_total": unlock_ratio,
            "note": "Detailed vesting schedules are not on-chain by default. "
                    "Check TokenUnlocks.io or Messari for project-specific vesting data.",
            "risk_flags": risk_flags
        }
    except Exception as e:
        return {"error": str(e)}


def generate_due_diligence_score(findings: dict) -> dict:
    """
    Aggregate all risk flags from prior tool results into a final
    Green / Yellow / Red score with a breakdown. Pass a dict containing
    the collected risk_flags lists from all other tools.

    findings format:
    {
        "audit_flags": [...],
        "holder_flags": [...],
        "token_flags": [...],
        "treasury_flags": [...],
        "security_flags": [...],
        "vesting_flags": [...]
    }
    """
    red_flags    = []
    yellow_flags = []

    all_flags = (
        findings.get("audit_flags", []) +
        findings.get("holder_flags", []) +
        findings.get("token_flags", []) +
        findings.get("treasury_flags", []) +
        findings.get("security_flags", []) +
        findings.get("vesting_flags", [])
    )

    for flag in all_flags:
        flag_str = str(flag)
        if "🔴" in flag_str:
            red_flags.append(flag_str)
        elif "🟡" in flag_str or "⚠️" in flag_str:
            yellow_flags.append(flag_str)

    # Scoring logic
    if red_flags:
        score = "🔴 RED - HIGH RISK"
        summary = "Significant red flags detected. Proceed with extreme caution or avoid."
    elif len(yellow_flags) >= 3:
        score = "🟡 YELLOW - MODERATE RISK"
        summary = "Multiple caution signals. Do additional research before investing."
    elif yellow_flags:
        score = "🟡 YELLOW - CAUTION"
        summary = "Some caution signals present. Review carefully."
    else:
        score = "🟢 GREEN - LOWER RISK"
        summary = "No major red flags found. Standard investment caution still applies."

    return {
        "overall_score": score,
        "summary": summary,
        "red_flags": red_flags,
        "yellow_flags": yellow_flags,
        "total_flags": len(red_flags) + len(yellow_flags),
        "disclaimer": "This is automated analysis only, not financial advice. Always DYOR."
    }

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_contract_audit_status",
            "description": "Check if a smart contract has been audited and is source-verified on Etherscan. Returns audit records and proxy status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_address": {"type": "string", "description": "ERC-20 token contract address (0x...)"}
                },
                "required": ["contract_address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_holder_concentration",
            "description": "Fetch top token holders and calculate concentration risk. High concentration = whale / rug risk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_address": {"type": "string", "description": "ERC-20 token contract address"},
                    "top_n": {"type": "integer", "description": "Number of top holders to check (default 10)"}
                },
                "required": ["contract_address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_info_coingecko",
            "description": "Get token metadata from CoinGecko: team links, GitHub activity, market cap, supply, whitepaper, community size. Use the CoinGecko slug (e.g. 'uniswap', 'chainlink').",
            "parameters": {
                "type": "object",
                "properties": {
                    "token_id": {"type": "string", "description": "CoinGecko token slug/ID (e.g. 'uniswap', 'aave', 'chainlink')"}
                },
                "required": ["token_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_treasury_health",
            "description": "Check the treasury/protocol wallet ETH balance and detect large recent outflows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_address": {"type": "string", "description": "Contract or treasury wallet address"}
                },
                "required": ["contract_address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_honeypot_and_permissions",
            "description": "Check for honeypot traps, high sell taxes, and dangerous privileged functions (mint, pause, blacklist) in the contract ABI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_address": {"type": "string", "description": "ERC-20 token contract address"}
                },
                "required": ["contract_address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_vesting_and_unlock_schedule",
            "description": "Estimate vesting / unlock risk by comparing circulating vs total supply. Large gaps indicate future sell pressure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "token_id": {"type": "string", "description": "CoinGecko token slug (e.g. 'uniswap', 'chainlink')"}
                },
                "required": ["token_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_due_diligence_score",
            "description": "Aggregate all collected risk flags into a final Green / Yellow / Red due diligence score. Call this LAST after running the other checks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "object",
                        "description": "Dict with keys: audit_flags, holder_flags, token_flags, treasury_flags, security_flags, vesting_flags - each a list of flag strings from the other tools.",
                        "properties": {
                            "audit_flags":    {"type": "array", "items": {"type": "string"}},
                            "holder_flags":   {"type": "array", "items": {"type": "string"}},
                            "token_flags":    {"type": "array", "items": {"type": "string"}},
                            "treasury_flags": {"type": "array", "items": {"type": "string"}},
                            "security_flags": {"type": "array", "items": {"type": "string"}},
                            "vesting_flags":  {"type": "array", "items": {"type": "string"}}
                        }
                    }
                },
                "required": ["findings"]
            }
        }
    }
]

TOOL_MAP = {
    "get_contract_audit_status":       get_contract_audit_status,
    "get_holder_concentration":        get_holder_concentration,
    "get_token_info_coingecko":        get_token_info_coingecko,
    "get_treasury_health":             get_treasury_health,
    "check_honeypot_and_permissions":  check_honeypot_and_permissions,
    "get_vesting_and_unlock_schedule": get_vesting_and_unlock_schedule,
    "generate_due_diligence_score":    generate_due_diligence_score,
}

SYSTEM_PROMPT = """You are a crypto due diligence AI agent. When a user asks you to check or audit a token, you:

1. Run ALL of the following checks IN ORDER:
   a. get_contract_audit_status  (needs contract address)
   b. check_honeypot_and_permissions (needs contract address)
   c. get_holder_concentration   (needs contract address)
   d. get_treasury_health        (needs contract address)
   e. get_token_info_coingecko   (needs CoinGecko slug)
   f. get_vesting_and_unlock_schedule (needs CoinGecko slug)
   g. generate_due_diligence_score  (pass all risk_flags collected above)

2. Present a clean report with sections: Audit, Security, Holders, Treasury, Team & Tokenomics, Vesting, and the final 🟢/🟡/🔴 score.

If the user only provides a contract address (no CoinGecko slug), skip steps e and f and note that team/vesting data requires the CoinGecko token ID.
If the user asks about a single aspect (e.g. "is this a honeypot?"), only run the relevant tool.

Be concise. Lead with the score. Always end with the disclaimer that this is not financial advice."""

def call_ollama(messages: list) -> Any:
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "stream": False
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def execute_tool(tool_name: str, tool_args: dict) -> str:
    func = TOOL_MAP.get(tool_name)
    if not func:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = func(**tool_args)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def run_agent(user_input: str, conversation_history: list) -> tuple[str, list]:
    conversation_history.append({"role": "user", "content": user_input})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history

    max_iterations = 10  # DD needs more iterations (7 tools)
    for i in range(max_iterations):
        response = call_ollama(messages)
        message = response["message"]
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            assistant_reply = message.get("content", "")
            conversation_history.append({"role": "assistant", "content": assistant_reply})
            return assistant_reply, conversation_history

        print(f"  🔧 Tools: {[tc['function']['name'] for tc in tool_calls]}")
        messages.append({
            "role": "assistant",
            "content": message.get("content", ""),
            "tool_calls": tool_calls
        })

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            tool_args = tc["function"].get("arguments", {})
            if isinstance(tool_args, str):
                tool_args = json.loads(tool_args)

            print(f"  📡 {tool_name}({list(tool_args.values())})...")
            result = execute_tool(tool_name, tool_args)
            print(f"  ✅ Done")

            messages.append({"role": "tool", "content": result})

    return "Agent reached maximum iterations.", conversation_history

def main():
    print("=" * 65)
    print("  🔍 Due Diligence AI Agent")
    print("  Checks: Audits · Holders · Honeypot · Treasury · Team · Vesting")
    print("  Powered by Ollama")
    print("=" * 65)
    print(f"  Model   : {MODEL}")
    print(f"  Network : Ethereum Mainnet")
    print()
    print("  Example queries:")
    print("  • Run full due diligence on LINK")
    print("    contract: 0x514910771AF9Ca656af840dff83E8264EcF986CA")
    print("    coingecko: chainlink")
    print()
    print("  • Is 0x514910771AF9Ca656af840dff83E8264EcF986CA a honeypot?")
    print("  • Check holder concentration for 0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984")
    print("  • What's the vesting risk for uniswap?")
    print("  • Full DD: contract 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2, token weth")
    print()
    print("  Type 'quit' to exit, 'clear' to reset conversation")
    print("=" * 65)
    print()

    conversation_history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("👋 Goodbye!")
            break
        if user_input.lower() == "clear":
            conversation_history = []
            print("🔄 Conversation cleared.\n")
            continue

        print()
        try:
            reply, conversation_history = run_agent(user_input, conversation_history)
            print(f"Agent:\n{reply}")
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to Ollama. Make sure it's running: `ollama serve`")
        except Exception as e:
            print(f"❌ Error: {e}")
        print()


if __name__ == "__main__":
    main()