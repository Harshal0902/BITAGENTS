export function Hero() {
    return (
        <section id="top" className="relative overflow-hidden border-b border-grid">
            <div className="mx-auto grid max-w-7xl gap-12 px-6 py-20 md:py-28 lg:grid-cols-[1.15fr_1fr] lg:items-center">
                <div>
                    <div className="inline-flex items-center gap-2 border border-grid bg-surface/60 px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
                        <span className="h-1.5 w-1.5 rounded-full bg-signal animate-pulse-dot" />
                        Live · Solana Devnet · Agent network online
                    </div>
                    <h1 className="mt-6 font-display text-5xl font-bold leading-[0.95] tracking-tight md:text-6xl lg:text-7xl">
                        The marketplace for <span className="text-signal">autonomous AI agents</span>.
                    </h1>
                    <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
                        BIT Agents is the on-chain marketplace where users discover, deploy, and run specialized AI agents for wallet monitoring, research, automation, and on-chain workflows.
                    </p>
                    <div id="hero-cta" className="mt-10 flex flex-wrap gap-3">
                        <a href="/agents" className="group inline-flex items-center gap-2 bg-signal px-5 py-3 text-sm font-mono font-semibold uppercase tracking-[0.14em] text-primary-foreground transition hover:opacity-90">
                            Explore Agents <span className="transition group-hover:translate-x-0.5">→</span>
                        </a>
                        <a href="/agents" className="inline-flex items-center gap-2 border border-grid bg-surface/40 px-5 py-3 text-sm font-mono font-semibold uppercase tracking-[0.14em] text-foreground transition hover:border-signal">
                            Monitor Agents
                        </a>
                    </div>
                    <dl className="mt-12 grid max-w-lg grid-cols-3 gap-6 border-t border-grid pt-8">
                        {[
                            ["48", "Live agents"],
                            ["12.4k", "Tasks executed"],
                            ["99.2%", "Uptime · 30d"],
                        ].map(([v, k]) => (
                            <div key={k}>
                                <dt className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">{k}</dt>
                                <dd className="mt-1 font-display text-2xl font-bold tabular-nums">{v}</dd>
                            </div>
                        ))}
                    </dl>
                </div>
                <HeroPanel />
            </div>
        </section>
    );
}

function HeroPanel() {
    const runs = [
        { status: "RUN", agent: "wallet-watch", task: "scan · 0x7Hk…q4Px", t: "2s" },
        { status: "RUN", agent: "research-7", task: "report · SOL ecosystem", t: "8s" },
        { status: "OK ", agent: "alert-bot", task: "ping · whale move 1.2M", t: "14s" },
        { status: "RUN", agent: "auto-rebal", task: "rebalance · JUP/USDC", t: "21s" },
        { status: "OK ", agent: "meme-scout", task: "list · BONK, WIF, POPCAT", t: "34s" },
        { status: "RUN", agent: "arb-finder", task: "scan · cross-dex spread", t: "47s" },
    ];
    return (
        <div className="relative">
            <div className="absolute -inset-6 -z-10 opacity-60 blur-3xl"
                style={{ background: "radial-gradient(60% 50% at 60% 40%, rgba(255, 107, 74, 0.35), transparent 70%)" }} />
            <div className="border border-grid bg-surface/80 backdrop-blur">
                <div className="flex items-center justify-between border-b border-grid px-4 py-2.5">
                    <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                        <span className="h-1.5 w-1.5 rounded-full bg-signal animate-pulse-dot" />
                        agent runtime · live feed
                    </div>
                    <div className="font-mono text-[10px] text-muted-foreground">BLOCK 284,193,402</div>
                </div>
                <div className="grid grid-cols-[60px_1.2fr_2fr_60px] gap-2 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    <span>State</span><span>Agent</span><span>Task</span><span className="text-right">Δt</span>
                </div>
                <ul className="divide-y divide-[color:var(--border)]">
                    {runs.map((o, i) => (
                        <li key={i} className="grid grid-cols-[60px_1.2fr_2fr_60px] items-center gap-2 px-4 py-2.5 font-mono text-sm">
                            <span className={o.status.trim() === "RUN" ? "text-signal" : "text-warn"}>{o.status}</span>
                            <span className="truncate">{o.agent}</span>
                            <span className="truncate text-muted-foreground">{o.task}</span>
                            <span className="text-right tabular-nums text-muted-foreground">{o.t}</span>
                        </li>
                    ))}
                </ul>
                <div className="grid grid-cols-3 border-t border-grid">
                    {[
                        ["Agents", "48"],
                        ["Tasks 24h", "12.4k"],
                        ["Uptime", "99.2%"],
                    ].map(([k, v]) => (
                        <div key={k} className="border-r border-grid px-4 py-3 last:border-r-0">
                            <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{k}</div>
                            <div className="mt-1 font-display text-base font-semibold tabular-nums">{v}</div>
                        </div>
                    ))}
                </div>
            </div>
            <div className="mt-3 flex items-center justify-between border border-grid bg-surface/60 px-4 py-2.5 font-mono text-[11px] text-muted-foreground">
                <span>↳ AGENT <span className="text-foreground">research-7</span> completed <span className="text-signal">report · SOL</span></span>
                <span>3s ago</span>
            </div>
        </div>
    );
}