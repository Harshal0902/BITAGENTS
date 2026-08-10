import { mapApiActions, type AgentAction } from "@/lib/dcaAgentClient";

export type HedgeFundChatResponse = {
  reply: string;
  session_id: string;
  actions: { tool: string; args: Record<string, unknown>; result: string }[];
};

export type HedgeFundHealth = {
  status: string;
  agent: string;
  model: string;
  fee_model?: string;
  management_fee_annual_pct?: number;
  performance_fee_pct?: number;
  pricing?: string;
  auth_required: boolean;
  paper_trading?: boolean;
  monitor_interval_seconds?: number;
};

export type HedgeFundFeeStructure = {
  name: string;
  management_fee_annual_pct: number;
  performance_fee_pct: number;
  traditional_2_20: { management_pct: number; performance_pct: number };
  description: string;
  example_100k_12mo: {
    management_fee_usd: number;
    performance_fee_usd: number;
    total_fees_usd: number;
    net_profit_after_fees_usd: number;
  };
};

export type PaperPosition = {
  id?: string;
  symbol: string;
  side?: string;
  units: number;
  avg_entry_usd?: number;
  mark_price_usd?: number;
  market_value_usd?: number;
  unrealized_pnl_usd?: number;
  strategy_id?: string;
};

export type PaperStrategy = {
  id: string;
  name: string;
  mode: string;
  status: string;
  symbols: string[];
  horizon_days?: number;
  horizon_label?: string;
  rules?: {
    take_profit_pct?: number;
    stop_loss_pct?: number;
    notes?: string;
    objective?: string;
    horizon_days?: number;
  };
  created_by?: string;
  updated_at?: string;
};

export type PaperDecision = {
  id?: string;
  strategy_id?: string;
  symbol?: string;
  action?: string;
  rationale?: string;
  created_at?: string;
  signals?: Record<string, unknown>[];
  decision_graph?: Record<string, unknown>;
};

export type PaperTrade = {
  id?: string;
  strategy_id?: string;
  symbol?: string;
  side?: string;
  notional_usd?: number;
  price_usd?: number;
  created_at?: string;
  reason?: string;
};

export type StrategyBlock = {
  strategy: PaperStrategy;
  positions: PaperPosition[];
  sleeve_value_usd?: number;
  trades: PaperTrade[];
  decisions: PaperDecision[];
  symbols: string[];
  horizon_days?: number;
  horizon_label?: string;
};

export type PaperDashboard = {
  mode: string;
  monitor_interval_seconds: number;
  last_market_refresh_at?: string | null;
  governance?: string;
  llm_required?: boolean;
  portfolio: {
    cash_usd?: number;
    equity_usd?: number;
    pnl_usd?: number;
    pnl_pct?: number;
    positions?: PaperPosition[];
    portfolio?: Record<string, unknown>;
  };
  strategies: PaperStrategy[];
  by_strategy?: StrategyBlock[];
  overlapping_assets?: Record<string, string[]>;
  decisions: PaperDecision[];
  trades: PaperTrade[];
  backtests?: Record<string, unknown>[];
  market?: { symbol: string; price_usd?: number; change_24h_pct?: number }[];
  news?: { symbol?: string; title?: string; publisher?: string }[];
};

async function authFetch(path: string, authToken: string, init?: RequestInit) {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail =
      typeof data.detail === "string" ? data.detail : data.error ?? "Request failed";
    throw new Error(detail);
  }
  return data;
}

export async function fetchHedgeFundHealth(): Promise<HedgeFundHealth | null> {
  try {
    const res = await fetch("/api/agents/hedge-fund/health", { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as HedgeFundHealth;
  } catch {
    return null;
  }
}

export async function fetchHedgeFundFees(): Promise<HedgeFundFeeStructure | null> {
  try {
    const res = await fetch("/api/agents/hedge-fund/fees", { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as HedgeFundFeeStructure;
  } catch {
    return null;
  }
}

export async function sendHedgeFundMessage(
  message: string,
  authToken: string,
  sessionId?: string,
  history?: { role: "user" | "assistant"; content: string }[]
): Promise<HedgeFundChatResponse> {
  const res = await fetch("/api/agents/hedge-fund/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify({ message, session_id: sessionId, history }),
  });

  const data = await res.json();
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : data.error ?? "Request failed";
    throw new Error(detail);
  }

  return data as HedgeFundChatResponse;
}

export async function fetchPaperDashboard(authToken: string): Promise<PaperDashboard> {
  return (await authFetch("/api/agents/hedge-fund/paper/dashboard", authToken)) as PaperDashboard;
}

export async function createPaperStrategy(
  authToken: string,
  body: {
    tokens?: string[];
    name?: string;
    mode?: string;
    take_profit_pct?: number;
    stop_loss_pct?: number;
    capital_usd?: number;
    notes?: string;
    horizon_days?: number;
  }
) {
  return authFetch("/api/agents/hedge-fund/paper/strategies", authToken, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updatePaperStrategy(
  authToken: string,
  strategyId: string,
  body: {
    take_profit_pct?: number;
    stop_loss_pct?: number;
    tokens?: string[];
    name?: string;
    status?: string;
    notes?: string;
  }
) {
  return authFetch(`/api/agents/hedge-fund/paper/strategies/${encodeURIComponent(strategyId)}`, authToken, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function runPaperMonitor(authToken: string, force = false) {
  const qs = force ? "?force=true" : "";
  return authFetch(`/api/agents/hedge-fund/paper/monitor${qs}`, authToken, { method: "POST" });
}

export async function runPaperBacktest(
  authToken: string,
  body: { period?: string; strategy_id?: string; tokens?: string[]; capital_usd?: number }
) {
  return authFetch("/api/agents/hedge-fund/paper/backtest", authToken, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function mapHedgeFundActions(actions: HedgeFundChatResponse["actions"]): AgentAction[] {
  return mapApiActions(actions);
}
