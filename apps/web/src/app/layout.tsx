import "./globals.css";
import "@solana/wallet-adapter-react-ui/styles.css";
import type { Metadata } from "next";
import { AppShell } from "@/components/AppShell";
import { SolanaProviders } from "@/components/SolanaProviders";

export const metadata: Metadata = {
  title: "BIT Agents",
  description: "AI agents powered by decentralized compute."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SolanaProviders>
          <AppShell>{children}</AppShell>
        </SolanaProviders>
      </body>
    </html>
  );
}
