import { Logo } from "@/components/Logo";

export function Footer() {
  const cols = [
    { title: "Protocol", items: ["Marketplace", "Vaults", "Agents", "Providers"] },
    { title: "Build", items: ["Docs", "SDK", "Anchor programs", "Devnet"] },
    { title: "Stack", items: ["Solana", "Next.js", "TailwindCSS", "shadcn/ui"] },
    { title: "Community", items: ["Discord", "X / Twitter", "GitHub", "Mirror"] },
  ];
  return (
    <footer className="bg-background">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="grid gap-12 md:grid-cols-[1.4fr_2fr]">
          <div>
            <Logo className="h-10 w-auto" />
            <p className="mt-4 max-w-sm text-sm text-muted-foreground">
              AI agents powered by decentralized compute. Wallet monitoring, research, automation, and on-chain workflows.
            </p>
            <div className="mt-6 inline-flex items-center gap-2 border border-grid bg-surface/60 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-signal animate-pulse-dot" />
              Solana · Anchor · Devnet live
            </div>
          </div>
          <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
            {cols.map((c) => (
              <div key={c.title}>
                <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-signal">{c.title}</div>
                <ul className="mt-4 space-y-2.5 text-sm text-muted-foreground">
                  {c.items.map((i) => (
                    <li key={i}><a href="#" className="transition hover:text-foreground">{i}</a></li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-14 flex flex-col items-start justify-between gap-3 border-t border-grid pt-6 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground md:flex-row md:items-center">
          <span>© 2026 BIT Agents · All rights reserved</span>
          <span>cGPU index · 0.4150 · <span className="text-signal">+0.6%</span></span>
        </div>
      </div>
    </footer>
  );
}