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

export function mapHedgeFundActions(actions: HedgeFundChatResponse["actions"]): AgentAction[] {
  return mapApiActions(actions);
}
