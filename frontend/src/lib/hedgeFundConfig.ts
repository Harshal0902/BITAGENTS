export const HEDGE_FUND = {
  slug: "hedge-fund",
  name: "Hedge Fund Agent",
  tagline: "Paper trading · 1/10 fees · 4h monitor",
  description:
    "Paper-trading hedge fund: pick stocks/crypto or let the agent choose, save TP/SL rules, monitor markets every 4 hours with shared quotes, and backtest strategies (1w–1y).",
  model: "meta-llama/llama-3.1-8b-instruct",
  cluster: "mainnet",
  assistantLabel: "Fund Manager",
  managementFeePct: 1,
  performanceFeePct: 10,
  examplePrompts: [
    "Create a paper strategy — you pick stocks or crypto, TP 15 SL 8",
    "Create paper strategy with AAPL NVDA BTC ETH, TP 20 SL 10",
    "Show my paper dashboard",
    "Backtest my strategy for 6m",
    "Set TP 25 SL 12 on my strategy",
  ],
} as const;
