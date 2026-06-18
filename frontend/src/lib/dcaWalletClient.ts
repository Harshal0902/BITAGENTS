export type TokenBalanceRow = {
  token: string;
  deposited: number;
  reserved_for_plans: number;
  spent_in_plans: number;
  available: number;
};

export type UserDepositBalances = {
  user_wallet: string;
  balances: TokenBalanceRow[];
  agent_wallet: string | null;
};

export type AgentWalletInfo = {
  agent_wallet: string | null;
  configured: boolean;
  supported_tokens: string[];
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

export async function fetchUserBalances(userWallet: string): Promise<UserDepositBalances | null> {
  try {
    const params = new URLSearchParams({ user_wallet: userWallet });
    const res = await fetch(`/api/agents/dca/wallet/balance?${params}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as UserDepositBalances;
  } catch {
    return null;
  }
}

export async function verifyDeposit(signature: string, userWallet: string) {
  const res = await fetch("/api/agents/dca/wallet/deposit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ signature, user_wallet: userWallet }),
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
