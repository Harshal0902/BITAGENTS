#!/usr/bin/env node
/**
 * Create a Meteora DLMM customizable permissionless pool, and seed it with
 * real liquidity so it's actually tradeable (an empty pool can't fill any
 * swap — see comments below).
 *
 * Usage: node create_dlmm_pool.cjs '{"tokenMint":"...","quoteMint":"...","initialPrice":1,"binStep":80,"feeBps":25,"tokenAmount":0,"quoteAmount":0}'
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
const { StrategyType } = require("@meteora-ag/dlmm");
const { getMint, NATIVE_MINT } = require("@solana/spl-token");
const BN = require("bn.js");
const bs58 = require("bs58").default || require("bs58");
const dotenv = require("dotenv");

dotenv.config({ path: path.resolve(__dirname, "../.env") });

// How many bins on either side of the current price to spread seed liquidity
// across. Narrow = liquidity concentrated near the current price, which is
// what we want: our own volume-bot trades are small and shouldn't need to
// move far from the starting price to fill.
const SEED_BIN_RANGE = 10;

function loadKeypair() {
  const raw = (process.env.VOLUME_AGENT_WALLET_PRIVATE_KEY || process.env.VOLUME_WALLET_PRIVATE_KEY || "").trim();
  if (!raw) throw new Error("VOLUME_AGENT_WALLET_PRIVATE_KEY is not set");
  const secret = raw.startsWith("ll_") ? raw.slice(3) : raw;
  if (secret.startsWith("[")) {
    return Keypair.fromSecretKey(Uint8Array.from(JSON.parse(secret)));
  }
  return Keypair.fromSecretKey(bs58.decode(secret));
}

async function toRawAmount(connection, mint, humanAmount) {
  if (humanAmount <= 0) return new BN(0);
  const decimals = mint.equals(NATIVE_MINT)
    ? 9
    : (await getMint(connection, mint)).decimals;
  return new BN(Math.round(humanAmount * 10 ** decimals));
}

// Seeds the newly-created (or already-existing) pool with real liquidity.
// Without this, `createCustomizablePermissionlessLbPair` above only creates
// an empty pool shell — zero liquidity in every bin — which cannot fill any
// swap at all. This was the exact gap Harshal found: pool creation "succeeded"
// but nothing could actually trade against it.
async function seedLiquidity({ connection, wallet, poolAddress, tokenMint, quoteMint, tokenAmount, quoteAmount }) {
  if (tokenAmount <= 0 && quoteAmount <= 0) {
    return { status: "skipped", reason: "No seed amounts provided." };
  }

  const dlmmPool = await DLMM.create(connection, poolAddress);
  const activeBin = await dlmmPool.getActiveBin();

  const isTokenMintX = dlmmPool.tokenX.publicKey.equals(tokenMint);
  const tokenRaw = await toRawAmount(connection, tokenMint, tokenAmount);
  const quoteRaw = await toRawAmount(connection, quoteMint, quoteAmount);
  const totalXAmount = isTokenMintX ? tokenRaw : quoteRaw;
  const totalYAmount = isTokenMintX ? quoteRaw : tokenRaw;

  const positionKeypair = Keypair.generate();
  const tx = await dlmmPool.initializePositionAndAddLiquidityByStrategy({
    positionPubKey: positionKeypair.publicKey,
    user: wallet.publicKey,
    totalXAmount,
    totalYAmount,
    strategy: {
      maxBinId: activeBin.binId + SEED_BIN_RANGE,
      minBinId: activeBin.binId - SEED_BIN_RANGE,
      strategyType: StrategyType.Spot,
    },
  });

  const { blockhash } = await connection.getLatestBlockhash("confirmed");
  tx.recentBlockhash = blockhash;
  tx.feePayer = wallet.publicKey;
  tx.sign(wallet, positionKeypair);

  const sig = await connection.sendRawTransaction(tx.serialize(), { skipPreflight: true });
  const confirmation = await connection.confirmTransaction(sig, "confirmed");
  if (confirmation.value.err) {
    return {
      status: "failed",
      error: `Liquidity deposit confirmed but failed on-chain: ${JSON.stringify(confirmation.value.err)} (sig: ${sig})`,
      signature: sig,
    };
  }

  // Same "don't trust confirmTransaction alone" check as the pool-creation
  // step above — verify the position actually holds liquidity before
  // reporting success.
  const positions = await dlmmPool.getPositionsByUserAndLbPair(wallet.publicKey);
  const created = positions.userPositions.find((p) => p.publicKey.equals(positionKeypair.publicKey));
  if (!created) {
    return {
      status: "failed",
      error: `Deposit transaction confirmed but no position account exists at ${positionKeypair.publicKey.toBase58()} (sig: ${sig}).`,
      signature: sig,
    };
  }

  return {
    status: "seeded",
    signature: sig,
    explorer_url: `https://explorer.solana.com/tx/${sig}`,
    position_address: positionKeypair.publicKey.toBase58(),
    token_amount: tokenAmount,
    quote_amount: quoteAmount,
  };
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
  const tokenAmount = Number(payload.tokenAmount || 0);
  const quoteAmount = Number(payload.quoteAmount || 0);

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
  const confirmation = await connection.confirmTransaction(sig, "confirmed");

  // confirmTransaction resolves once the tx is INCLUDED in a block — that is
  // NOT the same as succeeding. A reverted instruction still gets "confirmed"
  // with a non-null value.err. Without this check, the script would report
  // "created" with a signature and a pool address even when the on-chain
  // program call actually failed — which is exactly what was happening.
  if (confirmation.value.err) {
    throw new Error(
      `Transaction confirmed but failed on-chain: ${JSON.stringify(confirmation.value.err)} (sig: ${sig})`
    );
  }

  const poolAddress = DLMM.getLbPairPubkey(binStep, tokenMint, quoteMint, 0);

  // getLbPairPubkey only computes the expected PDA deterministically — it does
  // not confirm the account actually exists on-chain. Verify before reporting
  // success, since a failed tx (caught above) would otherwise still pair with
  // a plausible-looking but nonexistent address.
  const accountInfo = await connection.getAccountInfo(poolAddress);
  if (!accountInfo) {
    throw new Error(
      `Transaction confirmed successfully but no pool account exists at the expected address ${poolAddress.toBase58()} (sig: ${sig}). The pool was not actually created.`
    );
  }

  const explorer = `https://explorer.solana.com/tx/${sig}`;

  let liquidity = { status: "skipped", reason: "No seed amounts provided." };
  try {
    liquidity = await seedLiquidity({
      connection,
      wallet,
      poolAddress,
      tokenMint,
      quoteMint,
      tokenAmount,
      quoteAmount,
    });
  } catch (err) {
    liquidity = { status: "failed", error: err?.message || String(err) };
  }

  console.log(
    JSON.stringify({
      status: "created",
      signature: sig,
      pool_address: poolAddress.toBase58(),
      explorer_url: explorer,
      liquidity,
    })
  );
}

main().catch((err) => {
  console.error(err?.message || String(err));
  process.exit(1);
});
