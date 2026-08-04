export const HEDGE_FUND = {
  slug: "hedge-fund",
  name: "Hedge Fund Agent",
  tagline: "Covenant governance · 1/10 fees",
  description:
    "Covenant-inspired multi-analyst portfolio agent for Solana tokens — deterministic quant/value signals, code-enforced risk limits, and LLM macro synthesis.",
  model: "meta-llama/llama-3.1-8b-instruct",
  cluster: "mainnet",
  assistantLabel: "Fund Manager",
  managementFeePct: 1,
  performanceFeePct: 10,
  examplePrompts: [
    "You have 10000 USD and can trade stocks or crypto between 2025-12-01 and 2026-06-30. Name assets, allocation, buys/sells, and PnL",
    "Backtest AAPL MSFT NVDA BTC ETH from 2025-12-01 to 2026-04-30 with $10,000",
    "Analyze portfolio SOL JUP with $10,000",
    "What is the 1/10 fee structure?",
  ],
} as const;
