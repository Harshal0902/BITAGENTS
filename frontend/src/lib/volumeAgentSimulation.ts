import { getAgentBySlug } from "@/lib/agentsCatalog";

const catalog = getAgentBySlug("volume");

export const VOLUME_AGENT = {
  id: "volume",
  name: catalog?.name ?? "Volume Agent",
  tagline: catalog?.tagline ?? "DLMM volume · pool infra",
  description:
    catalog?.description ??
    "Run Meteora DLMM volume campaigns with scheduled buy/sell cycles.",
  platformFeeRate: 0.0025,
  platformFeeLabel: "0.25% per swap leg",
  poolCreationCostSol: 0.02669,
};

export const VOLUME_EXAMPLE_PROMPTS = [
  "List my volume campaigns",
  "Check DLMM pool for my token",
  "How much SOL do I need for pool creation?",
] as const;
