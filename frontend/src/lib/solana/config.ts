import { WalletAdapterNetwork } from "@solana/wallet-adapter-base";
import { clusterApiUrl } from "@solana/web3.js";

function readCluster(): string {
  return (
    process.env.NEXT_PUBLIC_SOLANA_CLUSTER ??
    process.env.SOLANA_CLUSTER ??
    "mainnet-beta"
  ).trim();
}

function publicFallbackRpcUrl(cluster: string): string {
  const normalized = cluster.toLowerCase();
  if (normalized === "mainnet" || normalized === "mainnet-beta") {
    return clusterApiUrl(WalletAdapterNetwork.Mainnet);
  }
  if (normalized === "testnet") {
    return clusterApiUrl(WalletAdapterNetwork.Testnet);
  }
  return clusterApiUrl(WalletAdapterNetwork.Devnet);
}

/** Server-only RPC URL (Helius, etc.). Never bundle this into client code. */
export function getServerSolanaRpcUrl(): string {
  const fromEnv = process.env.SOLANA_RPC_URL?.trim();
  if (fromEnv) {
    return fromEnv;
  }
  return publicFallbackRpcUrl(readCluster());
}

/** Browser Connection endpoint - same-origin proxy hides the private RPC key. */
export function getClientSolanaRpcEndpoint(origin?: string): string {
  const path = "/api/solana/rpc";
  if (origin) {
    return `${origin.replace(/\/$/, "")}${path}`;
  }
  return path;
}

export function getSolanaCluster(): string {
  return readCluster();
}

/** @deprecated Prefer getServerSolanaRpcUrl (server) or getClientSolanaRpcEndpoint (client). */
export function getSolanaRpcUrl(): string {
  if (typeof window === "undefined") {
    return getServerSolanaRpcUrl();
  }
  return getClientSolanaRpcEndpoint(window.location.origin);
}

export function getWalletAdapterNetwork(): WalletAdapterNetwork {
  const cluster = readCluster().toLowerCase();
  if (cluster === "mainnet" || cluster === "mainnet-beta") {
    return WalletAdapterNetwork.Mainnet;
  }
  if (cluster === "testnet") {
    return WalletAdapterNetwork.Testnet;
  }
  return WalletAdapterNetwork.Devnet;
}

export function isMainnetCluster(cluster?: string): boolean {
  const c = (cluster ?? readCluster()).toLowerCase();
  return c === "mainnet" || c === "mainnet-beta";
}
