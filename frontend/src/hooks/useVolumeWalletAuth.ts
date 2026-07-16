"use client";

import { useCallback, useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import bs58 from "bs58";

const STORAGE_PREFIX = "volume_auth_";

function storageKey(wallet: string) {
  return `${STORAGE_PREFIX}${wallet}`;
}

async function fetchChallenge(wallet: string) {
  const params = new URLSearchParams({ user_wallet: wallet });
  const res = await fetch(`/api/agents/volume/auth/challenge?${params}`, { cache: "no-store" });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : data.error ?? "Auth challenge failed");
  }
  return data as { message: string };
}

async function verifyAuth(body: { user_wallet: string; message: string; signature: string }) {
  const res = await fetch("/api/agents/volume/auth/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : data.error ?? "Wallet sign-in failed");
  }
  return data as { token: string; user_wallet: string };
}

async function fetchMe(token: string) {
  const res = await fetch("/api/agents/volume/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return (await res.json()) as { user_wallet: string };
}

export function useVolumeWalletAuth() {
  const { publicKey, signMessage, connected } = useWallet();
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wallet = publicKey?.toBase58() ?? null;

  const signIn = useCallback(async () => {
    if (!wallet || !signMessage) {
      setToken(null);
      setError("Wallet must support message signing.");
      return null;
    }

    setBusy(true);
    setError(null);

    try {
      const cached = sessionStorage.getItem(storageKey(wallet));
      if (cached) {
        const me = await fetchMe(cached);
        if (me?.user_wallet === wallet) {
          setToken(cached);
          return cached;
        }
        sessionStorage.removeItem(storageKey(wallet));
      }

      const challenge = await fetchChallenge(wallet);
      const signatureBytes = await signMessage(new TextEncoder().encode(challenge.message));
      const session = await verifyAuth({
        user_wallet: wallet,
        message: challenge.message,
        signature: bs58.encode(signatureBytes),
      });

      sessionStorage.setItem(storageKey(wallet), session.token);
      setToken(session.token);
      return session.token;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Wallet sign-in failed";
      setError(message);
      setToken(null);
      return null;
    } finally {
      setBusy(false);
    }
  }, [wallet, signMessage]);

  useEffect(() => {
    if (!connected || !wallet) {
      setToken(null);
      setError(null);
      return;
    }
    void signIn();
  }, [connected, wallet, signIn]);

  return {
    wallet,
    token,
    busy,
    error,
    signIn,
    authHeaders: token ? { Authorization: `Bearer ${token}` } : {},
    isAuthenticated: Boolean(token),
  };
}
