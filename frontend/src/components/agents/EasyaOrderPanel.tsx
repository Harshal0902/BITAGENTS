"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { Panel } from "@/components/AppShell";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import {
  cancelEasyaOrder,
  fetchEasyaOrders,
  orderExplorerUrl,
  updateEasyaLimitOrder,
  type EasyaOrderSummary,
} from "@/lib/easyaOrderClient";

const SECTION_MAX_HEIGHT = "max-h-[280px]";

type OrderStatusFilter = "all" | "active" | "filled" | "cancelled" | "failed";

function shortMint(mint?: string | null) {
  if (!mint) return "-";
  if (mint.length <= 12) return mint;
  return `${mint.slice(0, 4)}…${mint.slice(-4)}`;
}

function formatTime(iso?: string | null) {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function formatUsd(value?: number | null) {
  if (value == null || !Number.isFinite(value)) return "n/a";
  if (value < 0.0001) return `$${value.toExponential(2)}`;
  if (value < 1) return `$${value.toFixed(6)}`;
  return `$${value.toFixed(4)}`;
}

function statusClass(status: string) {
  if (status === "active") return "text-signal";
  if (status === "pending") return "text-warn";
  if (status === "filled") return "text-signal";
  if (status === "failed") return "text-warn";
  if (status === "cancelled") return "text-muted-foreground";
  return "text-foreground";
}

function orderTitle(order: EasyaOrderSummary) {
  if (order.order_type === "limit") {
    return `Limit buy · ${order.output_token}`;
  }
  return `Market buy · ${order.output_token}`;
}

function CollapsibleSection({
  title,
  count,
  defaultOpen = true,
  headerExtra,
  children,
}: {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  headerExtra?: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Panel
      title={`${title}${count != null ? ` (${count})` : ""}`}
      action={
        <div className="flex items-center gap-2">
          {headerExtra}
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground transition hover:text-signal"
            aria-expanded={open}
          >
            {open ? "Hide" : "Show"}
            <ChevronDown
              size={14}
              className={`transition-transform ${open ? "rotate-180" : ""}`}
            />
          </button>
        </div>
      }
    >
      {open ? (
        <div className={`${SECTION_MAX_HEIGHT} overflow-y-auto pr-1`}>{children}</div>
      ) : (
        <p className="font-mono text-[10px] text-muted-foreground">Section collapsed.</p>
      )}
    </Panel>
  );
}

function LimitOrderRow({
  order,
  authToken,
  busy,
  onUpdated,
  cluster,
}: {
  order: EasyaOrderSummary;
  authToken: string;
  busy: boolean;
  onUpdated: () => void;
  cluster?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [amountSol, setAmountSol] = useState(String(order.amount_input));
  const [limitPrice, setLimitPrice] = useState(
    order.limit_price_usd != null ? String(order.limit_price_usd) : ""
  );
  const [slippageBps, setSlippageBps] = useState(String(order.slippage_bps ?? 100));
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const canEdit = order.order_type === "limit" && order.status === "active";
  const canCancel = order.status === "active" || order.status === "pending";

  async function runCancel() {
    setActionBusy(true);
    setActionError(null);
    const result = await cancelEasyaOrder(order.id, authToken);
    setActionBusy(false);
    setConfirmCancel(false);
    if (result.error) {
      setActionError(result.error);
      return;
    }
    onUpdated();
  }

  async function runSave() {
    const parsedAmount = Number(amountSol);
    const parsedLimit = Number(limitPrice);
    const parsedSlippage = Number(slippageBps);

    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      setActionError("Enter a valid SOL amount.");
      return;
    }
    if (!Number.isFinite(parsedLimit) || parsedLimit <= 0) {
      setActionError("Enter a valid limit price.");
      return;
    }
    if (!Number.isFinite(parsedSlippage) || parsedSlippage < 1 || parsedSlippage > 5000) {
      setActionError("Slippage must be between 1 and 5000 bps.");
      return;
    }

    setActionBusy(true);
    setActionError(null);
    const result = await updateEasyaLimitOrder(
      order.id,
      {
        amount_sol: parsedAmount,
        limit_price_usd: parsedLimit,
        slippage_bps: Math.round(parsedSlippage),
      },
      authToken
    );
    setActionBusy(false);
    if (result.error) {
      setActionError(result.error);
      return;
    }
    setEditing(false);
    onUpdated();
  }

  const priceDistance =
    order.current_price_usd != null && order.limit_price_usd != null
      ? order.current_price_usd <= order.limit_price_usd
        ? "ready to fill"
        : `${(((order.current_price_usd - order.limit_price_usd) / order.limit_price_usd) * 100).toFixed(1)}% above limit`
      : null;

  return (
    <div className="border border-grid bg-background/60 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-mono text-xs text-foreground">{orderTitle(order)}</div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            ID `{order.id}` · {order.pair}
          </div>
        </div>
        <span className={`font-mono text-[10px] uppercase tracking-[0.16em] ${statusClass(order.status)}`}>
          {order.status}
        </span>
      </div>

      {!editing ? (
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[10px] text-muted-foreground">
          <div>
            <dt>Spend</dt>
            <dd className="text-foreground">
              {order.amount_input} {order.input_token}
              <span className="block text-[9px] text-muted-foreground">+ 0.1% fee on fill</span>
            </dd>
          </div>
          <div>
            <dt>Limit price</dt>
            <dd className="text-foreground">
              {order.limit_price_usd != null ? formatUsd(order.limit_price_usd) : "-"}
            </dd>
          </div>
          <div>
            <dt>Current price</dt>
            <dd className="text-foreground">{formatUsd(order.current_price_usd)}</dd>
          </div>
          <div>
            <dt>Trigger</dt>
            <dd className="text-foreground">price ≤ limit</dd>
          </div>
          {priceDistance && (
            <div className="col-span-2">
              <dt>Fill status</dt>
              <dd className={priceDistance === "ready to fill" ? "text-signal" : "text-warn"}>
                {priceDistance}
              </dd>
            </div>
          )}
          <div>
            <dt>Slippage</dt>
            <dd className="text-foreground">{order.slippage_bps ?? 100} bps</dd>
          </div>
          <div>
            <dt>Created</dt>
            <dd className="text-foreground">{formatTime(order.created_at)}</dd>
          </div>
          <div className="col-span-2">
            <dt>Mints</dt>
            <dd className="break-all text-foreground">
              in {shortMint(order.input_mint)} → out {shortMint(order.output_mint)}
            </dd>
          </div>
        </dl>
      ) : (
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <label className="grid gap-1 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
            SOL amount
            <input
              type="number"
              min="0"
              step="any"
              value={amountSol}
              onChange={(e) => setAmountSol(e.target.value)}
              disabled={actionBusy}
              className="border border-grid bg-background px-2 py-1.5 text-sm text-foreground outline-none focus:border-signal"
            />
          </label>
          <label className="grid gap-1 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
            Limit USD
            <input
              type="number"
              min="0"
              step="any"
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
              disabled={actionBusy}
              className="border border-grid bg-background px-2 py-1.5 text-sm text-foreground outline-none focus:border-signal"
            />
          </label>
          <label className="grid gap-1 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
            Slippage bps
            <input
              type="number"
              min="1"
              max="5000"
              step="1"
              value={slippageBps}
              onChange={(e) => setSlippageBps(e.target.value)}
              disabled={actionBusy}
              className="border border-grid bg-background px-2 py-1.5 text-sm text-foreground outline-none focus:border-signal"
            />
          </label>
        </div>
      )}

      {actionError && <p className="mt-2 font-mono text-[10px] text-warn">{actionError}</p>}

      <div className="mt-3 flex flex-wrap gap-2">
        {canEdit && !editing && (
          <button
            type="button"
            disabled={busy || actionBusy}
            onClick={() => {
              setEditing(true);
              setActionError(null);
            }}
            className="border border-grid px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground transition hover:border-signal hover:text-signal disabled:opacity-40"
          >
            Edit
          </button>
        )}
        {editing && (
          <>
            <button
              type="button"
              disabled={busy || actionBusy}
              onClick={() => void runSave()}
              className="border border-signal px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-signal transition hover:bg-signal/10 disabled:opacity-40"
            >
              {actionBusy ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              disabled={actionBusy}
              onClick={() => {
                setEditing(false);
                setAmountSol(String(order.amount_input));
                setLimitPrice(order.limit_price_usd != null ? String(order.limit_price_usd) : "");
                setSlippageBps(String(order.slippage_bps ?? 100));
                setActionError(null);
              }}
              className="border border-grid px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground transition hover:text-foreground disabled:opacity-40"
            >
              Cancel edit
            </button>
          </>
        )}
        {canCancel && (
          <button
            type="button"
            disabled={busy || actionBusy}
            onClick={() => setConfirmCancel(true)}
            className="border border-grid px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground transition hover:border-warn hover:text-warn disabled:opacity-40"
          >
            Delete
          </button>
        )}
      </div>

      <ConfirmDialog
        open={confirmCancel}
        onOpenChange={setConfirmCancel}
        title="Delete limit order"
        description={
          <p>
            Cancel limit buy for <strong className="text-foreground">{order.output_token}</strong>{" "}
            (ID `{order.id}`)? Reserved SOL will be released. This cannot be undone.
          </p>
        }
        confirmLabel="Delete order"
        cancelLabel="Keep order"
        busy={actionBusy}
        onConfirm={() => void runCancel()}
      />
    </div>
  );
}

function HistoryOrderRow({ order, cluster }: { order: EasyaOrderSummary; cluster?: string }) {
  const href = orderExplorerUrl(order.signature, cluster);
  const ok = order.status === "filled" && !order.error_message;

  return (
    <div className="border border-grid bg-background/40 px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-[11px] text-foreground">
          {order.order_type === "limit" ? "Limit" : "Market"} · {order.pair}
        </span>
        <span className={`font-mono text-[10px] uppercase ${ok ? "text-signal" : statusClass(order.status)}`}>
          {order.error_message ? "failed" : order.status}
        </span>
      </div>
      <div className="mt-1 font-mono text-[10px] text-muted-foreground">
        {formatTime(order.filled_at ?? order.cancelled_at ?? order.created_at)} · ID `{order.id}` ·{" "}
        {order.amount_input} {order.input_token}
        {order.limit_price_usd != null && ` · limit ${formatUsd(order.limit_price_usd)}`}
        {order.platform_fee != null && order.platform_fee > 0 && (
          <> · fee {order.platform_fee} {order.input_token}</>
        )}
        {order.output_amount != null && ` → ${order.output_amount} ${order.output_token}`}
      </div>
      {order.error_message && (
        <p className="mt-1 font-mono text-[10px] text-warn">{order.error_message}</p>
      )}
      {href && order.signature && (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block font-mono text-[10px] text-signal hover:underline"
        >
          {order.signature.slice(0, 8)}…{order.signature.slice(-8)} ↗
        </a>
      )}
    </div>
  );
}

export function EasyaOrderPanel({
  authToken,
  cluster,
  refreshTick = 0,
}: {
  authToken?: string | null;
  cluster?: string;
  refreshTick?: number;
}) {
  const [orders, setOrders] = useState<EasyaOrderSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<OrderStatusFilter>("active");
  const [searchQuery, setSearchQuery] = useState("");

  const reload = useCallback(async () => {
    if (!authToken) {
      setOrders([]);
      return;
    }
    setLoading(true);
    setError(null);
    const data = await fetchEasyaOrders(authToken);
    setOrders(data?.orders ?? []);
    if (!data) {
      setError("Could not load trading orders.");
    }
    setLoading(false);
  }, [authToken]);

  useEffect(() => {
    void reload();
  }, [reload, refreshTick]);

  useEffect(() => {
    if (!authToken) return;
    const interval = window.setInterval(() => {
      void reload();
    }, 30_000);
    return () => window.clearInterval(interval);
  }, [authToken, reload]);

  const activeLimitOrders = useMemo(
    () =>
      orders.filter(
        (order) =>
          order.order_type === "limit" && (order.status === "active" || order.status === "pending")
      ),
    [orders]
  );

  const historyOrders = useMemo(
    () =>
      orders.filter(
        (order) =>
          order.status === "filled" ||
          order.status === "cancelled" ||
          order.status === "failed" ||
          (order.order_type === "market" && order.status !== "active")
      ),
    [orders]
  );

  const filteredActive = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return activeLimitOrders.filter((order) => {
      if (statusFilter !== "all" && statusFilter !== "active" && order.status !== statusFilter) {
        return false;
      }
      if (!query) return true;
      return (
        order.output_token.toLowerCase().includes(query) ||
        order.pair.toLowerCase().includes(query) ||
        order.id.toLowerCase().includes(query) ||
        (order.output_mint ?? "").toLowerCase().includes(query)
      );
    });
  }, [activeLimitOrders, statusFilter, searchQuery]);

  if (!authToken) {
    return (
      <CollapsibleSection title="Your limit orders" defaultOpen>
        <p className="font-mono text-xs text-muted-foreground">
          Sign in with your wallet to view and manage limit orders here — no need to ask the agent
          to list them.
        </p>
      </CollapsibleSection>
    );
  }

  return (
    <div className="space-y-6">
      <CollapsibleSection
        title="Your limit orders"
        count={filteredActive.length}
        defaultOpen
        headerExtra={
          <button
            type="button"
            onClick={() => void reload()}
            disabled={loading}
            className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground transition hover:text-signal disabled:opacity-40"
          >
            {loading ? "…" : "Refresh"}
          </button>
        }
      >
        {error && <p className="mb-3 font-mono text-[11px] text-warn">{error}</p>}

        <p className="mb-3 text-sm text-muted-foreground">
          Active limit buys are monitored every ~30s. When EASY Screener price is at or below your
          limit, the agent executes a Jupiter swap (0.1% platform fee).
        </p>

        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search token, pair, id, mint…"
            className="flex-1 border border-grid bg-background px-3 py-2 font-mono text-[11px] text-foreground outline-none focus:border-signal"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as OrderStatusFilter)}
            className="border border-grid bg-background px-3 py-2 font-mono text-[11px] uppercase tracking-[0.12em] text-foreground outline-none focus:border-signal"
          >
            <option value="active">Active only</option>
            <option value="all">All statuses</option>
            <option value="filled">Filled</option>
            <option value="cancelled">Cancelled</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        {filteredActive.length === 0 && !loading && (
          <p className="font-mono text-xs text-muted-foreground">
            {activeLimitOrders.length === 0
              ? "No active limit orders. Create one via chat, e.g. “Place a limit buy for 0.05 SOL of BITAGENTS at $0.02”."
              : "No orders match your filters."}
          </p>
        )}

        <div className="grid gap-3 lg:grid-cols-2">
          {filteredActive.map((order) => (
            <LimitOrderRow
              key={order.id}
              order={order}
              authToken={authToken}
              busy={loading}
              onUpdated={() => void reload()}
              cluster={cluster}
            />
          ))}
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Order history" count={historyOrders.length} defaultOpen={false}>
        {historyOrders.length === 0 && !loading && (
          <p className="font-mono text-xs text-muted-foreground">
            Filled market/limit buys and cancelled orders appear here with on-chain signatures.
          </p>
        )}
        <div className="space-y-2">
          {historyOrders.map((order) => (
            <HistoryOrderRow key={`${order.id}-${order.filled_at ?? order.created_at}`} order={order} cluster={cluster} />
          ))}
        </div>
      </CollapsibleSection>
    </div>
  );
}
