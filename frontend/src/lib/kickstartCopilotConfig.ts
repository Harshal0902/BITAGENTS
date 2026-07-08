export const KICKSTART_COPILOT = {
  id: "kickstart-copilot",
  name: "EasyA Analysis Agent",
  slug: "kickstart-copilot",
  tagline: "Solana token analysis · powered by EASY Screener",
  description:
    "AI agent for live Solana token research - price, liquidity, holders, risk checks, health scores, and diligence summaries using EASY Screener data.",
  status: "Running" as const,
  model: "meta-llama/llama-3.3-70b-instruct",
  cluster: "mainnet-beta",
  dataSource: "EASY Screener",
  dataSourceUrl: "https://easyscreener.xyz",
};

export const KICKSTART_EXAMPLE_PROMPTS = [
  "Give me an overview of $COLD",
  "Give me an overview of BITAGENTS",
  "Analyze BITAGENTS token health",
  "Search tokens named cold",
  "Compare CPX and BITAGENTS",
  "Show my EasyA trading wallet balance",
  "Market buy 0.01 SOL of BITAGENTS",
] as const;
