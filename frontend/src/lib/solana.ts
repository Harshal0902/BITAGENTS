import { solToLamports } from "@bitagents/shared";
import {
  PublicKey,
  SystemProgram,
  Transaction,
  VersionedTransaction,
  type Connection
} from "@solana/web3.js";

export function toPublicKey(address: string): PublicKey {
  if (!address || address.includes("REPLACE")) {
    throw new Error("Treasury wallet is not configured. Set TREASURY_WALLET in your environment.");
  }
  return new PublicKey(address);
}

// SOL transfer used for the legacy devnet task-fee flow. The wallet adapter
// connection follows the selected network (see SolanaProviders); this helper is
// only invoked from the archived devnet payment path.
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
}): Promise<string> {
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

// Jupiter Recurring returns an unsigned base64 VersionedTransaction. The user's
// wallet signs it locally (no custody, no private key leaves the wallet) and we
// return the signed transaction as base64 for the /execute call.
export async function signBase64Transaction({
  base64,
  signTransaction
}: {
  base64: string;
  signTransaction: <T extends Transaction | VersionedTransaction>(transaction: T) => Promise<T>;
}): Promise<string> {
  const bytes = Uint8Array.from(Buffer.from(base64, "base64"));
  const transaction = VersionedTransaction.deserialize(bytes);
  const signed = await signTransaction(transaction);
  return Buffer.from(signed.serialize()).toString("base64");
}
