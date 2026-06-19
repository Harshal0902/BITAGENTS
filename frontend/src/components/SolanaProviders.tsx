"use client";

import { ConnectionProvider, WalletProvider } from "@solana/wallet-adapter-react";
import { WalletModalProvider } from "@solana/wallet-adapter-react-ui";
import { PhantomWalletAdapter } from "@solana/wallet-adapter-phantom";
import { useEffect, useMemo, useState, type ComponentType, type ReactNode } from "react";
import { getClientSolanaRpcEndpoint } from "@/lib/solana/config";

type ConnectionProviderProps = { endpoint: string; children: ReactNode };
type WalletProviderProps = { wallets: PhantomWalletAdapter[]; autoConnect?: boolean; children: ReactNode };
type WalletModalProviderProps = { children: ReactNode };

const WalletConnectionProvider = ConnectionProvider as unknown as ComponentType<ConnectionProviderProps>;
const WalletRootProvider = WalletProvider as unknown as ComponentType<WalletProviderProps>;
const WalletModalRootProvider = WalletModalProvider as unknown as ComponentType<WalletModalProviderProps>;

export function SolanaProviders({ children }: { children: ReactNode }) {
  const [endpoint, setEndpoint] = useState<string | null>(null);
  const wallets = useMemo(() => [new PhantomWalletAdapter()], []);

  useEffect(() => {
    setEndpoint(getClientSolanaRpcEndpoint(window.location.origin));
  }, []);

  if (!endpoint) {
    return <>{children}</>;
  }

  return (
    <WalletConnectionProvider endpoint={endpoint}>
      <WalletRootProvider wallets={wallets} autoConnect>
        <WalletModalRootProvider>{children}</WalletModalRootProvider>
      </WalletRootProvider>
    </WalletConnectionProvider>
  );
}
