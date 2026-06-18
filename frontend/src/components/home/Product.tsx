import { Wallet, Search, Workflow, Bot } from "lucide-react";

const cards = [
  { icon: Wallet, title: "Wallet Monitoring", body: "Track wallets, balances, token activity, and on-chain movement." },
  { icon: Search, title: "Research Agents", body: "Generate structured research summaries from market and project data." },
  { icon: Workflow, title: "On-Chain Automation", body: "Create workflows that can alert, prepare, and eventually execute actions." },
  { icon: Bot, title: "Agent Marketplace", body: "Discover, deploy, and run specialized agents from a unified on-chain marketplace." },
];

export function Product() {
  return (
    <section id="product" className="border-b border-grid">
      <div className="mx-auto max-w-7xl px-6 py-20 md:py-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-signal">Product</div>
        <div className="mt-4 grid gap-12 md:grid-cols-[1fr_1.4fr] md:items-start">
          <div>
            <h2 className="font-display text-4xl font-bold leading-tight md:text-5xl">
              From prompts to autonomous workflows.
            </h2>
            <p className="mt-6 max-w-md text-muted-foreground">
              BIT Agents turns everyday crypto workflows into agent-powered systems. Users can monitor wallets, research markets, automate repetitive tasks, and run everything from one agent marketplace.
            </p>
          </div>
          <div className="grid gap-px bg-[color:var(--border)] border border-grid sm:grid-cols-2">
            {cards.map(({ icon: Icon, title, body }) => (
              <div key={title} className="bg-background p-6">
                <Icon className="h-5 w-5 text-signal" />
                <div className="mt-5 font-display text-lg font-bold">{title}</div>
                <p className="mt-2 text-sm text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}