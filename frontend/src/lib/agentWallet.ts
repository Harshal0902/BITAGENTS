import { WSOL_MINT, solToLamports } from "@bitagents/shared";
import {
  createAssociatedTokenAccountIdempotentInstruction,
  createCloseAccountInstruction,
  createTransferInstruction,
  getAccount,
  getAssociatedTokenAddress
} from "@solana/spl-token";
import {
  Connection,
  Keypair,
  PublicKey,
  SystemProgram,
  Transaction,
  VersionedTransaction
} from "@solana/web3.js";
import bs58 from "bs58";

// ---------------------------------------------------------------------------
// Client-side agent wallet.
//
// A throwaway "hot" keypair that can sign its own swaps so it can auto-buy on a
// schedule without a wallet popup each time. The secret key lives ONLY in the
// browser's localStorage — it is never sent to or stored on the server, and is
// never logged. The user funds it with a tiny amount and can sweep everything
// back to their main wallet at any time. Caps keep the at-risk amount small.
// ---------------------------------------------------------------------------

export interface AgentBotCaps {
  maxOrders: number;
  maxPerOrderSol: number;
  maxTotalSol: number;
  minIntervalSeconds: number;
}

export const AGENT_BOT_CAPS: AgentBotCaps = {
  maxOrders: 10,
  maxPerOrderSol: 0.05,
  maxTotalSol: 0.2,
  minIntervalSeconds: 60
};

// Rough headroom for the output token account rent (~0.002 SOL) plus per-swap
// network/priority fees, so the funded amount covers the whole run.
const FUNDING_HEADROOM_SOL = 0.01;

export interface ClampedAgentPlan {
  numberOfOrders: number;
  perOrderAmountUi: number;
  intervalSeconds: number;
  warnings: string[];
}

/** Clamp a parsed plan to the agent-bot safety caps (pure, unit-tested). */
export function clampAgentPlan(
  input: { numberOfOrders: number; perOrderAmountUi: number; intervalSeconds: number },
  caps: AgentBotCaps = AGENT_BOT_CAPS
): ClampedAgentPlan {
  const warnings: string[] = [];
  let numberOfOrders = Math.max(1, Math.floor(input.numberOfOrders));
  let perOrderAmountUi = input.perOrderAmountUi;
  let intervalSeconds = Math.round(input.intervalSeconds);

  if (numberOfOrders > caps.maxOrders) {
    numberOfOrders = caps.maxOrders;
    warnings.push(`Capped to ${caps.maxOrders} buys for safety.`);
  }
  if (perOrderAmountUi > caps.maxPerOrderSol) {
    perOrderAmountUi = caps.maxPerOrderSol;
    warnings.push(`Capped per-buy to ${caps.maxPerOrderSol} SOL for safety.`);
  }
  if (intervalSeconds < caps.minIntervalSeconds) {
    intervalSeconds = caps.minIntervalSeconds;
    warnings.push(`Minimum interval is ${caps.minIntervalSeconds}s; using ${caps.minIntervalSeconds}s.`);
  }
  if (perOrderAmountUi * numberOfOrders > caps.maxTotalSol) {
    numberOfOrders = Math.max(1, Math.floor(caps.maxTotalSol / perOrderAmountUi));
    warnings.push(`Total capped to ${caps.maxTotalSol} SOL — reduced to ${numberOfOrders} buys.`);
  }

  return { numberOfOrders, perOrderAmountUi, intervalSeconds, warnings };
}

/** Suggested amount to fund the agent wallet with (pure, unit-tested). */
export function estimateFundingSol(perOrderAmountUi: number, numberOfOrders: number): number {
  const total = perOrderAmountUi * numberOfOrders + FUNDING_HEADROOM_SOL;
  return Math.round(total * 1e6) / 1e6;
}

function storageKey(userAddress: string): string {
  return `bitagents.dca.agentWallet.${userAddress}`;
}

/** Load the persisted agent keypair for a user, if one exists. */
export function loadAgentKeypair(userAddress: string): Keypair | null {
  if (typeof window === "undefined") return null;
  const secret = window.localStorage.getItem(storageKey(userAddress));
  if (!secret) return null;
  try {
    return Keypair.fromSecretKey(bs58.decode(secret));
  } catch {
    return null;
  }
}

/** Return the user's agent keypair, generating + persisting one if needed. */
export function getOrCreateAgentKeypair(userAddress: string): Keypair {
  const existing = loadAgentKeypair(userAddress);
  if (existing) return existing;
  const keypair = Keypair.generate();
  if (typeof window !== "undefined") {
    window.localStorage.setItem(storageKey(userAddress), bs58.encode(keypair.secretKey));
  }
  return keypair;
}

/** Forget the agent keypair (use only after sweeping funds out). */
export function clearAgentKeypair(userAddress: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(storageKey(userAddress));
}

export async function getSolBalance(connection: Connection, publicKey: PublicKey): Promise<number> {
  const lamports = await connection.getBalance(publicKey, "confirmed");
  return lamports / 1e9;
}

/** Move SOL from the user's connected wallet into the agent wallet (user signs). */
export async function fundAgentWallet({
  connection,
  from,
  to,
  amountSol,
  sendTransaction
}: {
  connection: Connection;
  from: PublicKey;
  to: PublicKey;
  amountSol: number;
  sendTransaction: (transaction: Transaction, connection: Connection) => Promise<string>;
}): Promise<string> {
  const transaction = new Transaction().add(
    SystemProgram.transfer({ fromPubkey: from, toPubkey: to, lamports: solToLamports(amountSol) })
  );
  const signature = await sendTransaction(transaction, connection);
  const latest = await connection.getLatestBlockhash("confirmed");
  await connection.confirmTransaction({ signature, ...latest }, "confirmed");
  return signature;
}

/** Sign a Jupiter swap (base64 VersionedTransaction) with the agent key and submit it. */
export async function signAndSendSwap({
  base64,
  connection,
  keypair,
  lastValidBlockHeight
}: {
  base64: string;
  connection: Connection;
  keypair: Keypair;
  lastValidBlockHeight?: number | null;
}): Promise<string> {
  const transaction = VersionedTransaction.deserialize(Uint8Array.from(Buffer.from(base64, "base64")));
  transaction.sign([keypair]);
  const signature = await connection.sendRawTransaction(transaction.serialize(), { maxRetries: 3 });
  const blockhash = transaction.message.recentBlockhash;
  const lastValid =
    typeof lastValidBlockHeight === "number"
      ? lastValidBlockHeight
      : (await connection.getLatestBlockhash("confirmed")).lastValidBlockHeight;
  await connection.confirmTransaction({ signature, blockhash, lastValidBlockHeight: lastValid }, "confirmed");
  return signature;
}

async function sendWithKeypair(
  connection: Connection,
  transaction: Transaction,
  keypair: Keypair
): Promise<string> {
  const latest = await connection.getLatestBlockhash("confirmed");
  transaction.recentBlockhash = latest.blockhash;
  transaction.feePayer = keypair.publicKey;
  transaction.sign(keypair);
  const signature = await connection.sendRawTransaction(transaction.serialize(), { maxRetries: 3 });
  await connection.confirmTransaction({ signature, ...latest }, "confirmed");
  return signature;
}

export interface SweepResult {
  tokenSignature: string | null;
  solSignature: string | null;
  tokenAmountRaw: string | null;
}

/**
 * Return everything in the agent wallet to the user's main wallet: first the
 * bought token (transfer + close its account to reclaim rent), then the
 * remaining SOL. Both are signed by the agent key.
 */
export async function sweepAgentWallet({
  connection,
  keypair,
  destination,
  outputMint
}: {
  connection: Connection;
  keypair: Keypair;
  destination: string;
  outputMint: string;
}): Promise<SweepResult> {
  const owner = keypair.publicKey;
  const dest = new PublicKey(destination);
  const result: SweepResult = { tokenSignature: null, solSignature: null, tokenAmountRaw: null };

  if (outputMint && outputMint !== WSOL_MINT) {
    const mint = new PublicKey(outputMint);
    const agentAta = await getAssociatedTokenAddress(mint, owner);
    let amount = 0n;
    try {
      amount = (await getAccount(connection, agentAta)).amount;
    } catch {
      amount = 0n;
    }
    if (amount > 0n) {
      const destAta = await getAssociatedTokenAddress(mint, dest);
      const tx = new Transaction().add(
        createAssociatedTokenAccountIdempotentInstruction(owner, destAta, dest, mint),
        createTransferInstruction(agentAta, destAta, owner, amount),
        createCloseAccountInstruction(agentAta, dest, owner)
      );
      result.tokenSignature = await sendWithKeypair(connection, tx, keypair);
      result.tokenAmountRaw = amount.toString();
    }
  }

  const lamports = await connection.getBalance(owner, "confirmed");
  const feeBuffer = 5000;
  const sendable = lamports - feeBuffer;
  if (sendable > 0) {
    const tx = new Transaction().add(
      SystemProgram.transfer({ fromPubkey: owner, toPubkey: dest, lamports: sendable })
    );
    result.solSignature = await sendWithKeypair(connection, tx, keypair);
  }

  return result;
}
