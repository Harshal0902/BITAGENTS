import "./globals.css";
import "@solana/wallet-adapter-react-ui/styles.css";
import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import { SolanaProviders } from "@/components/SolanaProviders";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = {
  title: "BIT Agents",
  description: "AI agents powered by decentralized compute."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SolanaProviders>
          <Nav>{children}</Nav>
        </SolanaProviders>
        <Toaster />
      </body>
    </html>
  );
}
