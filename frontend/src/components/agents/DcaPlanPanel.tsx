"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { Panel } from "@/components/AppShell";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { explorerUrlForSignature } from "@/lib/dcaActionResults";
import {
  executionExplorerUrl,
  fetchDcaExecutions,
  fetchDcaPlans,
  fetchWalletLedger,
  ledgerDirectionLabel,
  updateDcaPlanStatus,
  type DcaExecutionRow,
  type DcaPlanSummary,
  type LedgerEntry,
} from "@/lib/dcaPlanClient";

const SECTION_MAX_HEIGHT = "max-h-[280px]";

type PlanStatusFilter = "all" | "active" | "paused" | "completed" | "cancelled";

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

function statusClass(status: string) {
  if (status === "active") return "text-signal";
  if (status === "paused") return "text-warn";
  if (status === "completed" || status === "cancelled") return "text-muted-foreground";
  return "text-foreground";
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

function PlanRow({
  plan,
  authToken,
  busy,
  onUpdated,
}: {
  plan: DcaPlanSummary;
  authToken: string;
  busy: boolean;
  onUpdated: () => void;
}) {
  const [confirmAction, setConfirmAction] = useState<"pause" | "resume" | "cancel" | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  async function runStatus(action: "pause" | "resume" | "cancel") {
    setActionBusy(true);
    setActionError(null);
    const result = await updateDcaPlanStatus(plan.id, action, authToken);
    setActionBusy(false);
    setConfirmAction(null);
    if (result.error) {
      setActionError(result.error);
      return;
    }
    onUpdated();
  }

  return (
    <div className="border border-grid bg-background/60 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-mono text-xs text-foreground">{plan.name}</div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            ID `{plan.id}` · {plan.pair}
          </div>
        </div>
        <span className={`font-mono text-[10px] uppercase tracking-[0.16em] ${statusClass(plan.status)}`}>
          {plan.status}
        </span>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[10px] text-muted-foreground">
        <div>
          <dt>Buy</dt>
          <dd className="text-foreground">
            {plan.amount_per_buy} / {plan.interval}
            <span className="block text-[9px] text-muted-foreground">+ 0.5% fee per successful buy</span>
          </dd>
        </div>
        <div>
          <dt>Executions</dt>
          <dd className="text-foreground">
            {plan.executions}
            {plan.max_executions != null ? ` / ${plan.max_executions}` : ""}
          </dd>
        </div>
        <div>
          <dt>Spent</dt>
          <dd className="text-foreground">{plan.spent}</dd>
        </div>
        <div>
          <dt>Next run</dt>
          <dd className="text-foreground">{formatTime(plan.next_execution_at)}</dd>
        </div>
        <div className="col-span-2">
          <dt>Mints</dt>
          <dd className="break-all text-foreground">
            in {shortMint(plan.input_mint)} → out {shortMint(plan.output_mint)}
          </dd>
        </div>
      </dl>

      {actionError && <p className="mt-2 font-mono text-[10px] text-warn">{actionError}</p>}

      <div className="mt-3 flex flex-wrap gap-2">
        {plan.status === "active" && (
          <button
            type="button"
            disabled={busy || actionBusy}
            onClick={() => setConfirmAction("pause")}
            className="border border-grid px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground transition hover:border-warn hover:text-warn disabled:opacity-40"
          >
            Pause
          </button>
        )}
        {plan.status === "paused" && (
          <button
            type="button"
            disabled={busy || actionBusy}
            onClick={() => setConfirmAction("resume")}
            className="border border-grid px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground transition hover:border-signal hover:text-signal disabled:opacity-40"
          >
            Resume
          </button>
        )}
        {plan.status !== "cancelled" && plan.status !== "completed" && (
          <button
            type="button"
            disabled={busy || actionBusy}
            onClick={() => setConfirmAction("cancel")}
            className="border border-grid px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground transition hover:border-warn hover:text-warn disabled:opacity-40"
          >
            Cancel
          </button>
        )}
      </div>

      <ConfirmDialog
        open={confirmAction !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmAction(null);
        }}
        title={`${confirmAction ?? "Update"} plan`}
        description={
          <p>
            {confirmAction === "pause" && `Pause DCA plan ${plan.name}?`}
            {confirmAction === "resume" && `Resume DCA plan ${plan.name}?`}
            {confirmAction === "cancel" && `Cancel DCA plan ${plan.name}? This cannot be undone.`}
          </p>
        }
        confirmLabel="Yes, proceed"
        cancelLabel="No"
        busy={actionBusy}
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => {
          if (confirmAction) void runStatus(confirmAction);
        }}
      />
    </div>
  );
}

function ExecutionRow({ row, cluster }: { row: DcaExecutionRow; cluster?: string }) {
  const href = executionExplorerUrl(row, cluster);
  const ok = row.status === "success" && !row.error;

  return (
    <div className="border border-grid bg-background/40 px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-[11px] text-foreground">{row.pair}</span>
        <span className={`font-mono text-[10px] uppercase ${ok ? "text-signal" : "text-warn"}`}>
          {row.dry_run ? "dry run" : row.error ? "failed" : row.status ?? "-"}
        </span>
      </div>
      <div className="mt-1 font-mono text-[10px] text-muted-foreground">
        {formatTime(row.at)} · plan `{row.plan_id}` · {row.amount} {row.input_token}
        {row.platform_fee != null && row.platform_fee > 0 && (
          <> · fee {row.platform_fee} {row.input_token}</>
        )}
        {row.output_amount != null && ` → ${row.output_amount} ${row.output_token}`}
      </div>
      {row.error && <p className="mt-1 font-mono text-[10px] text-warn">{row.error}</p>}
      {href && row.signature && (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block font-mono text-[10px] text-signal hover:underline"
        >
          {row.signature.slice(0, 8)}…{row.signature.slice(-8)} ↗
        </a>
      )}
    </div>
  );
}

function LedgerRow({ entry, cluster }: { entry: LedgerEntry; cluster?: string }) {
  const href =
    entry.explorer_url ??
    (entry.signature ? explorerUrlForSignature(entry.signature, cluster) : null);
  const signed = entry.direction === "deposit" || entry.direction === "acquire" ? "+" : "−";

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border border-grid bg-background/40 px-3 py-2">
      <div>
        <div className="font-mono text-[11px] text-foreground">
          {ledgerDirectionLabel(entry.direction)} · {signed}
          {entry.amount} {entry.token}
        </div>
        <div className="font-mono text-[10px] text-muted-foreground">
          {formatTime(entry.verified_at)} · mint {shortMint(entry.mint)}
        </div>
      </div>
      {href && (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono text-[10px] text-signal hover:underline"
        >
          Explorer ↗
        </a>
      )}
    </div>
  );
}

export function DcaPlanPanel({
  authToken,
  cluster,
  refreshTick = 0,
}: {
  authToken?: string | null;
  cluster?: string;
  refreshTick?: number;
}) {
  const [plans, setPlans] = useState<DcaPlanSummary[]>([]);
  const [executions, setExecutions] = useState<DcaExecutionRow[]>([]);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<PlanStatusFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const reload = useCallback(async () => {
    if (!authToken) {
      setPlans([]);
      setExecutions([]);
      setLedger([]);
      return;
    }
    setLoading(true);
    setError(null);
    const [plansData, execData, ledgerData] = await Promise.all([
      fetchDcaPlans(authToken),
      fetchDcaExecutions(authToken, 50),
      fetchWalletLedger(authToken, 30),
    ]);
    setPlans(plansData?.plans ?? []);
    setExecutions(execData?.executions ?? []);
    setLedger(ledgerData?.entries ?? []);
    if (!plansData && !execData) {
      setError("Could not load DCA data.");
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
    }, 60_000);
    return () => window.clearInterval(interval);
  }, [authToken, reload]);

  const filteredPlans = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return plans.filter((plan) => {
      if (statusFilter !== "all" && plan.status !== statusFilter) return false;
      if (!query) return true;
      return (
        plan.name.toLowerCase().includes(query) ||
        plan.pair.toLowerCase().includes(query) ||
        plan.id.toLowerCase().includes(query) ||
        (plan.input_mint ?? "").toLowerCase().includes(query) ||
        (plan.output_mint ?? "").toLowerCase().includes(query)
      );
    });
  }, [plans, statusFilter, searchQuery]);

  if (!authToken) {
    return (
      <CollapsibleSection title="Your DCA plans" defaultOpen>
        <p className="font-mono text-xs text-muted-foreground">
          Sign in with your wallet to view plans and swap history here - no need to ask the agent to list them.
        </p>
      </CollapsibleSection>
    );
  }

  return (
    <div className="space-y-6">
      <CollapsibleSection
        title="Your DCA plans"
        count={filteredPlans.length}
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

        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search name, pair, id, mint…"
            className="flex-1 border border-grid bg-background px-3 py-2 font-mono text-[11px] text-foreground outline-none focus:border-signal"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as PlanStatusFilter)}
            className="border border-grid bg-background px-3 py-2 font-mono text-[11px] uppercase tracking-[0.12em] text-foreground outline-none focus:border-signal"
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        {filteredPlans.length === 0 && !loading && (
          <p className="font-mono text-xs text-muted-foreground">
            {plans.length === 0
              ? "No DCA plans yet. Create one via chat above."
              : "No plans match your filters."}
          </p>
        )}

        <div className="grid gap-3 lg:grid-cols-2">
          {filteredPlans.map((plan) => (
            <PlanRow
              key={plan.id}
              plan={plan}
              authToken={authToken}
              busy={loading}
              onUpdated={() => void reload()}
            />
          ))}
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="DCA swap history" count={executions.length} defaultOpen={false}>
        {executions.length === 0 && !loading && (
          <p className="font-mono text-xs text-muted-foreground">
            Completed DCA buys will appear here with on-chain signatures.
          </p>
        )}
        <div className="space-y-2">
          {executions.map((row, index) => (
            <ExecutionRow key={`${row.plan_id}-${row.at}-${index}`} row={row} cluster={cluster} />
          ))}
        </div>
      </CollapsibleSection>

      <CollapsibleSection
        title="Wallet ledger · deposits & withdrawals"
        count={ledger.length}
        defaultOpen={false}
      >
        {ledger.length === 0 && !loading && (
          <p className="font-mono text-xs text-muted-foreground">
            Deposits, DCA spends, acquired tokens, and withdrawals are recorded here.
          </p>
        )}
        <div className="space-y-2">
          {ledger.map((entry) => (
            <LedgerRow key={entry.id} entry={entry} cluster={cluster} />
          ))}
        </div>
      </CollapsibleSection>
    </div>
  );
}
