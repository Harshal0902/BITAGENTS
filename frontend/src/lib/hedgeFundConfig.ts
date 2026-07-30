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
    "Analyze portfolio SOL JUP BITAGENTS with $10,000",
    "Run portfolio analysis on BONK WIF with 5k capital",
    "What is the 1/10 fee structure?",
    "Analyze BITAGENTS for a $25k allocation",
  ],
} as const;
