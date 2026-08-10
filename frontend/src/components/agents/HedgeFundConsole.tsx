"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Panel } from "@/components/AppShell";
import {
  createPaperStrategy,
  fetchHedgeFundHealth,
  fetchPaperDashboard,
  mapHedgeFundActions,
  runPaperBacktest,
  runPaperMonitor,
  sendHedgeFundMessage,
  updatePaperStrategy,
  type HedgeFundHealth,
  type PaperDashboard,
} from "@/lib/hedgeFundClient";
import { HEDGE_FUND } from "@/lib/hedgeFundConfig";
import { useKickstartWalletAuth } from "@/hooks/useKickstartWalletAuth";
import type { AgentAction } from "@/lib/dcaAgentClient";
import { useWallet } from "@solana/wallet-adapter-react";

type ChatMessage = { id: string; role: "user" | "assistant"; content: string };

function formatReply(text: string) {
  return text.split("\n").map((line, i) => (
    <p key={i} className={line.trim() === "" ? "h-2" : undefined}>
      {line}
    </p>
  ));
}

function money(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function HedgeFundConsole() {
  const { publicKey } = useWallet();
  const { token, busy: authBusy, error: authError, isAuthenticated } = useKickstartWalletAuth();
  const [health, setHealth] = useState<HedgeFundHealth | null>(null);
  const [agentOnline, setAgentOnline] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actions, setActions] = useState<AgentAction[]>([]);
  const [dashboard, setDashboard] = useState<PaperDashboard | null>(null);
  const [dashBusy, setDashBusy] = useState(false);
  const [symbolInput, setSymbolInput] = useState("");
  const [tpInput, setTpInput] = useState("15");
  const [slInput, setSlInput] = useState("8");
  const [horizonDays, setHorizonDays] = useState("90");
  const [agentPick, setAgentPick] = useState(true);
  const [editTp, setEditTp] = useState<Record<string, string>>({});
  const [editSl, setEditSl] = useState<Record<string, string>>({});
  const [lastBacktest, setLastBacktest] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const refreshDashboard = useCallback(async () => {
    if (!token) return;
    setDashBusy(true);
    try {
      const dash = await fetchPaperDashboard(token);
      setDashboard(dash);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load paper dashboard");
    } finally {
      setDashBusy(false);
    }
  }, [token]);

  useEffect(() => {
    void fetchHedgeFundHealth().then((h) => {
      setHealth(h);
      setAgentOnline(h?.status === "ok");
    });
  }, []);

  useEffect(() => {
    if (token) void refreshDashboard();
  }, [token, refreshDashboard]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function runCommand(text: string) {
    if (!token || !text.trim()) return;
    setBusy(true);
    setError(null);
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: "user", content: text.trim() }]);
    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const res = await sendHedgeFundMessage(text.trim(), token, sessionId, history);
      setSessionId(res.session_id);
      setMessages((prev) => [...prev, { id: `a-${Date.now()}`, role: "assistant", content: res.reply }]);
      setActions(mapHedgeFundActions(res.actions));
      void refreshDashboard();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Request failed";
      setError(msg);
      setMessages((prev) => [...prev, { id: `e-${Date.now()}`, role: "assistant", content: msg }]);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    void runCommand(text);
  }

  async function onCreateStrategy() {
    if (!token) return;
    setDashBusy(true);
    setError(null);
    try {
      const tokens = agentPick
        ? undefined
        : symbolInput
            .split(/[,\s]+/)
            .map((s) => s.trim().toUpperCase())
            .filter(Boolean);
      await createPaperStrategy(token, {
        tokens,
        mode: agentPick ? "agent" : "user",
        take_profit_pct: Number(tpInput) || 15,
        stop_loss_pct: Number(slInput) || 8,
        horizon_days: Number(horizonDays) || 90,
        notes: agentPick
          ? `Agent pick for ${horizonDays}d horizon`
          : `User-selected symbols · horizon ${horizonDays}d`,
      });
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create strategy failed");
    } finally {
      setDashBusy(false);
    }
  }

  async function onSaveRules(strategyId: string) {
    if (!token) return;
    setDashBusy(true);
    try {
      await updatePaperStrategy(token, strategyId, {
        take_profit_pct: Number(editTp[strategyId] ?? 15),
        stop_loss_pct: Number(editSl[strategyId] ?? 8),
      });
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setDashBusy(false);
    }
  }

  async function onMonitor() {
    if (!token) return;
    setDashBusy(true);
    try {
      await runPaperMonitor(token, true);
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Monitor failed");
    } finally {
      setDashBusy(false);
    }
  }

  async function onBacktest(strategyId: string, period: string) {
    if (!token) return;
    setDashBusy(true);
    setLastBacktest(null);
    try {
      const res = await runPaperBacktest(token, { strategy_id: strategyId, period });
      const result = (res.result || res) as Record<string, unknown>;
      const net = result.net_pnl_pct ?? result.net_pnl_usd;
      setLastBacktest(
        `${period.toUpperCase()} · ${strategyId} · net ${typeof net === "number" ? (result.net_pnl_pct != null ? `${net}%` : money(net as number)) : "done"}`
      );
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backtest failed");
    } finally {
      setDashBusy(false);
    }
  }

  const port = dashboard?.portfolio;
  const positions = port?.positions || [];
  const hours = Math.round((health?.monitor_interval_seconds || dashboard?.monitor_interval_seconds || 14400) / 3600);

  return (
    <div className="space-y-6">
      <div className="border border-grid bg-surface/40 px-4 py-4">
        <p className="text-sm leading-relaxed text-muted-foreground">{HEDGE_FUND.description}</p>
        <p className="mt-2 font-mono text-xs text-signal">
          18-analyst · paper · monitor every {hours}h · shared quotes · fees{" "}
          {HEDGE_FUND.managementFeePct}/{HEDGE_FUND.performanceFeePct} · LLM optional ·{" "}
          <Link href="/agents/hedge-fund/pricing" className="underline hover:text-foreground">
            Pricing
          </Link>
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        <span className={`inline-flex items-center gap-2 ${agentOnline ? "text-signal" : "text-warn"}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${agentOnline ? "bg-signal animate-pulse-dot" : "bg-warn"}`} />
          {agentOnline ? "API online" : "API offline"}
        </span>
        <span>·</span>
        <span>{health?.model ?? HEDGE_FUND.model}</span>
        <span>·</span>
        <span className="text-signal">paper trading</span>
        {dashBusy && <span className="text-muted-foreground">· refreshing…</span>}
      </div>

      {error && (
        <div className="border border-warn/40 bg-warn/10 px-4 py-3 font-mono text-xs text-warn">{error}</div>
      )}
      {authError && (
        <div className="border border-warn/40 bg-warn/10 px-4 py-3 font-mono text-xs text-warn">
          Wallet sign-in: {authError}
        </div>
      )}

      {/* Paper monitor */}
      <div className="grid gap-4 lg:grid-cols-4">
        <Panel title="Paper book">
          <div className="space-y-2 font-mono text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Cash</span>
              <span>{money(port?.cash_usd)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Equity</span>
              <span>{money(port?.equity_usd)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">PnL</span>
              <span className={(port?.pnl_usd || 0) >= 0 ? "text-signal" : "text-warn"}>
                {money(port?.pnl_usd)} ({port?.pnl_pct ?? 0}%)
              </span>
            </div>
            <div className="flex gap-2 pt-2">
              <button
                type="button"
                disabled={!token || dashBusy}
                onClick={() => void refreshDashboard()}
                className="flex-1 border border-grid px-2 py-1.5 text-[10px] uppercase disabled:opacity-40"
              >
                Refresh
              </button>
              <button
                type="button"
                disabled={!token || dashBusy}
                onClick={() => void onMonitor()}
                className="flex-1 border border-signal/40 bg-signal/10 px-2 py-1.5 text-[10px] uppercase text-signal disabled:opacity-40"
              >
                Run cycle
              </button>
            </div>
          </div>
        </Panel>

        <Panel title="New strategy" className="lg:col-span-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
            <label className="flex items-center gap-2 font-mono text-xs">
              <input
                type="checkbox"
                checked={agentPick}
                onChange={(e) => setAgentPick(e.target.checked)}
                disabled={!token}
              />
              Agent picks assets for horizon
            </label>
            {!agentPick && (
              <input
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                placeholder="AAPL NVDA BTC ETH"
                className="min-w-[12rem] flex-1 border border-grid bg-background px-3 py-2 font-mono text-sm"
              />
            )}
            <div className="flex flex-wrap gap-2">
              <input
                value={horizonDays}
                onChange={(e) => setHorizonDays(e.target.value)}
                className="w-24 border border-grid bg-background px-2 py-2 font-mono text-sm"
                title="Horizon days"
                placeholder="Days"
              />
              <input
                value={tpInput}
                onChange={(e) => setTpInput(e.target.value)}
                className="w-20 border border-grid bg-background px-2 py-2 font-mono text-sm"
                title="Take profit %"
                placeholder="TP%"
              />
              <input
                value={slInput}
                onChange={(e) => setSlInput(e.target.value)}
                className="w-20 border border-grid bg-background px-2 py-2 font-mono text-sm"
                title="Stop loss %"
                placeholder="SL%"
              />
              <button
                type="button"
                disabled={!token || dashBusy || authBusy}
                onClick={() => void onCreateStrategy()}
                className="border border-signal bg-signal/10 px-4 py-2 font-mono text-xs uppercase text-signal disabled:opacity-40"
              >
                Create
              </button>
            </div>
          </div>
          <p className="mt-2 font-mono text-[10px] text-muted-foreground">
            Horizon (days) drives lookback + asset ranking. Same ticker can sit in multiple strategies.
          </p>
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Strategies">
          <div className="max-h-72 space-y-3 overflow-y-auto">
            {(dashboard?.strategies || []).length === 0 && (
              <p className="font-mono text-xs text-muted-foreground">No strategies yet — create one above or ask in chat.</p>
            )}
            {(dashboard?.strategies || []).map((s) => (
              <div key={s.id} className="border border-grid bg-surface/30 p-3 font-mono text-[11px]">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-signal">
                    {s.name} · {s.mode}/{s.status} · {s.horizon_days || s.rules?.horizon_days || "?"}d
                  </span>
                  <span className="text-muted-foreground">{s.id}</span>
                </div>
                <p className="mt-1 text-muted-foreground">{(s.symbols || []).join(", ")}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span>TP</span>
                  <input
                    className="w-14 border border-grid bg-background px-1 py-0.5"
                    value={editTp[s.id] ?? String(s.rules?.take_profit_pct ?? 15)}
                    onChange={(e) => setEditTp((prev) => ({ ...prev, [s.id]: e.target.value }))}
                  />
                  <span>SL</span>
                  <input
                    className="w-14 border border-grid bg-background px-1 py-0.5"
                    value={editSl[s.id] ?? String(s.rules?.stop_loss_pct ?? 8)}
                    onChange={(e) => setEditSl((prev) => ({ ...prev, [s.id]: e.target.value }))}
                  />
                  <button
                    type="button"
                    disabled={!token || dashBusy}
                    onClick={() => void onSaveRules(s.id)}
                    className="border border-grid px-2 py-0.5 uppercase disabled:opacity-40"
                  >
                    Save
                  </button>
                  {(["1w", "1m", "6m", "1y"] as const).map((p) => (
                    <button
                      key={p}
                      type="button"
                      disabled={!token || dashBusy}
                      onClick={() => void onBacktest(s.id, p)}
                      className="border border-signal/30 px-2 py-0.5 text-signal disabled:opacity-40"
                    >
                      BT {p}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {lastBacktest && <p className="font-mono text-[11px] text-signal">Last backtest: {lastBacktest}</p>}
          </div>
        </Panel>

        <Panel title="Overlapping assets">
          <div className="max-h-72 space-y-2 overflow-y-auto font-mono text-[11px]">
            {Object.keys(dashboard?.overlapping_assets || {}).length === 0 ? (
              <p className="text-muted-foreground">No shared tickers across strategies yet.</p>
            ) : (
              Object.entries(dashboard?.overlapping_assets || {}).map(([sym, sids]) => (
                <div key={sym} className="border-b border-grid/40 pb-1.5">
                  <span className="text-signal">{sym}</span>{" "}
                  <span className="text-muted-foreground">→ {sids.join(", ")}</span>
                </div>
              ))
            )}
          </div>
        </Panel>
      </div>

      <Panel title="By strategy — positions, trades, decisions">
        <div className="max-h-[28rem] space-y-4 overflow-y-auto">
          {(dashboard?.by_strategy || []).length === 0 && (
            <p className="font-mono text-xs text-muted-foreground">Create a strategy to see sleeves.</p>
          )}
          {(dashboard?.by_strategy || []).map((block) => {
            const s = block.strategy;
            return (
              <div key={s.id} className="border border-grid bg-surface/20 p-3 font-mono text-[11px]">
                <div className="mb-2 flex flex-wrap justify-between gap-2 text-signal">
                  <span>
                    {s.name} · sleeve {money(block.sleeve_value_usd)} · horizon{" "}
                    {block.horizon_days || s.horizon_days || "?"}d
                  </span>
                  <span className="text-muted-foreground">{s.id}</span>
                </div>
                <p className="mb-2 text-muted-foreground">Assets: {(block.symbols || []).join(", ") || "—"}</p>
                <div className="grid gap-3 md:grid-cols-3">
                  <div>
                    <div className="mb-1 text-muted-foreground">Positions</div>
                    {(block.positions || []).length === 0 && <p>—</p>}
                    {(block.positions || []).map((p) => (
                      <div key={`${s.id}-${p.symbol}`}>
                        {p.symbol} {Number(p.units).toPrecision(3)} · PnL {money(p.unrealized_pnl_usd)}
                      </div>
                    ))}
                  </div>
                  <div>
                    <div className="mb-1 text-muted-foreground">Trades</div>
                    {(block.trades || []).slice(0, 5).map((t, i) => (
                      <div key={t.id || i}>
                        {t.side} {t.symbol} {money(t.notional_usd)}
                      </div>
                    ))}
                    {(block.trades || []).length === 0 && <p>—</p>}
                  </div>
                  <div>
                    <div className="mb-1 text-muted-foreground">Decisions</div>
                    {(block.decisions || []).slice(0, 5).map((d, i) => (
                      <div key={d.id || i}>
                        {d.action} {d.symbol}
                      </div>
                    ))}
                    {(block.decisions || []).length === 0 && <p>—</p>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Positions (all)">
          <div className="max-h-72 overflow-y-auto font-mono text-[11px]">
            {positions.length === 0 ? (
              <p className="text-muted-foreground">No open positions.</p>
            ) : (
              <table className="w-full text-left">
                <thead className="text-muted-foreground">
                  <tr>
                    <th className="pb-2 font-normal">Strategy</th>
                    <th className="pb-2 font-normal">Symbol</th>
                    <th className="pb-2 font-normal">Units</th>
                    <th className="pb-2 font-normal">Entry</th>
                    <th className="pb-2 font-normal">Mark</th>
                    <th className="pb-2 font-normal">PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {(dashboard?.by_strategy || []).flatMap((b) =>
                    (b.positions || []).map((p) => (
                      <tr key={`${b.strategy.id}-${p.symbol}-${p.id}`} className="border-t border-grid/60">
                        <td className="py-1.5 text-muted-foreground">{b.strategy.id}</td>
                        <td className="py-1.5 text-signal">{p.symbol}</td>
                        <td className="py-1.5">{Number(p.units).toPrecision(4)}</td>
                        <td className="py-1.5">{money(p.avg_entry_usd)}</td>
                        <td className="py-1.5">{money(p.mark_price_usd)}</td>
                        <td className={`py-1.5 ${(p.unrealized_pnl_usd || 0) >= 0 ? "text-signal" : "text-warn"}`}>
                          {money(p.unrealized_pnl_usd)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            )}
          </div>
        </Panel>

        <Panel title="Decisions">
          <div className="max-h-72 space-y-2 overflow-y-auto font-mono text-[11px]">
            {(dashboard?.decisions || []).length === 0 && (
              <p className="text-muted-foreground">No decisions yet — run a monitor cycle.</p>
            )}
            {(dashboard?.decisions || []).slice(0, 20).map((d, i) => (
              <div key={d.id || i} className="border-b border-grid/40 pb-1.5">
                <span className="text-muted-foreground">[{d.strategy_id}]</span>{" "}
                <span className="text-signal">{d.action}</span> {d.symbol}{" "}
                <span className="text-muted-foreground">
                  {d.created_at ? String(d.created_at).slice(0, 16) : ""} — {d.rationale}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Trades">
          <div className="max-h-56 space-y-2 overflow-y-auto font-mono text-[11px]">
            {(dashboard?.trades || []).length === 0 && (
              <p className="text-muted-foreground">No paper fills yet.</p>
            )}
            {(dashboard?.trades || []).slice(0, 20).map((t, i) => (
              <div key={t.id || i} className="border-b border-grid/40 pb-1.5">
                <span className="text-muted-foreground">[{t.strategy_id}]</span>{" "}
                <span className="text-signal">{t.side}</span> {t.symbol} {money(t.notional_usd)} @ {money(t.price_usd)}{" "}
                <span className="text-muted-foreground">{t.reason}</span>
              </div>
            ))}
          </div>
        </Panel>
        <div />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title={HEDGE_FUND.name} className="lg:col-span-2">
          <div className="flex max-h-[420px] flex-col gap-4 overflow-y-auto pr-1">
            {messages.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Chat to create strategies, edit TP/SL, or run backtests. Paper only — no live orders.
              </p>
            )}
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`rounded border px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "border-grid bg-surface/60 text-foreground"
                    : "border-signal/30 bg-surface/30 text-muted-foreground"
                }`}
              >
                <div className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-signal">
                  {msg.role === "user" ? "You" : HEDGE_FUND.assistantLabel}
                </div>
                <div className="space-y-1">{formatReply(msg.content)}</div>
              </div>
            ))}
            {busy && <div className="animate-pulse font-mono text-xs text-muted-foreground">Working…</div>}
            <div ref={chatEndRef} />
          </div>

          <form onSubmit={onSubmit} className="mt-4 border-t border-grid pt-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  isAuthenticated
                    ? "e.g. Create paper strategy with BTC ETH, TP 20 SL 10"
                    : "Connect wallet to chat"
                }
                disabled={!token || busy}
                className="flex-1 border border-grid bg-background px-3 py-2 font-mono text-sm disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!token || busy || !input.trim()}
                className="border border-signal bg-signal/10 px-4 py-2 font-mono text-xs uppercase text-signal disabled:opacity-40"
              >
                Send
              </button>
            </div>
          </form>
        </Panel>

        <div className="space-y-6">
          <Panel title="Quick prompts">
            <div className="flex flex-col gap-2">
              {HEDGE_FUND.examplePrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  disabled={!token || busy}
                  onClick={() => void runCommand(prompt)}
                  className="border border-grid bg-surface/40 px-3 py-2 text-left font-mono text-xs text-muted-foreground hover:border-signal/40 disabled:opacity-40"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </Panel>

          {actions.length > 0 && (
            <Panel title="Tool activity">
              <div className="max-h-64 space-y-3 overflow-y-auto font-mono text-[11px]">
                {actions.map((action, idx) => (
                  <div key={`${action.tool}-${idx}`} className="border border-grid bg-surface/30 p-3">
                    <div className="mb-1 text-signal">{action.tool}</div>
                    <pre className="whitespace-pre-wrap break-all text-muted-foreground">
                      {action.result.slice(0, 800)}
                    </pre>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          {(dashboard?.market || []).length > 0 && (
            <Panel title="Shared market">
              <div className="space-y-1 font-mono text-[11px]">
                {(dashboard?.market || []).slice(0, 10).map((m) => (
                  <div key={m.symbol} className="flex justify-between border-b border-grid/40 py-1">
                    <span className="text-signal">{m.symbol}</span>
                    <span>
                      {money(m.price_usd)}{" "}
                      <span className={(m.change_24h_pct || 0) >= 0 ? "text-signal" : "text-warn"}>
                        {(m.change_24h_pct || 0).toFixed(2)}%
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </Panel>
          )}
        </div>
      </div>

      {!publicKey && (
        <div className="border border-grid bg-surface/40 px-4 py-3 font-mono text-xs text-muted-foreground">
          Connect your wallet to sign in.
        </div>
      )}
    </div>
  );
}
