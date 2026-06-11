# BITAGENTS Demo Script

## Step 1: Start app

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

Make sure Phantom is set to Solana devnet.

## Step 2: Register compute provider

1. Open `/provider`.
2. Connect or paste the provider wallet.
3. Set provider name to `Local BITAGENTS Provider`.
4. Set compute type to `CPU`.
5. Set price per task to `0.01` SOL.
6. Set status to `online`.
7. Click `Register provider`.

Copy the provider wallet into `.env.local`:

```bash
PROVIDER_WALLET=YOUR_PROVIDER_PUBLIC_KEY
```

Restart the worker if it is already running.

## Step 3: Connect user wallet

1. Open `/dashboard`.
2. Connect Phantom.
3. Confirm Phantom is on devnet.
4. Confirm the wallet has devnet SOL.

## Step 4: Create Wallet Watcher task

1. Select `Wallet Watcher`.
2. Use the connected wallet address or paste another devnet wallet.
3. Click `Create and pay task`.

## Step 5: Pay SOL on devnet

1. Phantom opens a transaction approval.
2. Approve the transfer to `NEXT_PUBLIC_TREASURY_PUBLIC_KEY`.
3. The UI records the payment signature.
4. Open the `Payment tx` link to show Solana Explorer on devnet.

## Step 6: Worker picks up task

The provider worker polls the API and finds the assigned task for `PROVIDER_WALLET`.

Expected worker log:

```text
[worker xxxx...yyyy] claiming Wallet Watcher Agent TASK_ID
```

## Step 7: Worker runs computation

For Wallet Watcher, the worker calls Solana devnet RPC for:

- SOL balance
- token account count
- latest 5 signatures

Expected status transition:

```text
assigned -> computing -> completed
```

## Step 8: Result appears

Open `/dashboard` or `/demo`.

Show:

- task status timeline
- SOL balance
- token accounts count
- latest signatures
- generated summary

## Step 9: Provider payout transaction shown

1. Open `/demo`.
2. Connect the treasury/admin wallet.
3. Click `Pay provider` on the completed task.
4. Approve the devnet SOL transfer to the provider wallet.
5. Show the `Payout tx` link on Solana Explorer devnet.

## Step 10: Explain future BITAGENTS token utility

Open `/utility` and explain:

- Platform fees and buybacks
- Compute provider staking
- Premium agent access
- Marketplace settlement
- Future agent credits

Close with the MVP proof:

```text
A user paid on Solana devnet, a provider worker completed real computation, and the provider payout was recorded on-chain.
```
