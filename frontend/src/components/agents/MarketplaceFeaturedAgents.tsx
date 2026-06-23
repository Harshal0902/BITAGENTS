"use client";

import { useEffect, useMemo, useState } from "react";
import { AgentCard } from "@/components/agents/AgentCard";
import { FEATURED_AGENTS } from "@/lib/agentsCatalog";
import { fetchPlatformMetrics, formatMetricNumber } from "@/lib/dcaPlanClient";

export function MarketplaceFeaturedAgents() {
  const [totalRuns, setTotalRuns] = useState<string | null>(null);

  useEffect(() => {
    void fetchPlatformMetrics().then((metrics) => {
      if (!metrics) return;
      setTotalRuns(
        formatMetricNumber(metrics.successful_swaps ?? metrics.total_executions ?? 0)
      );
    });
  }, []);

  const agents = useMemo(
    () =>
      FEATURED_AGENTS.map((agent) => {
        if (agent.slug !== "dca" || !totalRuns) return agent;
        return { ...agent, runs: totalRuns };
      }),
    [totalRuns]
  );

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {agents.map((agent) => (
        <AgentCard
          key={agent.id}
          agent={agent}
          runsLabel={agent.slug === "dca" ? "Total tx" : "Runs"}
        />
      ))}
    </div>
  );
}
