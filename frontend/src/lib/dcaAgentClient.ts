import {
  mergeTransactions,
  parseActionResult,
  type ParsedTransaction,
} from "@/lib/dcaActionResults";

export type DcaAgentAction = {
  tool: string;
  args: Record<string, unknown>;
  result: string;
};

export type DcaAgentHealth = {
  status: string;
  model: string;
  cluster: string;
  rpc: string;
  wallet: string | null;
  wallet_configured: boolean;
  detail?: string;
};

export type DcaAgentChatResponse = {
  reply: string;
  session_id: string;
  actions: DcaAgentAction[];
};

export type AgentAction = {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  status: "running" | "done" | "error";
  result: string;
  error?: string;
  transactions: ParsedTransaction[];
};

export async function fetchDcaAgentHealth(): Promise<DcaAgentHealth | null> {
  try {
    const res = await fetch("/api/agents/dca/health", { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as DcaAgentHealth;
  } catch {
    return null;
  }
}

export async function sendDcaAgentMessage(
  message: string,
  authToken: string,
  sessionId?: string
): Promise<DcaAgentChatResponse> {
  const res = await fetch("/api/agents/dca/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : data.error ?? "Request failed";
    throw new Error(detail);
  }

  return data as DcaAgentChatResponse;
}

export function mapApiActions(actions: DcaAgentAction[]): AgentAction[] {
  return actions.map((action, index) => {
    const parsed = parseActionResult(action.result);
    return {
      id: `api-${Date.now()}-${index}`,
      tool: action.tool,
      args: action.args ?? {},
      status: parsed.hasError ? "error" : "done",
      result: action.result,
      error: parsed.error,
      transactions: parsed.transactions,
    };
  });
}

export type { ParsedTransaction };
