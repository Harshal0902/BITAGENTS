# Volume Agent — fixes and handoff notes (Volume-bot branch)

This branch fixes three real bugs found while testing the Volume Agent end-to-end against the live BITAGENTS token on mainnet. All fixes are verified working with real on-chain transactions (not just code review) — a full 4-cycle test campaign ran to completion with correct accounting throughout.

## What was broken

### 1. Meteora pool-creation script crashed on import (`meteora_dlmm.py`, `scripts/create_dlmm_pool.cjs`)
`create_dlmm_pool.mjs` used ESM `import`, which breaks under current Node versions because `@meteora-ag/dlmm`'s ESM build re-exports `@coral-xyz/anchor` via a directory import Node's strict resolver rejects (`ERR_UNSUPPORTED_DIR_IMPORT`). Fixed by adding `create_dlmm_pool.cjs`, a CommonJS port using `require()` (the package's CJS build doesn't hit this). `METEORA_POOL_SCRIPT` now points at the `.cjs` file. The original `.mjs` is left in place but unused — safe to delete once you've confirmed the `.cjs` version is working for you too.

**Also needs**: `cd agent/new/scripts && npm install` — `node_modules` wasn't committed and wasn't present, so pool creation would fail immediately regardless of the ESM issue.

### 2. Swap execution was hardcoded to Meteora DLMM only (`volume_agent.py`, `_execute_meteora_swap`)
The Jupiter build request included `"dexes": "Meteora DLMM"`, which blocks routing through any other pool type. Real launched tokens (including our own BITAGENTS token) trade on **DAMM v2 / DBC pools, not DLMM** — this would make every swap fail with "no routes found" for most real target users. Removed the restriction entirely (matches how the DCA agent's swap execution already works, unrestricted).

### 3. Pool-check logic was blind to non-DLMM liquidity (`meteora_dlmm.py`, `check_pool_infrastructure`)
The check only queried Meteora's DLMM-specific API, so it reported "no pool, must create one" even when a token already has real, tradeable liquidity elsewhere (again — true for most real Kickstart tokens). Added `check_jupiter_route_exists()`: a wallet-free check against Jupiter's quote endpoint that recognizes liquidity of *any* pool type. If Jupiter can already route the pair, the agent now reuses that liquidity via Jupiter directly instead of creating a redundant, wasteful new pool. **This means most real users won't pay the pool-creation cost at all** — only genuinely brand-new, illiquid tokens still need a fresh pool.

### 4. Sell-leg platform fee was computed from the wrong quantity (`volume_agent.py`, `_run_volume_execution`)
The sell-leg fee recording passed `sell_amount` (the *base-token* quantity being sold, e.g. thousands of tokens) into a function that computes a *SOL* fee — producing a "spend" thousands of times too large and permanently corrupting the user's ledger balance (manifested as campaigns silently failing forever with "Insufficient SOL balance: Available 0.0"). Fixed to use the actual SOL proceeds from the sell leg (`sell.get("output_amount_raw")`, same pattern the buy-leg fee already used correctly), falling back to `trade_amount` if unavailable.

## New safety features added

- **Minimum trade size enforced** (`volume_ledger.py`, `validate_volume_trade_amount`): campaigns with a per-leg trade under `MIN_VOLUME_TRADE_SOL` (default 0.005 SOL) are rejected at creation time, before anything executes. A new SPL token account costs ~0.00204 SOL in one-time rent — trade sizes below that floor were failing on-chain with "insufficient SOL for ATA rent" and still burning network fees on every failed attempt.
- **Auto-pause on repeated failure** (`volume_agent.py`, `_record_execution_failure`): after `MAX_CONSECUTIVE_FAILURES` (default 3) consecutive failed cycles, a campaign automatically sets itself to `failed` and stops retrying. Before this, a misconfigured or under-funded campaign would retry forever, unattended, silently draining the wallet on Solana network fees. Both new constants are env-configurable (`MIN_VOLUME_TRADE_SOL`, `VOLUME_MAX_CONSECUTIVE_FAILURES`).

## What's still open for you

1. **Production wallet key**: `VOLUME_AGENT_WALLET_PRIVATE_KEY` needs to be set on the real deployed backend (Render) — it wasn't set anywhere I could find. Generate a fresh dedicated key for this, don't reuse a local test throwaway.
2. **`npm install` in `agent/new/scripts`** needs to happen in the deployed environment too, same as local.
3. **Product decision, not a bug**: for tokens with real existing liquidity, the agent now trades through Jupiter into that real pool rather than a dedicated one BITAGENTS controls. This costs more (third-party pool fees + price impact) but is the only way the generated volume is actually visible on the token's real trading pair (DexScreener, etc.) rather than hidden in an obscure side-pool. Worth confirming this tradeoff is the intended one — see commit history / conversation context for the full reasoning if you want to revisit it.
4. **`.mjs` cleanup**: once you've confirmed `create_dlmm_pool.cjs` works in your environment too, feel free to delete the now-unused `create_dlmm_pool.mjs`.

## How this was tested

Ran a real campaign against the live BITAGENTS/SOL pair (mint `iu3A7azWTm3zQSk81SUC1JctB4zPYnxLmcmqq71EASY`) on mainnet, with a throwaway local test wallet (not committed, not this repo's problem — you'll use your own on Render). Confirmed via direct on-chain transaction signatures that a 4-cycle campaign (0.005 SOL/leg) completed end-to-end with correct fee accounting on every cycle. Local test setup used an isolated Docker Postgres container, not the shared Neon database — no production data was touched.
