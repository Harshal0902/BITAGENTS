import {
  lamportsToSol,
  nowIso,
  type AgentResult,
  type AgentTask,
  type BenchmarkResult,
  type ResearchResult,
  type WalletWatcherResult
} from "@bitagents/shared";
import { Connection, PublicKey } from "@solana/web3.js";
import { createHash } from "node:crypto";
import { performance } from "node:perf_hooks";

const TOKEN_PROGRAM_ID = new PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA");

export async function computeTask(task: AgentTask, rpcUrl: string): Promise<AgentResult> {
  if (task.type === "wallet_watcher") {
    return computeWalletWatcher(task, rpcUrl);
  }

  if (task.type === "research") {
    return computeResearch(task);
  }

  return computeBenchmark(task);
}

async function computeWalletWatcher(task: AgentTask, rpcUrl: string): Promise<WalletWatcherResult> {
  if (!("walletAddress" in task.input)) {
    throw new Error("wallet watcher task is missing walletAddress input.");
  }

  const connection = new Connection(rpcUrl, "confirmed");
  const wallet = new PublicKey(task.input.walletAddress);
  const [lamports, tokenAccounts, signatures] = await Promise.all([
    connection.getBalance(wallet, "confirmed"),
    connection.getParsedTokenAccountsByOwner(wallet, { programId: TOKEN_PROGRAM_ID }, "confirmed"),
    connection.getSignaturesForAddress(wallet, { limit: 5 }, "confirmed")
  ]);

  const solBalance = lamportsToSol(lamports);
  const summary = `Wallet ${wallet.toBase58()} holds ${solBalance.toFixed(5)} SOL on devnet, has ${tokenAccounts.value.length} SPL token account(s), and ${signatures.length} recent signature(s) were returned.`;

  return {
    type: "wallet_watcher",
    walletAddress: wallet.toBase58(),
    solBalance,
    tokenAccountsCount: tokenAccounts.value.length,
    latestSignatures: signatures.map((item) => ({
      signature: item.signature,
      slot: item.slot,
      blockTime: item.blockTime ?? null,
      err: item.err
    })),
    summary,
    rpcUrl,
    computedAt: nowIso()
  };
}

function computeResearch(task: AgentTask): ResearchResult {
  if (!("keyword" in task.input)) {
    throw new Error("research task is missing keyword input.");
  }

  const keyword = task.input.keyword.trim();
  const lower = keyword.toLowerCase();
  const words = lower.match(/[a-z0-9]+/g) ?? [];
  const unique = Array.from(new Set(words));
  const hash = createHash("sha256").update(lower).digest("hex");
  const positiveTerms = new Set(["agent", "compute", "solana", "automation", "market", "research", "protocol", "wallet"]);
  const riskTerms = new Set(["risk", "hack", "bug", "centralized", "latency", "unknown", "volatile"]);
  const sentimentScore = words.reduce((score, word) => {
    if (positiveTerms.has(word)) return score + 1;
    if (riskTerms.has(word)) return score - 1;
    return score;
  }, 0);

  const primaryTerms = unique.slice(0, 5);
  const topic = primaryTerms.length > 0 ? primaryTerms.join(", ") : "general agent marketplace";

  return {
    type: "research",
    keyword,
    computedAt: nowIso(),
    wordCount: words.length,
    uniqueTermCount: unique.length,
    characterCount: keyword.length,
    sentimentScore,
    keywordHash: hash,
    structuredSummary: {
      headline: `${keyword} analysis report`,
      marketContext: `The query clusters around ${topic}. The deterministic hash prefix ${hash.slice(0, 10)} is used to make repeated runs auditable.`,
      technicalAngle: `BITAGENTS can route this topic into wallet monitoring, research synthesis, or compute benchmark agents depending on user intent and provider capability.`,
      risks: [
        "Research output is local and deterministic in the MVP, so it should be treated as a structured demo report.",
        "Future versions should attach external sources, agent reputation, and signed provider attestations.",
        `Keyword complexity score: ${Math.min(100, keyword.length + unique.length * 4)}.`
      ],
      nextQuestions: [
        `Which providers specialize in ${primaryTerms[0] ?? "this topic"}?`,
        "What token incentives improve result quality?",
        "Which agent outputs should be verifiable on-chain?"
      ]
    }
  };
}

function computeBenchmark(task: AgentTask): BenchmarkResult {
  if (!("size" in task.input)) {
    throw new Error("benchmark task is missing size input.");
  }

  const size = Math.min(220, Math.max(12, Math.floor(task.input.size)));
  const iterations = Math.max(1, Math.floor(80_000 / (size * size)));
  const a = new Float64Array(size * size);
  const b = new Float64Array(size * size);
  const c = new Float64Array(size * size);

  for (let i = 0; i < a.length; i += 1) {
    a[i] = ((i * 17 + size) % 101) / 101;
    b[i] = ((i * 31 + size * 3) % 97) / 97;
  }

  const start = performance.now();
  for (let iteration = 0; iteration < iterations; iteration += 1) {
    for (let row = 0; row < size; row += 1) {
      const rowOffset = row * size;
      for (let col = 0; col < size; col += 1) {
        let sum = 0;
        for (let k = 0; k < size; k += 1) {
          sum += a[rowOffset + k] * b[k * size + col];
        }
        c[rowOffset + col] = sum + iteration * 0.000001;
      }
    }
  }
  const runtimeMs = performance.now() - start;

  let checksum = 0;
  const step = Math.max(1, Math.floor(c.length / 64));
  for (let i = 0; i < c.length; i += step) {
    checksum += c[i];
  }
  const resultHash = createHash("sha256")
    .update(`${size}:${iterations}:${checksum.toFixed(12)}:${c[0]?.toFixed(12)}:${c[c.length - 1]?.toFixed(12)}`)
    .digest("hex");

  return {
    type: "benchmark",
    size,
    iterations,
    runtimeMs,
    checksum,
    resultHash,
    computedAt: nowIso()
  };
}
