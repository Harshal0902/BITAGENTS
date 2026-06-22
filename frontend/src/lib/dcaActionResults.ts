export type ParsedTransaction = {
  signature: string;
  explorerUrl?: string;
  status?: string;
  source?: string;
};

export type ParsedActionResult = {
  hasError: boolean;
  error?: string;
  transactions: ParsedTransaction[];
};

function pushTx(
  txs: ParsedTransaction[],
  seen: Set<string>,
  record: Record<string, unknown>,
  source?: string
) {
  const signature = record.signature;
  if (typeof signature !== "string" || !signature.trim() || seen.has(signature)) {
    return;
  }
  seen.add(signature);
  txs.push({
    signature,
    explorerUrl: typeof record.explorer_url === "string" ? record.explorer_url : undefined,
    status: typeof record.status === "string" ? record.status : undefined,
    source,
  });
}

function pushError(errors: string[], value: unknown) {
  if (typeof value === "string" && value.trim()) {
    errors.push(value.trim());
  }
}

function walk(value: unknown, txs: ParsedTransaction[], errors: string[], seen: Set<string>, source?: string) {
  if (value === null || value === undefined) return;

  if (Array.isArray(value)) {
    value.forEach((item) => walk(item, txs, errors, seen, source));
    return;
  }

  if (typeof value !== "object") return;

  const record = value as Record<string, unknown>;

  if ("error" in record) {
    pushError(errors, record.error);
  }

  if ("signature" in record) {
    pushTx(txs, seen, record, source);
  }

  for (const [key, nested] of Object.entries(record)) {
    if (key === "error" || key === "signature" || key === "explorer_url" || key === "status") {
      continue;
    }
    walk(nested, txs, errors, seen, source ?? key);
  }
}

export function parseActionResult(result: string): ParsedActionResult {
  let parsed: unknown = result;
  try {
    parsed = JSON.parse(result);
  } catch {
    const looksLikeError = /error|failed|exception/i.test(result);
    return {
      hasError: looksLikeError,
      error: looksLikeError ? result : undefined,
      transactions: [],
    };
  }

  const txs: ParsedTransaction[] = [];
  const errors: string[] = [];
  const seen = new Set<string>();

  walk(parsed, txs, errors, seen);

  const error = errors[0];
  const record = parsed as Record<string, unknown>;
  const topLevelFailed =
    record.status === "failed" ||
    (typeof record.error === "string" && record.error.length > 0);

  return {
    hasError: Boolean(error) || topLevelFailed,
    error,
    transactions: txs,
  };
}

export function parseConfirmationRequired(result: string): {
  message: string;
  pendingAction?: string;
} | null {
  try {
    const parsed = JSON.parse(result) as Record<string, unknown>;
    if (parsed.status !== "confirmation_required") return null;
    if (typeof parsed.message !== "string") return null;
    return {
      message: parsed.message,
      pendingAction:
        typeof parsed.pending_action === "string" ? parsed.pending_action : undefined,
    };
  } catch {
    return null;
  }
}

export function findLatestConfirmationRequired(
  actions: Array<{ result: string }>
): { message: string; pendingAction?: string } | null {
  for (let i = actions.length - 1; i >= 0; i -= 1) {
    const pending = parseConfirmationRequired(actions[i].result);
    if (pending) return pending;
  }
  return null;
}

export function mergeTransactions(
  existing: ParsedTransaction[],
  incoming: ParsedTransaction[]
): ParsedTransaction[] {
  const seen = new Set(existing.map((tx) => tx.signature));
  const merged = [...existing];
  for (const tx of incoming) {
    if (!seen.has(tx.signature)) {
      seen.add(tx.signature);
      merged.push(tx);
    }
  }
  return merged;
}

export function explorerUrlForSignature(signature: string, cluster?: string): string {
  const base = `https://explorer.solana.com/tx/${signature}`;
  if (!cluster || cluster === "mainnet" || cluster === "mainnet-beta") {
    return base;
  }
  return `${base}?cluster=${cluster}`;
}
