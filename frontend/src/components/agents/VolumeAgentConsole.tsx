"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Panel } from "@/components/AppShell";
import { VolumeAgentDeposit } from "@/components/agents/VolumeAgentDeposit";
import { VolumeCampaignPanel } from "@/components/agents/VolumeCampaignPanel";
import { VOLUME_AGENT, VOLUME_EXAMPLE_PROMPTS } from "@/lib/volumeAgentSimulation";
import {
  fetchVolumeAgentHealth,
  mapVolumeApiActions,
  sendVolumeAgentMessage,
  type AgentAction,
  type VolumeAgentHealth,
} from "@/lib/volumeAgentClient";
import { checkVolumePool, createVolumeCampaign } from "@/lib/volumePlanClient";
import { useVolumeWalletAuth } from "@/hooks/useVolumeWalletAuth";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { useWallet } from "@solana/wallet-adapter-react";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

function formatReply(text: string) {
  return text.split("\n").map((line, i) => {
    const parts = line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
    return (
      <span key={i} className="block">
        {parts.map((part, j) => {
          if (part.startsWith("**") && part.endsWith("**")) {
            return (
              <strong key={j} className="font-semibold text-foreground">
                {part.slice(2, -2)}
              </strong>
            );
          }
          if (part.startsWith("`") && part.endsWith("`")) {
            return (
              <code key={j} className="rounded bg-surface-2 px-1 py-0.5 text-signal">
                {part.slice(1, -1)}
              </code>
            );
          }
          return <span key={j}>{part}</span>;
        })}
      </span>
    );
  });
}

export function VolumeAgentConsole() {
  const { connected } = useWallet();
  const { wallet, token, busy: authBusy, error: authError, isAuthenticated } = useVolumeWalletAuth();
  const [health, setHealth] = useState<VolumeAgentHealth | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [chatBusy, setChatBusy] = useState(false);
  const [actions, setActions] = useState<AgentAction[]>([]);
  const [refreshTick, setRefreshTick] = useState(0);

  const [baseToken, setBaseToken] = useState("");
  const [tradeAmount, setTradeAmount] = useState("0.01");
  const [interval, setInterval] = useState("30 seconds");
  const [maxExecutions, setMaxExecutions] = useState("10");
  const [campaignBusy, setCampaignBusy] = useState(false);
  const [campaignError, setCampaignError] = useState<string | null>(null);
  const [campaignSuccess, setCampaignSuccess] = useState<string | null>(null);
  const [poolStatus, setPoolStatus] = useState<string | null>(null);
  const [poolCheckBusy, setPoolCheckBusy] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void fetchVolumeAgentHealth().then(setHealth);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, actions]);

  async function handleSend(message: string) {
    if (!token || !message.trim()) return;
    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: "user", content: message.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setChatBusy(true);
    setActions([]);

    try {
      const res = await sendVolumeAgentMessage(message.trim(), token, sessionId);
      setSessionId(res.session_id);
      setMessages((prev) => [
        ...prev,
        { id: `a-${Date.now()}`, role: "assistant", content: res.reply },
      ]);
      setActions(mapVolumeApiActions(res.actions ?? []));
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: "assistant",
          content: err instanceof Error ? err.message : "Request failed",
        },
      ]);
    } finally {
      setChatBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void handleSend(input);
  }

  async function checkPool() {
    const mint = baseToken.trim();
    if (mint.length < 32) {
      setPoolStatus("Enter a valid base token mint to check pool.");
      return;
    }
    setPoolCheckBusy(true);
    setPoolStatus(null);
    try {
      const result = await checkVolumePool(mint);
      setPoolStatus(
        result.pool_exists
          ? `DLMM pool exists · ${result.pool_address ?? "address pending"}`
          : `No pool found · creation cost ~${result.pool_creation_cost_sol ?? health?.pool_creation_cost_sol ?? VOLUME_AGENT.poolCreationCostSol} SOL`
      );
    } catch (err) {
      setPoolStatus(err instanceof Error ? err.message : "Pool check failed");
    } finally {
      setPoolCheckBusy(false);
    }
  }

  async function handleCreateCampaign(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setCampaignBusy(true);
    setCampaignError(null);
    setCampaignSuccess(null);

    try {
      const result = await createVolumeCampaign(
        {
          base_token: baseToken.trim(),
          quote_token: "SOL",
          trade_amount: Number(tradeAmount),
          interval: interval.trim(),
          max_executions: Number(maxExecutions),
        },
        token
      );
      setCampaignSuccess(result.message ?? `Campaign ${result.campaign.id} created.`);
      setRefreshTick((t) => t + 1);
    } catch (err) {
      setCampaignError(err instanceof Error ? err.message : "Campaign creation failed");
    } finally {
      setCampaignBusy(false);
    }
  }

  const poolCost = health?.pool_creation_cost_sol ?? VOLUME_AGENT.poolCreationCostSol;
  const cluster = health?.cluster;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Panel title="Create volume campaign">
          <form className="space-y-4" onSubmit={(e) => void handleCreateCampaign(e)}>
            <p className="text-sm text-muted-foreground">
              1. Sign in with your wallet · 2. Deposit token + SOL · 3. Set pair, trade size, frequency, and
              number of transactions. The agent checks for a Meteora DLMM pool, creates one if needed (~
              {poolCost} SOL), or reuses an existing pool. Platform fee is{" "}
              <strong className="text-foreground">{VOLUME_AGENT.platformFeeLabel}</strong> on every leg.
            </p>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1 font-mono text-[11px] sm:col-span-2">
                <span className="text-muted-foreground">Base token (symbol or mint)</span>
                <input
                  className="w-full border border-grid bg-background px-3 py-2 text-foreground"
                  value={baseToken}
                  onChange={(e) => setBaseToken(e.target.value)}
                  placeholder="Your token mint or symbol"
                  required
                />
              </label>
              <label className="space-y-1 font-mono text-[11px]">
                <span className="text-muted-foreground">SOL per trade leg</span>
                <input
                  className="w-full border border-grid bg-background px-3 py-2 text-foreground"
                  value={tradeAmount}
                  onChange={(e) => setTradeAmount(e.target.value)}
                  inputMode="decimal"
                  required
                />
              </label>
              <label className="space-y-1 font-mono text-[11px]">
                <span className="text-muted-foreground">Interval</span>
                <input
                  className="w-full border border-grid bg-background px-3 py-2 text-foreground"
                  value={interval}
                  onChange={(e) => setInterval(e.target.value)}
                  placeholder="30 seconds"
                  required
                />
              </label>
              <label className="space-y-1 font-mono text-[11px]">
                <span className="text-muted-foreground">Number of transactions (cycles)</span>
                <input
                  className="w-full border border-grid bg-background px-3 py-2 text-foreground"
                  value={maxExecutions}
                  onChange={(e) => setMaxExecutions(e.target.value)}
                  inputMode="numeric"
                  required
                />
              </label>
              <div className="flex items-end">
                <button
                  type="button"
                  onClick={() => void checkPool()}
                  disabled={poolCheckBusy}
                  className="w-full border border-grid px-3 py-2 font-mono text-[11px] uppercase"
                >
                  {poolCheckBusy ? "Checking…" : "Check DLMM pool"}
                </button>
              </div>
            </div>

            {poolStatus && <p className="font-mono text-[11px] text-muted-foreground">{poolStatus}</p>}
            {campaignError && <p className="font-mono text-[11px] text-warn">{campaignError}</p>}
            {campaignSuccess && <p className="font-mono text-[11px] text-signal">{campaignSuccess}</p>}

            <button
              type="submit"
              disabled={!isAuthenticated || campaignBusy}
              className="w-full border border-signal bg-signal/10 px-4 py-2 font-mono text-[11px] uppercase tracking-wider text-signal disabled:opacity-50"
            >
              {campaignBusy ? "Creating infrastructure…" : "Create campaign"}
            </button>
          </form>
        </Panel>

        <Panel title="Volume Agent chat">
          <div className="mb-4 flex flex-wrap gap-2">
            {VOLUME_EXAMPLE_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => void handleSend(prompt)}
                disabled={!isAuthenticated || chatBusy}
                className="border border-grid px-2 py-1 font-mono text-[10px] text-muted-foreground hover:text-foreground disabled:opacity-50"
              >
                {prompt}
              </button>
            ))}
          </div>

          <div className="mb-4 max-h-[360px] space-y-3 overflow-y-auto border border-grid bg-background/40 p-3">
            {messages.length === 0 && (
              <p className="font-mono text-[11px] text-muted-foreground">
                Ask about campaigns, pool infrastructure, or fees.
              </p>
            )}
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`font-mono text-[12px] ${
                  msg.role === "user" ? "text-foreground" : "text-muted-foreground"
                }`}
              >
                <span className="mr-2 text-[10px] uppercase tracking-wider text-signal">
                  {msg.role === "user" ? "You" : "Agent"}
                </span>
                {formatReply(msg.content)}
              </div>
            ))}
            {chatBusy && <p className="font-mono text-[11px] text-muted-foreground">Working…</p>}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={onSubmit} className="flex gap-2">
            <input
              className="min-w-0 flex-1 border border-grid bg-background px-3 py-2 font-mono text-[12px]"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={isAuthenticated ? "Message Volume Agent…" : "Connect wallet to chat"}
              disabled={!isAuthenticated || chatBusy}
            />
            <button
              type="submit"
              disabled={!isAuthenticated || chatBusy || !input.trim()}
              className="border border-signal px-4 py-2 font-mono text-[11px] uppercase text-signal disabled:opacity-50"
            >
              Send
            </button>
          </form>

          {actions.length > 0 && (
            <div className="mt-4 space-y-2">
              {actions.map((act) => (
                <div key={act.id} className="border border-grid p-2 font-mono text-[10px]">
                  <span className="text-signal">{act.tool}</span> · {act.status}
                </div>
              ))}
            </div>
          )}
        </Panel>

        {token && (
          <VolumeCampaignPanel
            authToken={token}
            cluster={cluster}
            refreshTick={refreshTick}
            onCampaignChange={() => setRefreshTick((t) => t + 1)}
          />
        )}
      </div>

      <div className="space-y-6">
        <Panel title="Wallet & status">
          <div className="space-y-3 font-mono text-[11px]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-muted-foreground">Wallet</span>
              {!connected ? (
                <WalletMultiButton className="!h-8" />
              ) : (
                <code className="break-all text-foreground">{wallet}</code>
              )}
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Sign-in</span>
              <span className={isAuthenticated ? "text-signal" : "text-warn"}>
                {authBusy ? "Signing…" : isAuthenticated ? "Authenticated" : "Required"}
              </span>
            </div>
            {authError && <p className="text-warn">{authError}</p>}
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Cluster</span>
              <span>{cluster ?? "—"}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Agent wallet</span>
              <span>{health?.trading_wallet_configured ? "Configured" : "Not set"}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Pool creation</span>
              <span>~{poolCost} SOL</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Platform fee</span>
              <span>{VOLUME_AGENT.platformFeeLabel}</span>
            </div>
            <Link href="/agents" className="inline-block text-signal">
              ← Marketplace
            </Link>
          </div>
        </Panel>

        <VolumeAgentDeposit
          cluster={cluster}
          authToken={token}
          refreshTick={refreshTick}
          poolCreationCostSol={poolCost}
          onBalancesChange={() => setRefreshTick((t) => t + 1)}
        />
      </div>
    </div>
  );
}
