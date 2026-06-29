export const KICKSTART_COPILOT = {
  id: "kickstart-copilot",
  name: "EasyA Analysis Agent",
  slug: "kickstart-copilot",
  tagline: "Token discovery · analytics · health scores",
  description:
    "Free AI copilot for Solana token research, comparisons, risk checks, and launch operations guidance.",
  status: "Running" as const,
  model: "meta-llama/llama-3.3-70b-instruct",
  cluster: "mainnet-beta",
};

export const KICKSTART_EXAMPLE_PROMPTS = [
  "List verified Kickstart tokens",
  "Give me an overview of BITAGENTS",
  "Analyze BITAGENTS token health",
  "What are the risks for BIT AGENTS?",
  "How do I lock liquidity for BITAGENTS?",
  "Watch BITAGENTS",
] as const;
