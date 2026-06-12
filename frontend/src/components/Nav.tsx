"use client";

import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { SolanaProviders } from "@/components/SolanaProviders";

const appLinks = [
  { href: "/marketplace", label: "Marketplace" },
  { href: "/provider", label: "Provider" },
  { href: "/vaults", label: "Vaults" },
  { href: "/agents", label: "Agents" },
  { href: "/analytics", label: "Analytics" }
];

const marketingLinks = [
  { href: "/#product", label: "Product" },
  { href: "/#compute", label: "Compute" },
  { href: "/#token-utility", label: "Token Utility" },
  { href: "/#roadmap", label: "Roadmap" }
];

export function Nav({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);
  const isPublicPage = pathname === "/" || pathname === "/coming-soon";

  useEffect(() => {
    setMounted(true);
  }, []);

  if (isPublicPage) {
    return <PublicShell>{children}</PublicShell>;
  }

  if (!mounted) {
    return (
      <div className="min-h-screen">
        <AppHeader pathname={pathname} walletReady={false} />
        <main>
          <div className="mx-auto max-w-7xl px-6 py-10">
            <div className="border border-grid bg-surface/40 p-6 font-mono text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Loading app runtime...
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <SolanaProviders>
      <div className="min-h-screen">
        <AppHeader pathname={pathname} walletReady />
        <main>{children}</main>
      </div>
    </SolanaProviders>
  );
}

function PublicShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f5efe6]">
      <header className="sticky top-0 z-30 border-b border-[#ded2c3] bg-[#f5efe6] backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-6">
          <Link href="/" className="flex items-center">
            <Wordmark compact />
          </Link>

          <nav className="hidden items-center gap-7 text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground md:flex">
            {marketingLinks.map(({ href, label }) => (
              <Link key={href} href={href} className="transition hover:text-foreground">
                {label}
              </Link>
            ))}
          </nav>

          <Link
            href="/marketplace"
            className="inline-flex items-center justify-center gap-2 rounded-md bg-[#d76545] px-4 py-2 text-sm font-black text-[#fff8ef] transition hover:bg-[#bd5134]"
          >
            Launch App <ArrowUpRight size={16} />
          </Link>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}

function AppHeader({ pathname, walletReady }: { pathname: string; walletReady: boolean }) {
  return (
    <header className="sticky top-0 z-30 border-b bg-background/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-6">
        <Link href="/" className="flex items-center">
          <Wordmark compact />
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {appLinks.map(({ href, label }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2 rounded-md px-3 py-1 text-xs font-mono uppercase tracking-[0.14em] ${active
                  ? "text-ember transition hover:text-[#2B2118] rounded-none border-2 border-[#E6DAC1]"
                  : "hover:text-black"
                  }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden sm:block">
          {walletReady ? (
            <WalletMultiButton className="wallet-connect-btn" />
          ) : (
            <div className="h-[38px] w-[156px] border-2 border-grid" />
          )}
        </div>
      </div>

      <div className="mx-auto flex max-w-7xl items-center gap-1 overflow-x-auto px-4 pb-3 sm:hidden">
        {appLinks.map(({ href, label }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex min-w-fit items-center gap-2 rounded-md px-3 py-2 text-sm font-bold ${active ? "bg-ember text-ink" : "bg-panel text-slate-300"}`}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}

export function Wordmark({ compact = false }: { compact?: boolean }) {
  const width = compact ? 132 : 390;

  return (
    <img
      src="/bit-agents-logo-transparent.png"
      alt="BIT Agents"
      width={width}
      height={Math.round(width * 0.8)}
      className={compact ? "block h-12 object-contain object-left" : "block h-auto max-w-full object-contain object-left"}
      style={{ width: compact ? 132 : "min(390px, 100%)" }}
    />
  );
}
