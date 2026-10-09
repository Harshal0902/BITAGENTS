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
  llm?: string;
  llm_configured?: boolean;
  llm_reachable?: boolean | null;
  llm_ping?: {
    ok?: boolean;
    error?: string;
    latency_ms?: number;
    url?: string;
    model?: string;
  } | null;
  detail?: string;
};

async function readJsonResponse(res: Response): Promise<Record<string, unknown>> {
  const text = await res.text();
  if (!text.trim()) {
    throw new Error(`Empty response from DCA agent API (${res.status})`);
  }
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    const snippet = text.trim().slice(0, 180);
    throw new Error(
      `DCA agent API returned non-JSON (${res.status}): ${snippet}`
    );
  }
}

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

export async function fetchDcaAgentHealth(pingLlm = false): Promise<DcaAgentHealth | null> {
  try {
    const params = pingLlm ? "?ping_llm=true" : "";
    const res = await fetch(`/api/agents/dca/health${params}`, { cache: "no-store" });
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

  const data = await readJsonResponse(res);
  if (!res.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : typeof data.error === "string"
          ? data.error
          : "Request failed";
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
