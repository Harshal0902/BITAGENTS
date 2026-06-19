"use client";

import { useCallback, useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import {
  clearDcaAuth,
  encodeSignature,
  fetchAuthChallenge,
  fetchAuthMe,
  getStoredDcaAuth,
  storeDcaAuth,
  verifyWalletAuth,
} from "@/lib/dcaAuthClient";

export function useDcaWalletAuth() {
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
      const cached = getStoredDcaAuth(wallet);
      if (cached) {
        const me = await fetchAuthMe(cached);
        if (me?.user_wallet === wallet) {
          setToken(cached);
          return cached;
        }
        clearDcaAuth(wallet);
      }

      const challenge = await fetchAuthChallenge(wallet);
      const messageBytes = new TextEncoder().encode(challenge.message);
      const signatureBytes = await signMessage(messageBytes);
      const session = await verifyWalletAuth({
        user_wallet: wallet,
        message: challenge.message,
        signature: encodeSignature(signatureBytes),
      });

      storeDcaAuth(wallet, session.token);
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

  useEffect(() => {
    if (!connected && wallet) {
      clearDcaAuth(wallet);
    }
  }, [connected, wallet]);

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
