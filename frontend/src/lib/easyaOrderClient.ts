import { explorerUrlForSignature } from "@/lib/dcaActionResults";

export type EasyaOrderSummary = {
  id: string;
  order_type: "limit" | "threshold" | "market" | string;
  recurring?: boolean;
  pair: string;
  input_token: string;
  output_token: string;
  input_mint?: string;
  output_mint?: string;
  amount_input: number;
  limit_price_usd?: number | null;
  limit_market_cap_usd?: number | null;
  stop_price_usd?: number | null;
  stop_market_cap_usd?: number | null;
  condition_mode?: string | null;
  slippage_bps?: number;
  status: string;
  executions?: number;
  max_executions?: number | null;
  total_spent?: number;
  check_interval_seconds?: number;
  last_checked_at?: string | null;
  last_filled_at?: string | null;
  platform_fee?: number | null;
  output_amount?: number | null;
  signature?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  filled_at?: string | null;
  cancelled_at?: string | null;
  current_price_usd?: number | null;
  current_market_cap_usd?: number | null;
  trigger_summary?: string | null;
  stop_summary?: string | null;
};

export type EasyaOrdersResponse = {
  user_wallet: string;
  count: number;
  orders: EasyaOrderSummary[];
};

function authHeaders(authToken: string): HeadersInit {
  return { Authorization: `Bearer ${authToken}` };
}

export async function fetchEasyaOrders(
  authToken: string,
  activeOnly = false
): Promise<EasyaOrdersResponse | null> {
  try {
    const params = activeOnly ? "?active_only=true" : "";
    const res = await fetch(`/api/agents/kickstart-copilot/orders${params}`, {
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
            : "Failed to load orders";
      throw new Error(detail);
    }
    return data as EasyaOrdersResponse;
  } catch (err) {
    console.error("fetchEasyaOrders failed:", err);
    throw err instanceof Error ? err : new Error("Failed to load orders");
  }
}

export async function cancelEasyaOrder(
  orderId: string,
  authToken: string
): Promise<{ error?: string; status?: string }> {
  const res = await fetch(`/api/agents/kickstart-copilot/orders/${encodeURIComponent(orderId)}/cancel`, {
    method: "POST",
    headers: authHeaders(authToken),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return { error: typeof data.detail === "string" ? data.detail : data.error ?? "Cancel failed" };
  }
  return data;
}

export async function updateEasyaLimitOrder(
  orderId: string,
  body: {
    amount_sol?: number;
    limit_price_usd?: number | null;
    limit_market_cap_usd?: number | null;
    stop_price_usd?: number | null;
    stop_market_cap_usd?: number | null;
    slippage_bps?: number;
  },
  authToken: string
): Promise<{ error?: string; status?: string; order?: EasyaOrderSummary }> {
  const res = await fetch(`/api/agents/kickstart-copilot/orders/${encodeURIComponent(orderId)}`, {
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

export function orderExplorerUrl(signature?: string | null, cluster?: string) {
  if (!signature) return null;
  return explorerUrlForSignature(signature, cluster);
}
