"use client";

import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const appLinks = [
  { href: "/agents", label: "Agents" },
  { href: "/analytics", label: "Analytics" },
];

const marketingLinks = [
  { href: "/#product", label: "Product" },
  { href: "/#how", label: "How It Works" },
  { href: "/#token-utility", label: "Token Utility" },
  { href: "/#roadmap", label: "Roadmap" },
];

const navLinkBase =
  "px-3 py-1.5 text-xs font-mono uppercase tracking-[0.14em] transition border";

function appLinkClass(active: boolean) {
  return active
    ? `${navLinkBase} border-signal bg-surface/60 text-signal`
    : `${navLinkBase} border-transparent text-muted-foreground hover:border-grid hover:bg-surface/40 hover:text-foreground`;
}

export function Nav({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublicPage = pathname === "/" || pathname === "/coming-soon";

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-grid bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-6">
          <Link href="/" className="flex items-center">
            <Wordmark compact />
          </Link>

          {isPublicPage ? (
            <>
              <nav className="hidden items-center gap-7 text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground md:flex">
                {marketingLinks.map(({ href, label }) => (
                  <Link key={href} href={href} className="transition hover:text-foreground">
                    {label}
                  </Link>
                ))}
              </nav>
              <Link
                href="/agents"
                className="inline-flex items-center justify-center gap-2 bg-signal px-4 py-2 text-sm font-mono font-semibold uppercase tracking-[0.12em] text-primary-foreground transition hover:opacity-90"
              >
                Launch App <ArrowUpRight size={16} />
              </Link>
            </>
          ) : (
            <>
              <nav className="hidden items-center gap-2 md:flex">
                {appLinks.map(({ href, label }) => (
                  <Link key={href} href={href} className={appLinkClass(pathname === href || (href === "/agents" && pathname.startsWith("/agents/")))}>
                    {label}
                  </Link>
                ))}
              </nav>
              <div className="hidden sm:block">
                <WalletMultiButton className="wallet-connect-btn" />
              </div>
            </>
          )}
        </div>

        {!isPublicPage && (
          <div className="mx-auto flex max-w-7xl items-center gap-2 overflow-x-auto px-4 pb-3 sm:hidden">
            {appLinks.map(({ href, label }) => (
              <Link key={href} href={href} className={`min-w-fit ${appLinkClass(pathname === href || (href === "/agents" && pathname.startsWith("/agents/")))}`}>
                {label}
              </Link>
            ))}
          </div>
        )}
      </header>
      <main>{children}</main>
    </div>
  );
}

export function Wordmark({ compact = false }: { compact?: boolean }) {
  const width = compact ? 200 : 390;

  return (
    <img
      src="/bit-agents-logo-transparent.png"
      alt="BIT Agents"
      width={width}
      height={Math.round(width * 0.8)}
      className={compact ? "block h-16 object-contain object-left" : "block h-auto max-w-full object-contain object-left"}
      style={{ width: compact ? 200 : "min(390px, 100%)" }}
    />
  );
}
