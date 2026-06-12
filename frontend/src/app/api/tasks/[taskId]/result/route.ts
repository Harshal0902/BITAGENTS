import type { AgentResult } from "@bitagents/shared";
import { recordStatus, updateDb } from "@/server/db";
import { requirePublicKey, requireString } from "@/server/validation";

export const runtime = "nodejs";

export async function POST(request: Request, { params }: { params: { taskId: string } }) {
  try {
    const body = (await request.json()) as Record<string, unknown>;
    const providerWallet = requirePublicKey(body.providerWallet, "provider wallet");

    const task = await updateDb((db) => {
      const found = db.tasks.find((item) => item.id === params.taskId);
      if (!found) {
        throw new Error("task not found.");
      }
      if (found.assignedProviderWallet !== providerWallet) {
        throw new Error("provider wallet does not match assignment.");
      }
      if (found.status !== "computing" && found.status !== "assigned") {
        throw new Error(`task is ${found.status}, not computing.`);
      }

      if (body.error) {
        found.error = requireString(body.error, "error", 500);
        recordStatus(found, "failed", found.error);
        return found;
      }

      if (!body.result || typeof body.result !== "object") {
        throw new Error("result is required.");
      }

      found.result = body.result as AgentResult;
      recordStatus(found, "completed", "Provider worker submitted computation result.");
      return found;
    });

    return Response.json({ task });
  } catch (error) {
    return Response.json({ error: (error as Error).message }, { status: 400 });
  }
}
