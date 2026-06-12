import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "@/components/Logo";

const NAV = [
  { to: "/marketplace", label: "Marketplace" },
  { to: "/provider", label: "Provider" },
  { to: "/vaults", label: "Vaults" },
  { to: "/agents", label: "Agents" },
  { to: "/analytics", label: "Analytics" },
];

export function AppShell({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="min-h-screen text-foreground">
      {/* <header className="sticky top-0 z-40 border-b border-grid bg-background/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
          <Link href="/" className="flex items-center gap-3">
            <Logo className="h-7 w-auto" />
            <span className="ml-1 hidden text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground md:inline">/ devnet</span>
          </Link>
          <nav className="hidden items-center gap-1 text-xs font-mono uppercase tracking-[0.14em] md:flex">
            {NAV.map((l) => (
              <Link
                key={l.to}
                href={l.to}
                className="px-3 py-1.5 text-muted-foreground transition hover:text-foreground"
                // activeProps={{ className: "px-3 py-1.5 text-signal border border-grid bg-surface/60" }}
              >
                {l.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-signal animate-pulse-dot" />
            <span className="hidden sm:inline">wallet · 7Hk…q4Px</span>
          </div>
        </div>
      </header> */}
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="mb-8 flex flex-col items-start justify-between gap-2 border-b border-grid pb-6 md:flex-row md:items-end">
          <div>
            <h1 className="font-display text-3xl font-bold leading-tight md:text-4xl">{title}</h1>
            {subtitle && <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>}
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
            block 284,193,402 · slot 18.4k
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Panel({ title, action, children, className = "" }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={`border border-grid bg-surface/40 ${className}`}>
      {title && (
        <div className="flex items-center justify-between border-b border-grid px-4 py-2.5">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">{title}</span>
          {action}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

export function Stat({ label, value, accent }: { label: string; value: string; accent?: "signal" | "warn" }) {
  return (
    <div className="border border-grid bg-surface/40 p-4">
      <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">{label}</div>
      <div className={`mt-2 font-display text-2xl font-bold tabular-nums ${accent === "signal" ? "text-signal" : accent === "warn" ? "text-warn" : ""}`}>{value}</div>
    </div>
  );
}
