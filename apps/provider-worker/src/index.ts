import { AGENT_LABELS, shortAddress, type AgentTask } from "@bitagents/shared";
import { PublicKey } from "@solana/web3.js";
import dotenv from "dotenv";
import path from "node:path";
import { computeTask } from "./compute.js";

dotenv.config({ path: path.resolve(process.cwd(), "../../.env") });
dotenv.config({ path: path.resolve(process.cwd(), "../../.env.local"), override: true });
dotenv.config({ override: true });

const apiBaseUrl = (process.env.API_BASE_URL ?? "http://localhost:3000").replace(/\/$/, "");
const rpcUrl = process.env.SOLANA_RPC_URL ?? process.env.NEXT_PUBLIC_SOLANA_RPC_URL ?? "https://api.devnet.solana.com";
const pollIntervalMs = Number(process.env.POLL_INTERVAL_MS ?? 4000);
const providerWallet = normalizeProviderWallet(process.env.PROVIDER_WALLET);
let polling = false;

function normalizeProviderWallet(value: string | undefined) {
  if (!value || value.includes("REPLACE_WITH")) {
    return "";
  }

  try {
    return new PublicKey(value).toBase58();
  } catch {
    console.error(`Invalid PROVIDER_WALLET: ${value}`);
    return "";
  }
}

function hasErrorMessage(value: unknown): value is { error: string } {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as { error?: unknown }).error === "string"
  );
}

async function apiFetch<T>(pathName: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${pathName}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  const payload = (await response.json().catch(() => null)) as unknown;

  if (!response.ok) {
    const message = hasErrorMessage(payload) ? payload.error : response.statusText;
    throw new Error(message);
  }

  return payload as T;
}

async function pollOnce() {
  if (polling) return;
  if (!providerWallet) {
    console.log("Set PROVIDER_WALLET in .env.local after registering a provider wallet in the UI.");
    return;
  }

  polling = true;
  try {
    const payload = await apiFetch<{ tasks: AgentTask[] }>(`/api/worker/tasks?providerWallet=${providerWallet}`);
    if (payload.tasks.length === 0) {
      console.log(`[worker ${shortAddress(providerWallet)}] no assigned tasks`);
      return;
    }

    for (const task of payload.tasks) {
      await processTask(task);
    }
  } catch (error) {
    console.error(`[worker] poll failed: ${(error as Error).message}`);
  } finally {
    polling = false;
  }
}

async function processTask(task: AgentTask) {
  console.log(`[worker ${shortAddress(providerWallet)}] claiming ${AGENT_LABELS[task.type]} ${task.id}`);
  try {
    await apiFetch(`/api/tasks/${task.id}/claim`, {
      method: "POST",
      body: JSON.stringify({ providerWallet })
    });

    const result = await computeTask(task, rpcUrl);
    await apiFetch(`/api/tasks/${task.id}/result`, {
      method: "POST",
      body: JSON.stringify({ providerWallet, result })
    });
    console.log(`[worker ${shortAddress(providerWallet)}] completed ${task.id}`);
  } catch (error) {
    const message = (error as Error).message;
    console.error(`[worker ${shortAddress(providerWallet)}] task ${task.id} failed: ${message}`);
    await apiFetch(`/api/tasks/${task.id}/result`, {
      method: "POST",
      body: JSON.stringify({ providerWallet, error: message })
    }).catch((submitError) => {
      console.error(`[worker] could not submit failure for ${task.id}: ${(submitError as Error).message}`);
    });
  }
}

console.log("BITAGENTS provider worker starting");
console.log(`API: ${apiBaseUrl}`);
console.log(`RPC: ${rpcUrl}`);
console.log(`Provider wallet: ${providerWallet ? shortAddress(providerWallet) : "not configured"}`);

void pollOnce();
const interval = setInterval(() => void pollOnce(), Number.isFinite(pollIntervalMs) ? pollIntervalMs : 4000);

process.on("SIGINT", () => {
  clearInterval(interval);
  process.exit(0);
});

process.on("SIGTERM", () => {
  clearInterval(interval);
  process.exit(0);
});
