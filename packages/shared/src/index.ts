export const TASK_STATUSES = [
  "created",
  "paid_pending",
  "assigned",
  "computing",
  "completed",
  "paid_out",
  "failed"
] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];

export const AGENT_TYPES = [
  "wallet_watcher",
  "research",
  "benchmark"
] as const;

export type AgentType = (typeof AGENT_TYPES)[number];

export type ComputeType = "CPU" | "GPU_SIMULATED" | "GENERAL";
export type ProviderStatus = "online" | "offline";

export interface StatusEvent {
  status: TaskStatus;
  at: string;
  note?: string;
}

export interface ComputeProvider {
  id: string;
  name: string;
  walletAddress: string;
  computeType: ComputeType;
  pricePerTaskSol: number;
  status: ProviderStatus;
  createdAt: string;
  updatedAt: string;
}

export interface WalletWatcherInput {
  walletAddress: string;
}

export interface ResearchInput {
  keyword: string;
}

export interface BenchmarkInput {
  size: number;
}

export type AgentInput = WalletWatcherInput | ResearchInput | BenchmarkInput;

export interface WalletSignatureSummary {
  signature: string;
  slot: number;
  blockTime: number | null;
  err: unknown;
}

export interface WalletWatcherResult {
  type: "wallet_watcher";
  walletAddress: string;
  solBalance: number;
  tokenAccountsCount: number;
  latestSignatures: WalletSignatureSummary[];
  summary: string;
  rpcUrl: string;
  computedAt: string;
}

export interface ResearchResult {
  type: "research";
  keyword: string;
  computedAt: string;
  wordCount: number;
  uniqueTermCount: number;
  characterCount: number;
  sentimentScore: number;
  keywordHash: string;
  structuredSummary: {
    headline: string;
    marketContext: string;
    technicalAngle: string;
    risks: string[];
    nextQuestions: string[];
  };
}

export interface BenchmarkResult {
  type: "benchmark";
  size: number;
  iterations: number;
  runtimeMs: number;
  checksum: number;
  resultHash: string;
  computedAt: string;
}

export type AgentResult = WalletWatcherResult | ResearchResult | BenchmarkResult;

export interface AgentTask {
  id: string;
  type: AgentType;
  input: AgentInput;
  requesterWallet: string;
  status: TaskStatus;
  priceSol: number;
  assignedProviderId?: string;
  assignedProviderWallet?: string;
  paymentSignature?: string;
  payoutSignature?: string;
  result?: AgentResult;
  error?: string;
  createdAt: string;
  updatedAt: string;
  history: StatusEvent[];
}

export interface BitagentsDb {
  providers: ComputeProvider[];
  tasks: AgentTask[];
}

export const AGENT_LABELS: Record<AgentType, string> = {
  wallet_watcher: "Wallet Watcher Agent",
  research: "Research Agent",
  benchmark: "Compute Benchmark Agent"
};

export const STATUS_LABELS: Record<TaskStatus, string> = {
  created: "Created",
  paid_pending: "Paid pending",
  assigned: "Assigned",
  computing: "Computing",
  completed: "Completed",
  paid_out: "Paid out",
  failed: "Failed"
};

export const STATUS_ORDER: TaskStatus[] = [
  "created",
  "paid_pending",
  "assigned",
  "computing",
  "completed",
  "paid_out"
];

export const DEFAULT_TASK_PRICE_SOL = 0.01;
export const LAMPORTS_PER_SOL_NUMBER = 1_000_000_000;

export function isAgentType(value: string): value is AgentType {
  return (AGENT_TYPES as readonly string[]).includes(value);
}

export function isTaskStatus(value: string): value is TaskStatus {
  return (TASK_STATUSES as readonly string[]).includes(value);
}

export function solToLamports(sol: number): number {
  return Math.max(0, Math.round(sol * LAMPORTS_PER_SOL_NUMBER));
}

export function lamportsToSol(lamports: number): number {
  return lamports / LAMPORTS_PER_SOL_NUMBER;
}

export function makeExplorerTxUrl(signature: string, cluster = "devnet"): string {
  return `https://explorer.solana.com/tx/${signature}?cluster=${cluster}`;
}

export function shortAddress(address: string): string {
  if (address.length <= 12) {
    return address;
  }
  return `${address.slice(0, 4)}...${address.slice(-4)}`;
}

export function nowIso(): string {
  return new Date().toISOString();
}

export function taskInputLabel(task: Pick<AgentTask, "type" | "input">): string {
  if (task.type === "wallet_watcher" && "walletAddress" in task.input) {
    return task.input.walletAddress;
  }

  if (task.type === "research" && "keyword" in task.input) {
    return task.input.keyword;
  }

  if (task.type === "benchmark" && "size" in task.input) {
    return `matrix ${task.input.size}x${task.input.size}`;
  }

  return "Unknown input";
}
