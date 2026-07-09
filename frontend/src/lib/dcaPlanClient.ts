import { explorerUrlForSignature } from "@/lib/dcaActionResults";

export type DcaPlanSummary = {
  id: string;
  name: string;
  pair: string;
  input_mint?: string;
  output_mint?: string;
  amount_per_buy: number;
  interval: string;
  status: string;
  executions: number;
  max_executions?: number | null;
  total_budget?: number | null;
  slippage_bps?: number;
  spent: number;
  next_execution_at?: string | null;
};

export type DcaPlansResponse = {
  plans: DcaPlanSummary[];
  count: number;
  user_wallet: string;
};

export type DcaExecutionRow = {
  plan_id: string;
  plan_name: string;
  pair: string;
  input_mint?: string;
  output_mint?: string;
  at?: string;
  amount?: number;
  platform_fee?: number;
  total_cost?: number;
  input_token?: string;
  output_token?: string;
  dry_run?: boolean;
  status?: string;
  signature?: string;
  explorer_url?: string;
  output_amount?: number | string;
  error?: string;
};

export type DcaExecutionsResponse = {
  user_wallet: string;
  executions: DcaExecutionRow[];
  count: number;
};

export type DcaPlanExecutionsResponse = {
  plan_id: string;
  name: string;
  executions_count: number;
  spent_so_far: number;
  executions: Array<{
    at?: string;
    amount?: number;
    platform_fee?: number;
    total_cost?: number;
    input_token?: string;
    output_token?: string;
    dry_run?: boolean;
    result?: {
      status?: string;
      signature?: string;
      explorer_url?: string;
      output_amount?: number | string;
      error?: string;
    };
    error?: string;
  }>;
};

export type LedgerEntry = {
  id: string;
  token: string;
  mint: string;
  amount: number;
  direction: "deposit" | "spend" | "acquire" | "withdraw" | string;
  reference_type?: string;
  signature?: string;
  explorer_url?: string;
  verified_at?: string;
  status?: string;
};

export type LedgerResponse = {
  user_wallet: string;
  entries: LedgerEntry[];
  count: number;
};

export type PlatformMetrics = {
  total_plans: number;
  active_plans: number;
  total_users: number;
  total_executions: number;
  successful_swaps: number;
  failed_swaps: number;
  total_volume_sol: number;
  total_deposits: number;
  total_withdrawals: number;
  executions_24h: number;
  updated_at?: string;
};

function authHeaders(authToken: string): HeadersInit {
  return { Authorization: `Bearer ${authToken}` };
}

export async function fetchDcaPlans(
  authToken: string,
  activeOnly = false
): Promise<DcaPlansResponse | null> {
  try {
    const params = activeOnly ? "?active_only=true" : "";
    const res = await fetch(`/api/agents/dca/plans${params}`, {
      cache: "no-store",
      headers: authHeaders(authToken),
    });
    if (!res.ok) return null;
    return (await res.json()) as DcaPlansResponse;
  } catch {
    return null;
  }
}

export async function updateDcaPlanStatus(
  planId: string,
  action: "pause" | "resume" | "cancel",
  authToken: string
): Promise<{ error?: string; status?: string }> {
  const res = await fetch(`/api/agents/dca/plans/${encodeURIComponent(planId)}/status`, {
    method: "POST",
    headers: {
      ...authHeaders(authToken),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ action }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return { error: typeof data.detail === "string" ? data.detail : data.error ?? "Update failed" };
  }
  return data;
}

export async function updateDcaPlan(
  planId: string,
  body: {
    amount_per_buy?: number;
    interval?: string;
    max_executions?: number | null;
    total_budget?: number | null;
    slippage_bps?: number;
  },
  authToken: string
): Promise<{ error?: string; status?: string; plan?: DcaPlanSummary }> {
  const res = await fetch(`/api/agents/dca/plans/${encodeURIComponent(planId)}`, {
    method: "PATCH",
    headers: {
      ...authHeaders(authToken),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return { error: typeof data.detail === "string" ? data.detail : data.error ?? "Update failed" };
  }
  return data;
}

export async function fetchDcaPlanExecutions(
  planId: string,
  authToken: string
): Promise<DcaPlanExecutionsResponse | null> {
  try {
    const res = await fetch(`/api/agents/dca/plans/${encodeURIComponent(planId)}/executions`, {
      cache: "no-store",
      headers: authHeaders(authToken),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail =
        typeof data.error === "string"
          ? data.error
          : typeof data.detail === "string"
            ? data.detail
            : "Failed to load plan history";
      throw new Error(detail);
    }
    return data as DcaPlanExecutionsResponse;
  } catch (err) {
    console.error("fetchDcaPlanExecutions failed:", err);
    throw err instanceof Error ? err : new Error("Failed to load plan history");
  }
}

export function mapPlanExecutionRow(
  plan: DcaPlanSummary,
  entry: DcaPlanExecutionsResponse["executions"][number]
): DcaExecutionRow {
  const result = entry.result ?? {};
  return {
    plan_id: plan.id,
    plan_name: plan.name,
    pair: plan.pair,
    input_mint: plan.input_mint,
    output_mint: plan.output_mint,
    at: entry.at,
    amount: entry.amount,
    platform_fee: entry.platform_fee,
    total_cost: entry.total_cost,
    input_token: entry.input_token,
    output_token: entry.output_token,
    dry_run: entry.dry_run,
    status: result.status,
    signature: result.signature,
    explorer_url: result.explorer_url,
    output_amount: result.output_amount,
    error: result.error ?? entry.error,
  };
}

export async function fetchDcaExecutions(
  authToken: string,
  limit = 100
): Promise<DcaExecutionsResponse | null> {
  try {
    const res = await fetch(`/api/agents/dca/wallet/dca-executions?limit=${limit}`, {
      cache: "no-store",
      headers: authHeaders(authToken),
    });
    if (!res.ok) return null;
    return (await res.json()) as DcaExecutionsResponse;
  } catch {
    return null;
  }
}

export async function fetchWalletLedger(
  authToken: string,
  limit = 50
): Promise<LedgerResponse | null> {
  try {
    const res = await fetch(`/api/agents/dca/wallet/ledger?limit=${limit}`, {
      cache: "no-store",
      headers: authHeaders(authToken),
    });
    if (!res.ok) return null;
    return (await res.json()) as LedgerResponse;
  } catch {
    return null;
  }
}

export async function fetchPlatformMetrics(): Promise<PlatformMetrics | null> {
  try {
    const res = await fetch("/api/agents/dca/metrics", { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as PlatformMetrics;
  } catch {
    return null;
  }
}

export function formatMetricNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return String(value);
}

export function formatVolumeSol(value: number): string {
  if (value <= 0) return "0 SOL";
  if (value >= 1_000) return `${(value / 1_000).toFixed(2)}k SOL`;
  if (value >= 100) return `${value.toFixed(1)} SOL`;
  if (value >= 1) return `${value.toFixed(2)} SOL`;
  return `${value.toFixed(4)} SOL`;
}

export function executionExplorerUrl(row: DcaExecutionRow, cluster?: string): string | null {
  if (row.explorer_url) return row.explorer_url;
  if (row.signature) return explorerUrlForSignature(row.signature, cluster);
  return null;
}

export function ledgerDirectionLabel(direction: string): string {
  switch (direction) {
    case "deposit":
      return "Deposit";
    case "withdraw":
      return "Withdraw";
    case "spend":
      return "DCA spend";
    case "dca_fee":
      return "DCA fee (0.5%)";
    case "acquire":
      return "DCA acquire";
    default:
      return direction;
  }
}
