#!/usr/bin/env node
/**
 * Create a Meteora DLMM customizable permissionless pool.
 * Usage: node create_dlmm_pool.cjs '{"tokenMint":"...","quoteMint":"...","initialPrice":1,"binStep":80,"feeBps":25}'
 *
 * CommonJS variant of create_dlmm_pool.mjs — @meteora-ag/dlmm's ESM build re-exports
 * @coral-xyz/anchor via a directory import that Node's strict ESM resolver rejects
 * (ERR_UNSUPPORTED_DIR_IMPORT). The package's CJS build (require()) does not hit this,
 * so this script uses require() throughout instead of import.
 *
 * Requires: npm install in agent/new/scripts
 */
const path = require("path");
const { Connection, Keypair, PublicKey } = require("@solana/web3.js");
const DLMM = require("@meteora-ag/dlmm").default || require("@meteora-ag/dlmm");
const bs58 = require("bs58").default || require("bs58");
const dotenv = require("dotenv");

dotenv.config({ path: path.resolve(__dirname, "../.env") });

function loadKeypair() {
  const raw = (process.env.VOLUME_AGENT_WALLET_PRIVATE_KEY || process.env.VOLUME_WALLET_PRIVATE_KEY || "").trim();
  if (!raw) throw new Error("VOLUME_AGENT_WALLET_PRIVATE_KEY is not set");
  const secret = raw.startsWith("ll_") ? raw.slice(3) : raw;
  if (secret.startsWith("[")) {
    return Keypair.fromSecretKey(Uint8Array.from(JSON.parse(secret)));
  }
  return Keypair.fromSecretKey(bs58.decode(secret));
}

async function main() {
  const payload = JSON.parse(process.argv[2] || "{}");
  const rpc = process.env.SOLANA_RPC_URL || "https://api.mainnet-beta.solana.com";
  const connection = new Connection(rpc, "confirmed");
  const wallet = loadKeypair();

  const tokenMint = new PublicKey(payload.tokenMint);
  const quoteMint = new PublicKey(payload.quoteMint || "So11111111111111111111111111111111111111112");
  const binStep = Number(payload.binStep || 80);
  const feeBps = Number(payload.feeBps || 25);
  const initialPrice = Number(payload.initialPrice || 1);

  const activeId = DLMM.getBinIdFromPrice(initialPrice, binStep, false);
  const tx = await DLMM.createCustomizablePermissionlessLbPair(
    connection,
    binStep,
    tokenMint,
    quoteMint,
    activeId,
    feeBps,
    0,
    false,
    wallet.publicKey,
    undefined,
    { cluster: "mainnet-beta" }
  );

  tx.sign(wallet);
  const sig = await connection.sendRawTransaction(tx.serialize(), { skipPreflight: true });
  await connection.confirmTransaction(sig, "confirmed");

  const poolAddress = DLMM.getLbPairPubkey(binStep, tokenMint, quoteMint, 0);
  const explorer = `https://explorer.solana.com/tx/${sig}`;
  console.log(
    JSON.stringify({
      status: "created",
      signature: sig,
      pool_address: poolAddress.toBase58(),
      explorer_url: explorer,
    })
  );
}

main().catch((err) => {
  console.error(err?.message || String(err));
  process.exit(1);
});
