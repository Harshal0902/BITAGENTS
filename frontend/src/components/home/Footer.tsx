import { Logo } from "@/components/Logo";

export function Footer() {
  const cols = [
    { title: "Protocol", items: ["Agents", "Analytics", "Token Utility", "Roadmap"] },
    { title: "Build", items: ["Docs", "SDK", "Anchor programs", "Devnet"] },
    { title: "Stack", items: ["Solana", "Next.js", "TailwindCSS", "shadcn/ui"] },
    { title: "Community", items: ["Discord", "X / Twitter", "GitHub", "Mirror"] },
  ];
  return (
    <footer className="bg-background">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="grid gap-12 md:grid-cols-[1.4fr_2fr]">
          <div>
            <Logo className="h-14 w-auto" />
            <p className="mt-4 max-w-sm text-sm text-muted-foreground">
              The on-chain marketplace for autonomous AI agents. Wallet monitoring, research, automation, and on-chain workflows.
            </p>
            {/* <div className="mt-6 inline-flex items-center gap-2 border border-grid bg-surface/60 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-signal animate-pulse-dot" />
              Solana · Anchor · Devnet live
            </div> */}
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
        <div className="mt-14 flex flex-col items-start justify-between gap-4 border-t border-grid pt-6 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground md:flex-row md:items-center">
          <div className="flex flex-wrap gap-x-4 gap-y-2">
            <span>© 2026 BIT Agents · All rights reserved</span>
            <a href="/terms" className="transition hover:text-signal">
              Terms
            </a>
            <a href="/privacy" className="transition hover:text-signal">
              Privacy
            </a>
            <a href="/risk-disclaimer" className="transition hover:text-signal">
              Risk disclaimer
            </a>
          </div>
          <span>
            48 live agents · <span className="text-signal">12.4k tasks · 30d</span>
          </span>
        </div>
      </div>
    </footer>
  );
}