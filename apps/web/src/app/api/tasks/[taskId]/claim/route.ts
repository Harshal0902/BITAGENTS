import { recordStatus, updateDb } from "@/server/db";
import { requirePublicKey } from "@/server/validation";

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
      if (found.status !== "assigned") {
        throw new Error(`task is ${found.status}, not assigned.`);
      }
      if (found.assignedProviderWallet !== providerWallet) {
        throw new Error("provider wallet does not match assignment.");
      }

      recordStatus(found, "computing", "Provider worker claimed the task.");
      return found;
    });

    return Response.json({ task });
  } catch (error) {
    return Response.json({ error: (error as Error).message }, { status: 400 });
  }
}
