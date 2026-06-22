import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { AgentCard } from "@/components/agents/AgentCard";
import { AppShell, Stat } from "@/components/AppShell";
import {
  AGENT_CATEGORIES,
  FEATURED_AGENTS,
  MARKETPLACE_STATS,
} from "@/lib/agentsCatalog";

export function AgentMarketplace() {
  const listedCount = FEATURED_AGENTS.length;

  return (
    <AppShell
      title="Agent Marketplace"
      subtitle="Discover and deploy autonomous AI agents. Pay per task · settle on Solana."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Live agents" value={MARKETPLACE_STATS.liveAgents} accent="signal" />
        <Stat label="Tasks · 24h" value={MARKETPLACE_STATS.tasks24h} />
        <Stat label="Active builders" value={MARKETPLACE_STATS.activeBuilders} />
        <Stat label="Uptime · 30d" value={MARKETPLACE_STATS.uptime30d} accent="signal" />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_280px]">
        <section>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
              // Featured agents
            </h2>
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              {listedCount} listed
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {FEATURED_AGENTS.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        </section>

        <aside className="space-y-6">
          <div className="border border-grid bg-surface/40">
            <div className="border-b border-grid px-4 py-2.5">
              <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                // Categories
              </span>
            </div>
            <ul className="divide-y divide-grid">
              {AGENT_CATEGORIES.map(({ name, count }) => (
                <li
                  key={name}
                  className="flex items-center justify-between px-4 py-3 font-mono text-xs uppercase tracking-[0.12em]"
                >
                  <span className="text-foreground">{name}</span>
                  <span className="text-muted-foreground">{count}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="border border-grid bg-surface/40">
            <div className="border-b border-grid px-4 py-2.5">
              <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                // Quick links
              </span>
            </div>
            <div className="space-y-3 p-4">
              <Link
                href="/agents/dca"
                className="flex items-center justify-between bg-signal px-4 py-3 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-primary-foreground transition hover:opacity-90"
              >
                Monitor running agents
                <ArrowRight size={14} />
              </Link>
              <Link
                href="/analytics"
                className="flex items-center justify-between border border-grid px-4 py-3 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-foreground transition hover:border-signal hover:text-signal"
              >
                Protocol analytics
                <ArrowRight size={14} />
              </Link>
            </div>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
