import bs58 from "bs58";

export type DcaAuthSession = {
  token: string;
  user_wallet: string;
  expires_at: string;
};

function storageKey(wallet: string) {
  return `dca_auth_${wallet}`;
}

export function getStoredDcaAuth(wallet: string): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(storageKey(wallet));
}

export function storeDcaAuth(wallet: string, token: string) {
  sessionStorage.setItem(storageKey(wallet), token);
}

export function clearDcaAuth(wallet: string) {
  sessionStorage.removeItem(storageKey(wallet));
}

export async function fetchAuthChallenge(userWallet: string) {
  const params = new URLSearchParams({ user_wallet: userWallet });
  const res = await fetch(`/api/agents/dca/auth/challenge?${params}`, { cache: "no-store" });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : data.error ?? "Auth challenge failed");
  }
  return data as { user_wallet: string; message: string; nonce: string; expires_at: string };
}

export async function verifyWalletAuth(body: {
  user_wallet: string;
  message: string;
  signature: string;
}): Promise<DcaAuthSession> {
  const res = await fetch("/api/agents/dca/auth/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : data.error ?? "Wallet sign-in failed");
  }
  return data as DcaAuthSession;
}

export async function fetchAuthMe(token: string) {
  const res = await fetch("/api/agents/dca/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return (await res.json()) as { user_wallet: string; expires_at: string };
}

export function encodeSignature(signature: Uint8Array) {
  return bs58.encode(signature);
}
