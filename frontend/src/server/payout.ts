import { solToLamports } from "@bitagents/shared";
import { Connection, Keypair, PublicKey, SystemProgram, Transaction, sendAndConfirmTransaction } from "@solana/web3.js";
import bs58 from "bs58";
import { getServerSolanaRpcUrl } from "@/lib/solana/config";

function parseTreasuryKeypair(): Keypair | null {
  const secret = process.env.TREASURY_SECRET_KEY?.trim();
  if (!secret) {
    return null;
  }

  try {
    if (secret.startsWith("[")) {
      return Keypair.fromSecretKey(Uint8Array.from(JSON.parse(secret) as number[]));
    }

    return Keypair.fromSecretKey(bs58.decode(secret));
  } catch (error) {
    throw new Error(`TREASURY_SECRET_KEY could not be parsed: ${(error as Error).message}`);
  }
}

export async function sendServerPayout(toWallet: string, amountSol: number) {
  const keypair = parseTreasuryKeypair();
  if (!keypair) {
    throw new Error("TREASURY_SECRET_KEY is not configured. Use the browser payout flow or add a treasury keypair.");
  }

  const connection = new Connection(getServerSolanaRpcUrl(), "confirmed");
  const transaction = new Transaction().add(
    SystemProgram.transfer({
      fromPubkey: keypair.publicKey,
      toPubkey: new PublicKey(toWallet),
      lamports: solToLamports(amountSol)
    })
  );

  return sendAndConfirmTransaction(connection, transaction, [keypair], { commitment: "confirmed" });
}
