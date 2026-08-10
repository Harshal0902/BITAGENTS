export const HEDGE_FUND = {
  slug: "hedge-fund",
  name: "Hedge Fund Agent",
  tagline: "18-analyst · paper · 4h monitor",
  description:
    "Deterministic 18-analyst portfolio system (quant/value/macro), code-enforced risk, horizon-based asset picks, multi-strategy paper book, and SPY-benchmarked backtests. LLM optional — never required for trades.",
  model: "meta-llama/llama-3.1-8b-instruct",
  cluster: "mainnet",
  assistantLabel: "Fund Manager",
  managementFeePct: 1,
  performanceFeePct: 10,
  examplePrompts: [
    "Create a paper strategy for 2 weeks — pick the best assets, TP 12 SL 6",
    "I will trade for 6 months, choose stocks or crypto for max profit",
    "Create paper strategy with NVDA META BTC, horizon 30 days, TP 20 SL 10",
    "Show my paper dashboard by strategy",
    "Backtest my strategy for 6m vs SPY",
  ],
} as const;
