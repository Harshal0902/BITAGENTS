import type { Metadata } from "next";
import Link from "next/link";
import { AppShell, Panel } from "@/components/AppShell";
import { DCA_AGENT } from "@/lib/dcaAgentSimulation";

export const metadata: Metadata = {
  title: "Agents — BIT Agents",
  description: "Browse and run autonomous AI agents on the BIT Agents marketplace.",
};

export default function AgentsPage() {
  const running = DCA_AGENT.status === "Running";

  return (
    <AppShell
      title="Agent Marketplace"
      subtitle="Discover and run specialized AI agents for on-chain workflows."
    >
      <Link href={`/agents/${DCA_AGENT.slug}`} className="group block max-w-2xl">
        <Panel
          title={`// ${DCA_AGENT.strategy}`}
          action={
            <span
              className={`inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] ${
                running ? "text-signal" : "text-muted-foreground"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  running ? "bg-signal animate-pulse-dot" : "bg-muted-foreground"
                }`}
              />
              {DCA_AGENT.status}
            </span>
          }
        >
          <div className="font-display text-2xl font-bold transition group-hover:text-signal">
            {DCA_AGENT.name}
          </div>
          <p className="mt-2 text-sm text-muted-foreground">{DCA_AGENT.tagline}</p>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{DCA_AGENT.description}</p>

          <div className="mt-1 font-mono text-xs text-muted-foreground">↳ {DCA_AGENT.task}</div>

          <div className="mt-6 flex flex-wrap gap-4 border-t border-grid pt-5 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
            <span>
              Model <span className="ml-1 text-foreground">{DCA_AGENT.model}</span>
            </span>
            <span>
              Cluster <span className="ml-1 text-foreground">{DCA_AGENT.cluster}</span>
            </span>
            <span className="text-signal transition group-hover:underline">Open agent →</span>
          </div>
        </Panel>
      </Link>
    </AppShell>
  );
}
