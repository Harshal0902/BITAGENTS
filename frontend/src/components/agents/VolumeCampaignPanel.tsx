"use client";

import { useCallback, useEffect, useState } from "react";
import { Panel } from "@/components/AppShell";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { explorerUrlForSignature } from "@/lib/dcaActionResults";
import {
  fetchVolumeCampaignExecutions,
  fetchVolumeCampaigns,
  updateVolumeCampaignStatus,
  type VolumeCampaignSummary,
} from "@/lib/volumePlanClient";

function statusClass(status: string) {
  if (status === "active") return "text-signal";
  if (status === "paused" || status === "provisioning") return "text-warn";
  return "text-muted-foreground";
}

function formatTime(iso?: string | null) {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function VolumeCampaignPanel({
  authToken,
  cluster,
  refreshTick = 0,
  onCampaignChange,
}: {
  authToken: string;
  cluster?: string;
  refreshTick?: number;
  onCampaignChange?: () => void;
}) {
  const [campaigns, setCampaigns] = useState<VolumeCampaignSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<{
    id: string;
    action: "pause" | "resume" | "cancel";
    name: string;
  } | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [executions, setExecutions] = useState<Record<string, unknown[]>>({});

  const loadCampaigns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchVolumeCampaigns(authToken);
      setCampaigns(data.campaigns ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load campaigns");
      setCampaigns([]);
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  useEffect(() => {
    void loadCampaigns();
  }, [loadCampaigns, refreshTick]);

  async function runStatusAction() {
    if (!pendingAction) return;
    setBusyId(pendingAction.id);
    try {
      await updateVolumeCampaignStatus(pendingAction.id, pendingAction.action, authToken);
      await loadCampaigns();
      onCampaignChange?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusyId(null);
      setPendingAction(null);
    }
  }

  async function toggleExecutions(campaign: VolumeCampaignSummary) {
    if (expandedId === campaign.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(campaign.id);
    if (executions[campaign.id]) return;
    try {
      const data = await fetchVolumeCampaignExecutions(campaign.id, authToken);
      setExecutions((prev) => ({ ...prev, [campaign.id]: data.executions ?? [] }));
    } catch {
      setExecutions((prev) => ({ ...prev, [campaign.id]: [] }));
    }
  }

  return (
    <Panel title="Volume campaigns">
      <div className="space-y-3">
        {loading && <p className="font-mono text-[11px] text-muted-foreground">Loading campaigns…</p>}
        {error && <p className="font-mono text-[11px] text-warn">{error}</p>}
        {!loading && campaigns.length === 0 && (
          <p className="font-mono text-[11px] text-muted-foreground">
            No campaigns yet. Create one above after depositing token + SOL.
          </p>
        )}

        {campaigns.map((campaign) => (
          <div key={campaign.id} className="border border-grid bg-background/60 p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-mono text-[12px] text-foreground">{campaign.name}</p>
                <p className="font-mono text-[10px] text-muted-foreground">
                  <code>{campaign.id}</code> · {campaign.base_token}/{campaign.quote_token} ·{" "}
                  <span className={statusClass(campaign.status)}>{campaign.status}</span>
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {campaign.status === "active" && (
                  <button
                    type="button"
                    className="border border-grid px-2 py-1 font-mono text-[10px] uppercase"
                    disabled={busyId === campaign.id}
                    onClick={() =>
                      setPendingAction({ id: campaign.id, action: "pause", name: campaign.name })
                    }
                  >
                    Pause
                  </button>
                )}
                {campaign.status === "paused" && (
                  <button
                    type="button"
                    className="border border-signal px-2 py-1 font-mono text-[10px] uppercase text-signal"
                    disabled={busyId === campaign.id}
                    onClick={() =>
                      setPendingAction({ id: campaign.id, action: "resume", name: campaign.name })
                    }
                  >
                    Resume
                  </button>
                )}
                {(campaign.status === "active" || campaign.status === "paused" || campaign.status === "provisioning") && (
                  <button
                    type="button"
                    className="border border-warn px-2 py-1 font-mono text-[10px] uppercase text-warn"
                    disabled={busyId === campaign.id}
                    onClick={() =>
                      setPendingAction({ id: campaign.id, action: "cancel", name: campaign.name })
                    }
                  >
                    Cancel
                  </button>
                )}
                <button
                  type="button"
                  className="border border-grid px-2 py-1 font-mono text-[10px] uppercase"
                  onClick={() => void toggleExecutions(campaign)}
                >
                  {expandedId === campaign.id ? "Hide" : "History"}
                </button>
              </div>
            </div>

            <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[10px] sm:grid-cols-4">
              <div>
                <dt className="text-muted-foreground">Trade / leg</dt>
                <dd>{campaign.trade_amount} {campaign.quote_token}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Cycles</dt>
                <dd>
                  {campaign.executions_count}/{campaign.max_executions}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Interval</dt>
                <dd>{campaign.interval}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Pool</dt>
                <dd>{campaign.pool_address ? "reused" : campaign.pool_exists ? "ready" : "pending"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Spent</dt>
                <dd>
                  {campaign.spent_so_far} / {campaign.total_budget ?? "∞"} {campaign.quote_token}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Next run</dt>
                <dd>{formatTime(campaign.next_execution_at)}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted-foreground">Fee</dt>
                <dd>0.25% per buy + sell leg</dd>
              </div>
            </dl>

            {expandedId === campaign.id && (
              <div className="mt-3 max-h-48 space-y-2 overflow-y-auto border-t border-grid pt-3">
                {(executions[campaign.id] ?? []).length === 0 ? (
                  <p className="font-mono text-[10px] text-muted-foreground">No cycles recorded yet.</p>
                ) : (
                  (executions[campaign.id] ?? []).map((entry, index) => {
                    const row = entry as {
                      cycle?: number;
                      at?: string;
                      buy?: { signature?: string };
                      sell?: { signature?: string };
                    };
                    return (
                      <div key={`${row.at}-${index}`} className="font-mono text-[10px] text-muted-foreground">
                        Cycle {row.cycle ?? index + 1} · {formatTime(row.at)}
                        {row.buy?.signature && (
                          <a
                            href={explorerUrlForSignature(row.buy.signature, cluster)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-2 text-signal"
                          >
                            buy ↗
                          </a>
                        )}
                        {row.sell?.signature && (
                          <a
                            href={explorerUrlForSignature(row.sell.signature, cluster)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-2 text-signal"
                          >
                            sell ↗
                          </a>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <ConfirmDialog
        open={Boolean(pendingAction)}
        onOpenChange={(open) => !open && setPendingAction(null)}
        title={`${pendingAction?.action ?? "Update"} campaign`}
        description={
          pendingAction
            ? `Apply "${pendingAction.action}" to ${pendingAction.name}?`
            : undefined
        }
        confirmLabel={pendingAction?.action ?? "Confirm"}
        onConfirm={() => void runStatusAction()}
      />
    </Panel>
  );
}
