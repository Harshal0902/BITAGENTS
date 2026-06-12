import requests
import random
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import ollama

class VaultType(Enum):
    BALANCED = "balanced"

@dataclass
class MarketData:
    symbol: str
    price: float
    volume: float
    change_24h: float

@dataclass
class VaultState:
    vault_id: str
    capital: float
    initial_capital: float
    positions: dict = field(default_factory=dict)

    @property
    def pnl_pct(self):
        return (self.capital - self.initial_capital) / self.initial_capital

class MarketDataFeed:
    """
    Pulls Solana ecosystem tokens (up to 500) from CoinGecko.
    """

    URL = "https://api.coingecko.com/api/v3/coins/markets"

    def fetch(self):
        all_tokens = []

        for page in [1, 2]:  # 250 x 2 = 500
            params = {
                "vs_currency": "usd",
                "category": "solana-ecosystem",
                "order": "market_cap_desc",
                "per_page": 250,
                "page": page,
                "sparkline": False
            }

            r = requests.get(self.URL, params=params)
            data = r.json()

            for t in data:
                all_tokens.append(MarketData(
                    symbol=t["symbol"].upper() + "/USDT",
                    price=t["current_price"] or 0,
                    volume=t["total_volume"] or 0,
                    change_24h=t["price_change_percentage_24h"] or 0
                ))

        # keep only most volatile (IMPORTANT for LLM)
        all_tokens = sorted(
            all_tokens,
            key=lambda x: abs(x.change_24h),
            reverse=True
        )[:50]

        return all_tokens

class OllamaEngine:
    def __init__(self, model="llama3.2"):
        self.model = model

    def analyze(self, market_data, vault):
        snapshot = "\n".join(
            f"{d.symbol}: ${d.price:.4f} | {d.change_24h:+.2f}%"
            for d in market_data
        )

        prompt = f"""
You are a Solana crypto trading AI.

Focus on momentum and volatility.

Market:
{snapshot}
"""

        res = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )

        return res["message"]["content"]

    def signal(self, market_data, vault, analysis):
        prompt = f"""
Analysis:
{analysis}

Return ONLY JSON:

{{
  "action": "BUY|SELL|HOLD",
  "symbol": "TOKEN/USDT",
  "confidence": 0.0,
  "reasoning": "short sentence",
  "suggested_size": 0.0
}}
"""

        res = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )

        return json.loads(res["message"]["content"])

class TradeExecutor:
    def execute(self, signal, vault, market_data):
        prices = {d.symbol: d.price for d in market_data}
        price = prices.get(signal["symbol"])

        if not price:
            return {"status": "ignored"}

        if signal["action"] == "BUY":
            size = vault.capital * signal["suggested_size"]
            vault.capital -= size
            vault.positions[signal["symbol"]] = size / price

        elif signal["action"] == "SELL":
            vault.positions.pop(signal["symbol"], None)

        return signal

class ComputeVaultEngine:
    def __init__(self):
        self.feed = MarketDataFeed()
        self.llm = OllamaEngine()
        self.exec = TradeExecutor()

        self.vault = VaultState(
            vault_id=str(uuid.uuid4())[:8],
            capital=10000,
            initial_capital=10000
        )

    def run_cycle(self):
        market = self.feed.fetch()
        analysis = self.llm.analyze(market, self.vault)
        signal = self.llm.signal(market, self.vault, analysis)
        trade = self.exec.execute(signal, self.vault, market)

        return {
            "vault_id": self.vault.vault_id,
            "capital": self.vault.capital,
            "pnl_pct": self.vault.pnl_pct,
            "analysis": analysis,
            "signal": signal,
            "trade": trade,
            "top_tokens_used": len(market)
        }