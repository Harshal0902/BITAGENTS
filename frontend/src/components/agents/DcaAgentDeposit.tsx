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
  resolveDepositToken,
  verifyDeposit,
  withdrawTokens,
  type ResolvedToken,
  type TokenBalanceRow,
  type UserDepositBalances,
} from "@/lib/dcaWalletClient";

const PRESET_TOKENS = ["SOL", "USDC", "JUP"] as const;
type PresetToken = (typeof PRESET_TOKENS)[number];

export function DcaAgentDeposit({
  cluster,
  authToken,
  onBalancesChange,
}: {
  cluster?: string;
  authToken?: string | null;
  onBalancesChange?: (balances: UserDepositBalances | null) => void;
}) {
  const { connection } = useConnection();
  const { publicKey, sendTransaction, connected } = useWallet();
  const [agentWallet, setAgentWallet] = useState<string | null>(null);
  const [anySplToken, setAnySplToken] = useState(true);
  const [balances, setBalances] = useState<TokenBalanceRow[]>([]);
  const [token, setToken] = useState<PresetToken | "custom">("SOL");
  const [customMint, setCustomMint] = useState("");
  const [resolvedCustom, setResolvedCustom] = useState<ResolvedToken | null>(null);
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [withdrawBusy, setWithdrawBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastTx, setLastTx] = useState<string | null>(null);
  const [withdrawToken, setWithdrawToken] = useState("");
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [lastWithdrawTx, setLastWithdrawTx] = useState<string | null>(null);

  const refreshBalances = useCallback(async () => {
    if (!publicKey || !authToken) {
      setBalances([]);
      onBalancesChange?.(null);
      return;
    }
    const data = await fetchUserBalances(authToken);
    if (data) {
      setBalances(data.balances);
      onBalancesChange?.(data);
    }
  }, [publicKey, authToken, onBalancesChange]);

  useEffect(() => {
    void fetchAgentWallet().then((info) => {
      setAgentWallet(info?.agent_wallet ?? null);
      setAnySplToken(info?.any_spl_token ?? true);
    });
  }, []);

  useEffect(() => {
    void refreshBalances();
  }, [refreshBalances]);

  useEffect(() => {
    if (withdrawToken) return;
    const first = balances.find((row) => (row.withdrawable ?? 0) > 0);
    if (first) setWithdrawToken(first.token);
  }, [balances, withdrawToken]);

  useEffect(() => {
    if (token !== "custom" || customMint.trim().length < 32) {
      setResolvedCustom(null);
      return;
    }

    const handle = window.setTimeout(() => {
      void resolveDepositToken(customMint.trim())
        .then(setResolvedCustom)
        .catch((err) => {
          setResolvedCustom(null);
          setError(err instanceof Error ? err.message : "Unknown token");
        });
    }, 400);

    return () => window.clearTimeout(handle);
  }, [token, customMint]);

  async function handleDeposit() {
    if (!publicKey || !agentWallet || !amount || !authToken) return;
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
        let mintAddress: string;
        let decimals: number;

        if (token === "custom") {
          if (!resolvedCustom) {
            setError("Enter a valid SPL token mint address");
            return;
          }
          mintAddress = resolvedCustom.mint;
          decimals = resolvedCustom.decimals;
        } else {
          mintAddress = DEPOSIT_TOKEN_MINTS[token];
          decimals = DEPOSIT_TOKEN_DECIMALS[token] ?? 6;
        }

        const mint = new PublicKey(mintAddress);
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
      const verified = await verifyDeposit(signature, authToken);
      if (verified.balances?.balances) {
        setBalances(verified.balances.balances);
        onBalancesChange?.(verified.balances);
      } else {
        await refreshBalances();
      }
      setAmount("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deposit failed");
    } finally {
      setBusy(false);
    }
  }

  const selectedWithdrawRow = balances.find((row) => row.token === withdrawToken);
  const withdrawableAmount = selectedWithdrawRow?.withdrawable ?? 0;

  async function handleWithdraw() {
    if (!publicKey || !authToken || !withdrawToken || !withdrawAmount) return;
    const parsed = Number(withdrawAmount);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setError("Enter a valid withdraw amount");
      return;
    }
    if (parsed > withdrawableAmount + 1e-12) {
      setError(`Maximum withdrawable ${withdrawToken}: ${withdrawableAmount}`);
      return;
    }

    setWithdrawBusy(true);
    setError(null);
    setLastWithdrawTx(null);

    try {
      const result = await withdrawTokens(withdrawToken, parsed, authToken);
      if (result.signature) setLastWithdrawTx(result.signature);
      await refreshBalances();
      setWithdrawAmount("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Withdrawal failed");
    } finally {
      setWithdrawBusy(false);
    }
  }

  return (
    <Panel title="// AI Agent wallet · deposit & withdraw">
      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Deposit any SPL token to the AI Agent wallet on{" "}
            <span className="text-foreground">{cluster ?? "Solana"}</span>. Deposits are verified
            on-chain and credited to your balance before the agent can run DCA for you.
          </p>

          <div className="font-mono text-[11px] leading-relaxed text-muted-foreground">
            <span className="uppercase tracking-[0.16em] text-signal">Agent wallet</span>
            <div className="mt-1 break-all text-foreground">
              {agentWallet ?? "Not configured on server"}
            </div>
            {anySplToken && (
              <div className="mt-2 text-[10px] uppercase tracking-[0.14em] text-signal">
                Any SPL token · symbol or mint address
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <WalletMultiButton className="wallet-adapter-button-trigger" />
            {connected && publicKey && (
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                {publicKey.toBase58().slice(0, 4)}…{publicKey.toBase58().slice(-4)}
              </span>
            )}
          </div>

          <div className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-[140px_1fr_auto]">
              <select
                value={token}
                onChange={(e) => setToken(e.target.value as PresetToken | "custom")}
                disabled={busy || !connected}
                className="border border-grid bg-background px-3 py-2.5 font-mono text-sm outline-none focus:border-signal disabled:opacity-50"
              >
                {PRESET_TOKENS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
                <option value="custom">Custom mint</option>
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

            {token === "custom" && (
              <div className="space-y-2">
                <input
                  type="text"
                  value={customMint}
                  onChange={(e) => setCustomMint(e.target.value)}
                  disabled={busy || !connected}
                  placeholder="Token mint address (any SPL token)"
                  className="w-full border border-grid bg-background px-3 py-2.5 font-mono text-sm outline-none focus:border-signal disabled:opacity-50"
                />
                {resolvedCustom && (
                  <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                    Resolved: {resolvedCustom.symbol} · {resolvedCustom.decimals} decimals
                  </div>
                )}
              </div>
            )}
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

          <div className="border-t border-grid pt-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-signal">
              Withdraw to your wallet
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              Withdraw unused deposits and tokens bought by your DCA plans. Amounts reserved for
              active plans cannot be withdrawn.
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-[140px_1fr_auto]">
              <select
                value={withdrawToken}
                onChange={(e) => setWithdrawToken(e.target.value)}
                disabled={withdrawBusy || !connected || balances.length === 0}
                className="border border-grid bg-background px-3 py-2.5 font-mono text-sm outline-none focus:border-signal disabled:opacity-50"
              >
                {balances.length === 0 ? (
                  <option value="">No balance</option>
                ) : (
                  balances.map((row) => (
                    <option key={row.token} value={row.token}>
                      {row.token} ({row.withdrawable ?? 0})
                    </option>
                  ))
                )}
              </select>
              <input
                type="number"
                min="0"
                step="any"
                value={withdrawAmount}
                onChange={(e) => setWithdrawAmount(e.target.value)}
                disabled={withdrawBusy || !connected || !withdrawToken}
                placeholder={`Max ${withdrawableAmount}`}
                className="border border-grid bg-background px-3 py-2.5 font-mono text-sm outline-none focus:border-signal disabled:opacity-50"
              />
              <button
                type="button"
                onClick={() => void handleWithdraw()}
                disabled={
                  withdrawBusy ||
                  !connected ||
                  !authToken ||
                  !withdrawToken ||
                  !withdrawAmount ||
                  withdrawableAmount <= 0
                }
                className="border border-signal px-4 py-2.5 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-signal transition hover:bg-signal/10 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {withdrawBusy ? "Sending…" : "Withdraw"}
              </button>
            </div>
            {withdrawToken && withdrawableAmount > 0 && (
              <button
                type="button"
                onClick={() => setWithdrawAmount(String(withdrawableAmount))}
                disabled={withdrawBusy || !connected}
                className="mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground hover:text-signal"
              >
                Use max · {withdrawableAmount} {withdrawToken}
              </button>
            )}
            {lastWithdrawTx && (
              <a
                href={explorerUrlForSignature(lastWithdrawTx, cluster)}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex font-mono text-xs text-signal hover:underline"
              >
                Last withdraw tx · {lastWithdrawTx.slice(0, 8)}…{lastWithdrawTx.slice(-8)} ↗
              </a>
            )}
          </div>
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
                  <div className="mt-1 flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                    <span>withdraw {row.withdrawable ?? 0}</span>
                    {(row.acquired_from_dca ?? 0) > 0 && (
                      <span className="text-signal">dca +{row.acquired_from_dca}</span>
                    )}
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
