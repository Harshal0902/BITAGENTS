export type ResearchAgentSlug =
  | "whale-tracking"
  | "token-research"
  | "wallet-monitoring"
  | "due-diligence";

export type ResearchAgentConfig = {
  slug: ResearchAgentSlug;
  name: string;
  tagline: string;
  description: string;
  model: string;
  cluster: string;
  assistantLabel: string;
  examplePrompts: readonly string[];
};

export const RESEARCH_AGENTS: Record<ResearchAgentSlug, ResearchAgentConfig> = {
  "whale-tracking": {
    slug: "whale-tracking",
    name: "Whale Tracking Agent",
    tagline: "Wallet intel · copy-trade research",
    description:
      "Track Solana wallet addresses, monitor smart-money activity, maintain watchlists, and research copy-trade opportunities.",
    model: "meta-llama/llama-3.1-8b-instruct",
    cluster: "mainnet",
    assistantLabel: "Whale Agent",
    examplePrompts: [
      "List curated whale wallets",
      "Analyze wallet 5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
      "Add a wallet to my watchlist",
      "Preview copy trade for a whale buying BONK",
    ],
  },
  "token-research": {
    slug: "token-research",
    name: "Token Research Agent",
    tagline: "On-chain RPC · Jupiter · Meteora",
    description:
      "Research any Solana token using on-chain RPC data, Jupiter prices, and Meteora pool metrics.",
    model: "meta-llama/llama-3.1-8b-instruct",
    cluster: "mainnet",
    assistantLabel: "Research Agent",
    examplePrompts: [
      "Search for WIF on EASY Screener",
      "Give me a research brief on JUP",
      "Compare BONK and WIF",
      "What are the risks for this mint?",
    ],
  },
  "wallet-monitoring": {
    slug: "wallet-monitoring",
    name: "Wallet Monitoring Agent",
    tagline: "Portfolio snapshot · trade ideas",
    description:
      "Monitor your connected wallet — SOL balance, SPL holdings, recent activity, and informational trade suggestions.",
    model: "meta-llama/llama-3.1-8b-instruct",
    cluster: "mainnet",
    assistantLabel: "Wallet Agent",
    examplePrompts: [
      "Analyze my connected wallet",
      "What tokens do I hold?",
      "Suggest trades for my portfolio",
      "How is my SOL balance looking?",
    ],
  },
  "due-diligence": {
    slug: "due-diligence",
    name: "Due Diligence Agent",
    tagline: "Mint authority · risk score",
    description:
      "Due diligence on tokens and SPL mints before you interact — authorities, holder concentration, liquidity, and graded risk.",
    model: "meta-llama/llama-3.1-8b-instruct",
    cluster: "mainnet",
    assistantLabel: "Diligence Agent",
    examplePrompts: [
      "Run due diligence on JUP",
      "Check mint and freeze authority for this token",
      "Is this token safe to buy?",
      "Show top holders and concentration risk",
    ],
  },
};

export function getResearchAgentConfig(slug: string): ResearchAgentConfig | undefined {
  return RESEARCH_AGENTS[slug as ResearchAgentSlug];
}
