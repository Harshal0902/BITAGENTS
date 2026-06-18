import { WalletAdapterNetwork } from "@solana/wallet-adapter-base";
import { clusterApiUrl } from "@solana/web3.js";

function readCluster(): string {
  return (
    process.env.NEXT_PUBLIC_SOLANA_CLUSTER ??
    process.env.SOLANA_CLUSTER ??
    "mainnet-beta"
  ).trim();
}

function readRpcUrl(cluster: string): string {
  const fromEnv =
    process.env.NEXT_PUBLIC_SOLANA_RPC_URL ??
    process.env.SOLANA_RPC_URL;

  if (fromEnv?.trim()) {
    return fromEnv.trim();
  }

  const normalized = cluster.toLowerCase();
  if (normalized === "mainnet" || normalized === "mainnet-beta") {
    return clusterApiUrl(WalletAdapterNetwork.Mainnet);
  }
  if (normalized === "testnet") {
    return clusterApiUrl(WalletAdapterNetwork.Testnet);
  }
  return clusterApiUrl(WalletAdapterNetwork.Devnet);
}

export function getSolanaCluster(): string {
  return readCluster();
}

export function getSolanaRpcUrl(): string {
  return readRpcUrl(readCluster());
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
