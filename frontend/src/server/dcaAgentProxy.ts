const DCA_AGENT_URL = process.env.DCA_AGENT_URL ?? "http://127.0.0.1:8765";
const DCA_INTERNAL_API_KEY = process.env.DCA_INTERNAL_API_KEY ?? "";

function getDcaAgentBaseUrl() {
  return DCA_AGENT_URL.replace(/\/$/, "");
}

function buildHeaders(authToken?: string, extra?: Record<string, string>): HeadersInit {
  const headers: Record<string, string> = {
    ...extra,
  };
  if (DCA_INTERNAL_API_KEY) {
    headers["X-Internal-Key"] = DCA_INTERNAL_API_KEY;
  }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }
  return headers;
}

function getAuthToken(request?: Request): string | undefined {
  if (!request) return undefined;
  const header = request.headers.get("authorization");
  if (!header?.startsWith("Bearer ")) return undefined;
  return header.slice("Bearer ".length).trim();
}

export async function proxyDcaHealth(): Promise<Response> {
  return fetch(`${getDcaAgentBaseUrl()}/health`, {
    cache: "no-store",
    headers: buildHeaders(),
  });
}

export async function proxyDcaAuthChallenge(userWallet: string): Promise<Response> {
  const params = new URLSearchParams({ user_wallet: userWallet });
  return fetch(`${getDcaAgentBaseUrl()}/auth/challenge?${params}`, {
    cache: "no-store",
    headers: buildHeaders(),
  });
}

export async function proxyDcaAuthVerify(body: {
  user_wallet: string;
  message: string;
  signature: string;
}): Promise<Response> {
  return fetch(`${getDcaAgentBaseUrl()}/auth/verify`, {
    method: "POST",
    headers: buildHeaders(undefined, { "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
}

export async function proxyDcaAuthMe(authToken: string): Promise<Response> {
  return fetch(`${getDcaAgentBaseUrl()}/auth/me`, {
    cache: "no-store",
    headers: buildHeaders(authToken),
  });
}

export async function proxyDcaChat(
  body: { message: string; session_id?: string },
  authToken: string
): Promise<Response> {
  return fetch(`${getDcaAgentBaseUrl()}/chat`, {
    method: "POST",
    headers: buildHeaders(authToken, { "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
}

export async function proxyDcaWalletAgent(): Promise<Response> {
  return fetch(`${getDcaAgentBaseUrl()}/wallet/agent`, {
    cache: "no-store",
    headers: buildHeaders(),
  });
}

export async function proxyDcaResolveToken(query: string): Promise<Response> {
  const params = new URLSearchParams({ query });
  return fetch(`${getDcaAgentBaseUrl()}/tokens/resolve?${params}`, {
    cache: "no-store",
    headers: buildHeaders(),
  });
}

export async function proxyDcaWalletBalance(authToken: string): Promise<Response> {
  return fetch(`${getDcaAgentBaseUrl()}/wallet/balance`, {
    cache: "no-store",
    headers: buildHeaders(authToken),
  });
}

export async function proxyDcaDepositVerify(
  body: { signature: string },
  authToken: string
): Promise<Response> {
  return fetch(`${getDcaAgentBaseUrl()}/wallet/deposit/verify`, {
    method: "POST",
    headers: buildHeaders(authToken, { "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
}

export async function proxyDcaWithdraw(
  body: { token: string; amount: number },
  authToken: string
): Promise<Response> {
  return fetch(`${getDcaAgentBaseUrl()}/wallet/withdraw`, {
    method: "POST",
    headers: buildHeaders(authToken, { "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
}

export { getAuthToken };
