"use client";

import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import {
  createAssociatedTokenAccountInstruction,
  createTransferInstruction,
  getAssociatedTokenAddress,
  getAccount,
} from "@solana/spl-token";
import { LAMPORTS_PER_SOL, PublicKey, SystemProgram, Transaction } from "@solana/web3.js";
import { useCallback, useEffect, useState } from "react";
import { Panel } from "@/components/AppShell";
import { explorerUrlForSignature } from "@/lib/dcaActionResults";
import {
  DEPOSIT_TOKEN_DECIMALS,
  DEPOSIT_TOKEN_MINTS,
  fetchAgentWallet,
  fetchUserBalances,
  verifyDeposit,
  type TokenBalanceRow,
  type UserDepositBalances,
} from "@/lib/dcaWalletClient";

const DEPOSIT_TOKENS = ["SOL", "USDC"] as const;

export function DcaAgentDeposit({
  cluster,
  onBalancesChange,
}: {
  cluster?: string;
  onBalancesChange?: (balances: UserDepositBalances | null) => void;
}) {
  const { connection } = useConnection();
  const { publicKey, sendTransaction, connected } = useWallet();
  const [agentWallet, setAgentWallet] = useState<string | null>(null);
  const [balances, setBalances] = useState<TokenBalanceRow[]>([]);
  const [token, setToken] = useState<(typeof DEPOSIT_TOKENS)[number]>("USDC");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastTx, setLastTx] = useState<string | null>(null);

  const refreshBalances = useCallback(async () => {
    if (!publicKey) {
      setBalances([]);
      onBalancesChange?.(null);
      return;
    }
    const data = await fetchUserBalances(publicKey.toBase58());
    if (data) {
      setBalances(data.balances);
      onBalancesChange?.(data);
    }
  }, [publicKey, onBalancesChange]);

  useEffect(() => {
    void fetchAgentWallet().then((info) => setAgentWallet(info?.agent_wallet ?? null));
  }, []);

  useEffect(() => {
    void refreshBalances();
  }, [refreshBalances]);

  async function handleDeposit() {
    if (!publicKey || !agentWallet || !amount) return;
    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setError("Enter a valid amount");
      return;
    }

    setBusy(true);
    setError(null);
    setLastTx(null);

    try {
      const agentPk = new PublicKey(agentWallet);
      const tx = new Transaction();

      if (token === "SOL") {
        tx.add(
          SystemProgram.transfer({
            fromPubkey: publicKey,
            toPubkey: agentPk,
            lamports: Math.round(parsed * LAMPORTS_PER_SOL),
          })
        );
      } else {
        const mint = new PublicKey(DEPOSIT_TOKEN_MINTS[token]);
        const decimals = DEPOSIT_TOKEN_DECIMALS[token] ?? 6;
        const rawAmount = BigInt(Math.round(parsed * 10 ** decimals));

        const userAta = await getAssociatedTokenAddress(mint, publicKey);
        const agentAta = await getAssociatedTokenAddress(mint, agentPk);

        try {
          await getAccount(connection, agentAta);
        } catch {
          tx.add(
            createAssociatedTokenAccountInstruction(publicKey, agentAta, agentPk, mint)
          );
        }

        tx.add(createTransferInstruction(userAta, agentAta, publicKey, rawAmount));
      }

      const signature = await sendTransaction(tx, connection);
      const latest = await connection.getLatestBlockhash("confirmed");
      await connection.confirmTransaction({ signature, ...latest }, "confirmed");

      setLastTx(signature);
      await verifyDeposit(signature, publicKey.toBase58());
      await refreshBalances();
      setAmount("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deposit failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="// AI Agent wallet · deposit">
      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Deposit tokens to the AI Agent wallet on{" "}
            <span className="text-foreground">{cluster ?? "Solana"}</span>. Deposits are verified on-chain
            and credited to your balance before the agent can run DCA for you.
          </p>

          <div className="font-mono text-[11px] leading-relaxed text-muted-foreground">
            <span className="uppercase tracking-[0.16em] text-signal">Agent wallet</span>
            <div className="mt-1 break-all text-foreground">
              {agentWallet ?? "Not configured on server"}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <WalletMultiButton className="wallet-adapter-button-trigger" />
            {connected && publicKey && (
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                {publicKey.toBase58().slice(0, 4)}…{publicKey.toBase58().slice(-4)}
              </span>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-[120px_1fr_auto]">
            <select
              value={token}
              onChange={(e) => setToken(e.target.value as (typeof DEPOSIT_TOKENS)[number])}
              disabled={busy || !connected}
              className="border border-grid bg-background px-3 py-2.5 font-mono text-sm outline-none focus:border-signal disabled:opacity-50"
            >
              {DEPOSIT_TOKENS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <input
              type="number"
              min="0"
              step="any"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              disabled={busy || !connected}
              placeholder="Amount"
              className="border border-grid bg-background px-3 py-2.5 font-mono text-sm outline-none focus:border-signal disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => void handleDeposit()}
              disabled={busy || !connected || !agentWallet || !amount}
              className="bg-signal px-4 py-2.5 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy ? "Sending…" : "Deposit"}
            </button>
          </div>

          {error && (
            <div className="border border-warn/40 bg-warn/10 px-3 py-2 font-mono text-xs text-warn">
              {error}
            </div>
          )}

          {lastTx && (
            <a
              href={explorerUrlForSignature(lastTx, cluster)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex font-mono text-xs text-signal hover:underline"
            >
              Last deposit tx · {lastTx.slice(0, 8)}…{lastTx.slice(-8)} ↗
            </a>
          )}
        </div>

        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-signal">
            Your credited balance
          </div>
          {!connected ? (
            <p className="mt-3 text-sm text-muted-foreground">Connect wallet to view balance.</p>
          ) : balances.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">No verified deposits yet.</p>
          ) : (
            <div className="mt-3 space-y-2">
              {balances.map((row) => (
                <div key={row.token} className="border border-grid bg-background/60 px-3 py-2.5">
                  <div className="flex items-center justify-between font-display text-base font-bold">
                    <span>{row.token}</span>
                    <span className="text-signal tabular-nums">{row.available} avail</span>
                  </div>
                  <div className="mt-1 grid grid-cols-3 gap-2 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                    <span>dep {row.deposited}</span>
                    <span>rsv {row.reserved_for_plans}</span>
                    <span>spent {row.spent_in_plans}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
