export type TokenBalanceRow = {
  token: string;
  deposited: number;
  acquired_from_dca?: number;
  withdrawn?: number;
  reserved_for_plans: number;
  spent_in_plans: number;
  available: number;
  withdrawable?: number;
};

export type UserDepositBalances = {
  user_wallet: string;
  balances: TokenBalanceRow[];
  agent_wallet: string | null;
};

export type AgentWalletInfo = {
  agent_wallet: string | null;
  configured: boolean;
  any_spl_token?: boolean;
  common_tokens?: string[];
  /** @deprecated use common_tokens */
  supported_tokens?: string[];
};

export type ResolvedToken = {
  symbol: string;
  mint: string;
  decimals: number;
  name?: string;
};

export type DepositRecord = {
  id: string;
  user_wallet: string;
  signature: string;
  token: string;
  amount: number;
  verified_at: string;
  explorer_url?: string;
};

export const DEPOSIT_TOKEN_DECIMALS: Record<string, number> = {
  SOL: 9,
  USDC: 6,
  USDT: 6,
  JUP: 6,
  BONK: 5,
};

export const DEPOSIT_TOKEN_MINTS: Record<string, string> = {
  SOL: "So11111111111111111111111111111111111111112",
  USDC: "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
  USDT: "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
  JUP: "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
};

export async function fetchAgentWallet(): Promise<AgentWalletInfo | null> {
  try {
    const res = await fetch("/api/agents/dca/wallet/agent", { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as AgentWalletInfo;
  } catch {
    return null;
  }
}

export async function resolveDepositToken(query: string): Promise<ResolvedToken> {
  const params = new URLSearchParams({ query: query.trim() });
  const res = await fetch(`/api/agents/dca/tokens/resolve?${params}`, { cache: "no-store" });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(typeof data.error === "string" ? data.error : "Unknown token");
  }
  return data as ResolvedToken;
}

export async function fetchUserBalances(authToken: string): Promise<UserDepositBalances | null> {
  try {
    const res = await fetch("/api/agents/dca/wallet/balance", {
      cache: "no-store",
      headers: { Authorization: `Bearer ${authToken}` },
    });
    const data = await res.json();
    if (!res.ok) {
      const detail = typeof data.error === "string" ? data.error : "Failed to load balances";
      throw new Error(detail);
    }
    return data as UserDepositBalances;
  } catch (err) {
    console.error("fetchUserBalances failed:", err);
    return null;
  }
}

export async function verifyDeposit(signature: string, authToken: string) {
  const res = await fetch("/api/agents/dca/wallet/deposit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify({ signature }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(typeof data.error === "string" ? data.error : "Deposit verification failed");
  }
  return data as {
    status: string;
    deposits?: DepositRecord[];
    balances?: UserDepositBalances;
  };
}

export async function withdrawTokens(token: string, amount: number, authToken: string) {
  const res = await fetch("/api/agents/dca/wallet/withdraw", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify({ token, amount }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(typeof data.error === "string" ? data.error : "Withdrawal failed");
  }
  return data as {
    status: string;
    signature?: string;
    explorer_url?: string;
    balances?: UserDepositBalances;
  };
}
