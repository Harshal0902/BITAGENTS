# Volume Agent — handoff notes (`claude-branch`)

For Harshal. This branch = `origin/Volume-bot` + your merged fixes (already in, see "Layer 1" below) + a new layer of fixes found by actually running a real campaign end-to-end against live BITAGENTS on mainnet. Nothing here duplicates your work — this picks up from exactly where your merge left off.

**Branch lineage**, oldest to newest:
```
origin/Volume-bot (7408a25)          ← what's currently pushed/shared
  └─ bbdcbde                          ← ATA rent reclaim + consecutive-failure persistence (prior session)
       └─ 246eeb8                    ← merge of YOUR fixes (4dc3119) with the above
            └─ (this branch's new commit) ← everything below
```

---

## Layer 1 — already in `246eeb8` (your work + earlier fixes, for context)

This is what the code looked like **before** this branch's new changes — i.e. what I pulled and started from today.

- **Meteora pool-creation script** (`scripts/create_dlmm_pool.cjs`): CommonJS port because the ESM build of `@meteora-ag/dlmm` breaks under current Node (`ERR_UNSUPPORTED_DIR_IMPORT`). Also verifies the pool account actually exists on-chain via `getAccountInfo` before reporting success — the original bug where the script said "created" but Solscan/Meteora showed nothing was a discarded `confirmTransaction` result plus no existence check.
- **Swap routing unrestricted** (`volume_agent.py`): removed a hardcoded `"dexes": "Meteora DLMM"` filter on the Jupiter swap request. Real tokens (including BITAGENTS) mostly trade on DAMM v2/DBC pools, not DLMM — the filter made every swap fail with "no routes found."
- **Pool-check recognizes non-DLMM liquidity** (`meteora_dlmm.py`, `check_jupiter_route_exists` + your `ensure_meteora_dlmm_pool`/`meteora_pool_app_url` additions): if Jupiter can already route a pair through any pool type, the agent reuses it instead of creating a redundant new DLMM pool. Your merge added the `/volume/pool/check` and `/volume/pool/ensure` manual endpoints/buttons on top of this.
- **Sell-leg fee bug fixed**: fee was computed from the base-token quantity instead of SOL proceeds, corrupting the ledger by orders of magnitude.
- **Safety rails added**: minimum trade size (`MIN_VOLUME_TRADE_SOL`, default 0.005 SOL — below this an ATA rent cost alone fails the tx), and auto-pause after `MAX_CONSECUTIVE_FAILURES` (default 3) so a broken/underfunded campaign stops retrying instead of burning fees forever.
- **`consecutive_failures`/`last_error` columns** added to `volume_campaigns` (were missing from schema, so every write to them was silently dropped and auto-pause never actually persisted).

All of the above was verified with real on-chain signatures at the time. Layer 2 is what's new.

---

## Layer 2 — new in this branch

Found by actually running a full campaign for BITAGENTS through the UI (not just code review), on the real Neon database, real mainnet RPC.

### 1. Balance check double-counted a campaign's own reservation against itself (`volume_ledger.py`, `volume_agent.py`)

**Symptom**: a freshly-created campaign with exactly enough budget would fail its very first cycle with "Insufficient SOL balance," 3 times in a row, and auto-pause — instantly, silently. Looked like "nothing happens."

**Root cause**: `check_user_can_spend_volume` computes `available = deposited − spent − reserved_for_other_campaigns`. But `_reserved_for_campaigns` counted **every** active/provisioning/paused campaign, including the one currently trying to spend — so a campaign would reserve its entire remaining budget against itself, then check if it could afford its own next cycle against a balance that already had that same budget subtracted. A campaign needing 0.2005 SOL total, with 0.24 SOL deposited and 0.035 already spent from earlier tests, would see `0.24 − 0.035 − 0.2005 (itself) ≈ 0.0042 SOL available` — nowhere near enough for even one 0.02 SOL cycle.

**Fix**: `_reserved_for_campaigns`, `get_volume_user_balances`, and `check_user_can_spend_volume` now all take an optional `exclude_campaign_id`. The two call sites that check a specific campaign's own affordability (`_run_volume_execution`'s per-cycle check, and `provision_campaign_infrastructure`'s pool-cost check) now pass their own campaign id so a campaign's own reservation never blocks its own spend.

**Verified**: re-ran the same campaign after the fix — it correctly saw the full available balance and completed all 10 cycles.

### 2. Sell-leg proceeds were never credited back to the user's ledger (`volume_ledger.py`, `volume_agent.py`)

**Symptom**: the campaign's own `spent_so_far`/`total_budget` tracking said 100% of budget spent, but that's expected — the real problem is the user-facing **available balance** dropped by the full buy amount every cycle and never got the sell proceeds back, overstating real cost by roughly **20x**.

**Root cause**: each cycle does buy (SOL→BITAGENTS) then sell (BITAGENTS→SOL) — the sell leg puts SOL back into the *same* agent wallet. `_run_volume_execution` recorded `record_user_spend_volume` for the buy and `record_volume_platform_fee` for both legs' fees, but nothing ever recorded the sell leg's SOL proceeds as a credit. That SOL was genuinely sitting back in the wallet, but the user's ledger balance had no entry for it — so it looked spent forever.

**Fix**: added `record_user_credit_volume()` (`volume_ledger.py`) — inserts a `direction="deposit"`, `reference_type="volume_sell_return"` ledger row. Does **not** re-verify an on-chain transfer (unlike the real-deposit path) because the agent itself already executed and confirmed the swap; this just reflects funds that are already confirmed to have landed back in the shared wallet. Wired into `_run_volume_execution` right after the sell-fee is recorded (`volume_agent.py`).

**One-time backfill (already run against production, not a repeatable script)**: 16 sell legs across 3 already-completed campaigns on the live wallet had this gap. Manually replayed `record_user_credit_volume` for each from the campaigns' stored `executions` history — restored **0.124852 SOL** to the real user's available balance (confirmed before/after via `get_volume_user_balances`). This was a one-off data fix on the shared Neon DB, not something this branch runs automatically — if any other wallet had run campaigns before this fix landed, the same backfill logic would need to be re-applied for them (check `SELECT DISTINCT user_wallet FROM volume_campaigns` — at the time of this fix, only one wallet had ever used it).

### 3. New simplified UI: `/agents/volume2`

New page + component (`frontend/src/app/agents/volume2/page.tsx`, `frontend/src/components/agents/VolumeAgentSimpleConsole.tsx`). Same wallet-connect/deposit/campaign-status machinery as the original `/agents/volume` page (reuses `VolumeAgentDeposit`, `VolumeCampaignPanel`, `useVolumeWalletAuth` unchanged) — the difference is purely the campaign-creation UI:

- BITAGENTS mint (`iu3A7azWTm3zQSk81SUC1JctB4zPYnxLmcmqq71EASY`) and SOL are hardcoded — no token fields.
- No manual "Check on Meteora" / "Create on Meteora" widget (not needed for BITAGENTS, and it was a source of confusing errors — see below).
- Three preset buttons instead of a manual form: Quick test (~0.2 SOL), Standard (~1 SOL), Full day (~3 SOL).

This exists specifically because Zeya found the original page too complex for day-to-day use as CEO, not because the original page is being deprecated.

### 4. Failed campaigns now show why (`VolumeCampaignPanel.tsx`, `volumePlanClient.ts`)

The campaign list showed `status: failed` with zero explanation — `last_error` was already being written to the DB (Layer 1's auto-pause work) but never read by the frontend. Added `last_error`/`consecutive_failures` to the `VolumeCampaignSummary` type and a warning block on failed campaigns showing the actual error (e.g. "Stopped after 3 failed attempts: Insufficient SOL balance...").

---

## Layer 3 — new-token pool creation now actually seeds liquidity

This directly answers what Harshal reported in the "Swaps Infrastructure and DNS Handoff" call (Jul 23): *"it is not creating the pool for the new tokens, and for the existing tokens, it is not depositing the funds."*

**Root cause, confirmed by reading the script line by line**: `create_dlmm_pool.cjs` built a payload including `tokenAmount`/`quoteAmount` (clearly intended as "how much liquidity to seed with"), but the script never read either field — it only created an **empty pool shell** via `createCustomizablePermissionlessLbPair` and stopped. There is no liquidity-provisioning code anywhere else in the repo either. An empty DLMM pool can't fill any swap, so a newly "created" pool looked broken the moment anyone tried to trade against it. This is one bug, not two — both halves of Harshal's report are the same missing feature.

**Fix** (`scripts/create_dlmm_pool.cjs`, `meteora_dlmm.py`, `volume_agent.py`):
- After the pool-creation transaction is verified on-chain (Layer 1's check), the script now does a second step: opens a DLMM position and deposits real `tokenAmount` + `quoteAmount` liquidity into it (Meteora's `initializePositionAndAddLiquidityByStrategy`, Spot strategy, ±10 bins around the starting price — narrow and simple, since our own trade sizes are small). Same "verify on-chain before reporting success" pattern as the pool-creation check itself: it reads the position back after confirming, and fails loudly if the position doesn't actually exist.
- `provision_campaign_infrastructure` now reads the campaign's `seed_token_amount` (already existed as a stored field, was never wired to anything) and passes it through as the base-token side of the deposit.
- **A pool is no longer marked ready to trade unless liquidity actually landed.** If seeding fails, the whole provisioning is marked `failed` (same auto-pause path as any other failure) instead of silently leaving behind a pool address that looks fine but can't fill orders.
- **Accounting fix to match**: the SOL/token amounts are only charged to the user's ledger if the deposit actually succeeded — previously the full estimated pool cost was charged unconditionally regardless of whether anything real happened on-chain.

**Important, easy to miss**: `seed_token_amount` has to be set to something meaningful when creating a campaign for a genuinely new token. If it's left at 0, the pool creates fine but has no base-token liquidity to sell to buyers — the first buy attempt will fail with no liquidity on that side. This isn't validated in code (kept deliberately simple); it's on whoever creates the campaign to size it sensibly relative to their planned trade volume.

### The 2% fee concern — checked against live data, not guessed

Pulled a live Jupiter quote for BITAGENTS directly: `routePlan[0].swapInfo.label` = **"Meteora DAMM v2"**, `platformFee: null`. Two things this confirms:

1. **BITAGENTS is already trading through a real Meteora pool** — Jupiter's "no dedicated DLMM pool" fallback label was just a detection gap in our own code (see below), not a sign it was avoiding Meteora.
2. **Jupiter itself charges nothing extra on top.** The `platformFee` field is null because we don't set one, and Jupiter doesn't add its own by default. So switching "to Meteora" wouldn't change BITAGENTS's economics at all — it's already there.

The real number worth watching: a 0.01 SOL test quote showed **~1.35% price impact** — that's the pool's actual depth (~$19.6K TVL at the time), not a fee. That's the correct lever for the "50 cycles" concern: **pool depth**, not which venue routes the trade. This is exactly what the seeding fix above addresses for brand-new pools — seed them with enough real liquidity relative to planned trade sizes and price impact per cycle stays small. For BITAGENTS's *own* existing pool specifically, adding more liquidity to reduce that 1.35% further would require topping up a live DAMM v2 pool — a different Meteora program/SDK than the DLMM pools this branch creates, and a separate, larger task not included here.

**Also fixed** (`meteora_dlmm.py`, `check_jupiter_route_exists`): now reports which venue Jupiter actually routed through and whether it's Meteora, instead of a flat `"source": "jupiter"` label that made it look like Meteora wasn't involved at all. `check_pool_infrastructure` now reports `"source": "meteora (via Jupiter)"` when that's what's actually happening.

---

## Operational note: local backend vs. a real deployment

Worth flagging since it came up directly: **there is currently no deployed backend.** `frontend/.env.local` points `AGENTS_API_URL` at `http://127.0.0.1:8765` — every campaign so far (including the real on-chain test runs referenced above) has been executed by a Python process running on Zeya's own laptop, connecting out to the real Neon DB, real Jupiter, and real Solana mainnet RPC over his home internet.

This explains an oddity Zeya noticed: turning his WiFi off mid-campaign made everything stop (no DB reads, no RPC calls possible), and turning it back on resumed it correctly. That's expected for the *current* local setup, not a bug — but it also means, right now, **the entire Volume Agent depends on Zeya's laptop being on, connected, and this process still running.** No campaign for any user executes if that machine is off or asleep.

For a real deployment, the backend needs to run on an always-on host (the `.env.local.example` has a placeholder line for a Render service URL, but nothing is actually deployed there yet). Once that's live, campaigns keep running on the server's own connection regardless of anyone's local machine — that's the main practical reason to prioritize actually standing up that deployment before onboarding anyone beyond internal testing.

---

## What's still open for you

1. **No production deployment exists yet** (see above) — this is probably the single biggest blocker to this being usable by anyone but us.
2. **`VOLUME_AGENT_WALLET_PRIVATE_KEY`** needs to be set wherever the backend does end up deployed — generate a fresh dedicated key, don't reuse the local test key.
3. **`npm install` in `agent/new/scripts`** needs to happen in the deployed environment (Meteora pool-creation script's `node_modules` isn't committed).
4. **Ledger backfill scope**: if anyone besides Zeya's test wallet ran volume campaigns before this branch, they need the same sell-proceeds backfill (see Layer 2, #2) — check `volume_campaigns` for other `user_wallet` values.
5. **Fee collection is still purely bookkeeping**: the "0.25% per leg" platform fee is recorded in the ledger (reduces a user's available balance) but nothing actually moves it to a separate BITAGENTS-controlled wallet — all deposited/spent/fee SOL sits in one shared agent wallet. Worth a product decision on when/how to actually sweep fees out as real revenue.
6. **`.mjs` cleanup**: `create_dlmm_pool.mjs` is superseded by the `.cjs` version and unused — safe to delete once you've confirmed the `.cjs` version works in your environment too.
7. **Adding liquidity to BITAGENTS's own existing pool** (not new-pool creation, topping up the live one) is a separate, larger task — that pool is Meteora DAMM v2, a different program/SDK than the DLMM pools this branch creates and seeds. Not started.
8. **Orca was explicitly ruled out** for this round (Zeya's call) — the branch stays Meteora-only. Don't spend time on the "Ecura"/Orca idea from the Jul 23 call unless that changes.

## How this was tested

Full campaign (10 cycles, 0.01 SOL/leg) run against the live BITAGENTS/SOL pair on mainnet through the actual `/agents/volume2` UI, using Zeya's real deposited SOL on the real Neon production database (not a local test DB — there was no safe way to test the reservation/accounting bugs without the real ledger state that caused them). Every cycle's buy and sell signature was independently checked against Solana mainnet RPC directly (`getTransaction`, confirming `err: null`), not just trusted from this app's own database. The sell-proceeds backfill was verified by comparing `get_volume_user_balances` output before and after.
