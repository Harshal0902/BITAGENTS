const DCA_AGENT_URL = process.env.DCA_AGENT_URL ?? "http://127.0.0.1:8765";

function getDcaAgentBaseUrl() {
  return DCA_AGENT_URL.replace(/\/$/, "");
}

export async function proxyDcaHealth(): Promise<Response> {
  const url = `${getDcaAgentBaseUrl()}/health`;
  return fetch(url, { cache: "no-store" });
}

export async function proxyDcaChat(body: {
  message: string;
  session_id?: string;
  user_wallet?: string;
}): Promise<Response> {
  const url = `${getDcaAgentBaseUrl()}/chat`;
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function proxyDcaWalletAgent(): Promise<Response> {
  return fetch(`${getDcaAgentBaseUrl()}/wallet/agent`, { cache: "no-store" });
}

export async function proxyDcaWalletBalance(userWallet: string): Promise<Response> {
  const params = new URLSearchParams({ user_wallet: userWallet });
  return fetch(`${getDcaAgentBaseUrl()}/wallet/balance?${params}`, { cache: "no-store" });
}

export async function proxyDcaDepositVerify(body: {
  signature: string;
  user_wallet: string;
}): Promise<Response> {
  return fetch(`${getDcaAgentBaseUrl()}/wallet/deposit/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
