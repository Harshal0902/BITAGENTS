"use client";

import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { ArrowUpRight, Cpu, LayoutDashboard, RadioTower, ScrollText } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const appLinks = [
  { href: "/dashboard", label: "Tasks", icon: LayoutDashboard },
  { href: "/provider", label: "Provider", icon: Cpu },
  { href: "/demo", label: "Demo", icon: RadioTower },
  { href: "/utility", label: "Utility", icon: ScrollText }
];

const marketingLinks = [
  { href: "/#product", label: "Product" },
  { href: "/#compute", label: "Compute" },
  { href: "/#token-utility", label: "Token Utility" },
  { href: "/#roadmap", label: "Roadmap" }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublicPage = pathname === "/" || pathname === "/coming-soon";

  return (
    <div className={isPublicPage ? "min-h-screen bg-[#f5efe6]" : "min-h-screen"}>
      <header className={isPublicPage ? "sticky top-0 z-30 border-b border-[#ded2c3] bg-[#f5efe6] backdrop-blur" : "sticky top-0 z-30 border-b border-line/80 bg-ink/90 backdrop-blur"}>
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center">
            <Wordmark compact />
          </Link>

          {isPublicPage ? (
            <>
              <nav className="hidden items-center gap-1 md:flex">
                {marketingLinks.map(({ href, label }) => (
                  <Link
                    key={href}
                    href={href}
                    className="rounded-md px-3 py-2 text-sm font-bold text-[#4c4036] transition hover:bg-[#eadfd2] hover:text-[#211912]"
                  >
                    {label}
                  </Link>
                ))}
              </nav>
              <Link
                href="/coming-soon"
                className="inline-flex items-center justify-center gap-2 rounded-md bg-[#d76545] px-4 py-2 text-sm font-black text-[#fff8ef] transition hover:bg-[#bd5134]"
              >
                Launch App <ArrowUpRight size={16} />
              </Link>
            </>
          ) : (
            <>
              <nav className="hidden items-center gap-1 md:flex">
                {appLinks.map(({ href, label, icon: Icon }) => {
                  const active = pathname === href;
                  return (
                    <Link
                      key={href}
                      href={href}
                      className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-bold transition ${
                        active
                          ? "bg-ember text-ink"
                          : "text-slate-300 hover:bg-panel hover:text-white"
                      }`}
                    >
                      <Icon size={16} />
                      {label}
                    </Link>
                  );
                })}
              </nav>
              <div className="hidden sm:block">
                <WalletMultiButton />
              </div>
            </>
          )}
        </div>

        {!isPublicPage && (
          <div className="mx-auto flex max-w-7xl items-center gap-1 overflow-x-auto px-4 pb-3 sm:hidden">
            {appLinks.map(({ href, label, icon: Icon }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex min-w-fit items-center gap-2 rounded-md px-3 py-2 text-sm font-bold ${
                    active ? "bg-ember text-ink" : "bg-panel text-slate-300"
                  }`}
                >
                  <Icon size={15} />
                  {label}
                </Link>
              );
            })}
          </div>
        )}
      </header>
      <main>{children}</main>
    </div>
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
