import type { Metadata } from "next";
import { AgentMarketplace } from "@/components/agents/AgentMarketplace";

export const metadata: Metadata = {
  title: "Agent Marketplace - BIT Agents",
  description: "Discover and deploy autonomous AI agents on the BIT Agents marketplace.",
};

export default function AgentsPage() {
  return <AgentMarketplace />;
}
