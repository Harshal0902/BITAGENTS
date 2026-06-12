import { solToLamports } from "@bitagents/shared";
import { PublicKey, SystemProgram, Transaction, type Connection } from "@solana/web3.js";

export function getTreasuryPublicKey(): PublicKey {
  const value = process.env.NEXT_PUBLIC_TREASURY_PUBLIC_KEY;
  if (!value || value.includes("REPLACE_WITH")) {
    throw new Error("Set NEXT_PUBLIC_TREASURY_PUBLIC_KEY in .env.local before sending devnet SOL.");
  }

  return new PublicKey(value);
}

export async function sendSolTransfer({
  connection,
  from,
  to,
  amountSol,
  sendTransaction
}: {
  connection: Connection;
  from: PublicKey;
  to: PublicKey;
  amountSol: number;
  sendTransaction: (transaction: Transaction, connection: Connection) => Promise<string>;
}) {
  const transaction = new Transaction().add(
    SystemProgram.transfer({
      fromPubkey: from,
      toPubkey: to,
      lamports: solToLamports(amountSol)
    })
  );

  const signature = await sendTransaction(transaction, connection);
  const latest = await connection.getLatestBlockhash("confirmed");
  await connection.confirmTransaction({ signature, ...latest }, "confirmed");
  return signature;
}
