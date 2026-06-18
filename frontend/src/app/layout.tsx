import "./globals.css";
import "@solana/wallet-adapter-react-ui/styles.css";
import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import { SolanaProviders } from "@/components/SolanaProviders";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = {
  title: "BIT Agents",
  description: "The on-chain marketplace for autonomous AI agents."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground">
        <SolanaProviders>
          <Nav>{children}</Nav>
        </SolanaProviders>
        <Toaster />
      </body>
    </html>
  );
}
