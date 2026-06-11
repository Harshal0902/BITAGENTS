import { recordStatus, updateDb } from "@/server/db";
import { sendServerPayout } from "@/server/payout";
import { requireString } from "@/server/validation";

export const runtime = "nodejs";

export async function POST(request: Request, { params }: { params: { taskId: string } }) {
  try {
    const body = (await request.json()) as Record<string, unknown>;
    let signature = typeof body.payoutSignature === "string" ? body.payoutSignature.trim() : "";

    const task = await updateDb(async (db) => {
      const found = db.tasks.find((item) => item.id === params.taskId);
      if (!found) {
        throw new Error("task not found.");
      }
      if (found.status !== "completed") {
        throw new Error(`task is ${found.status}, not completed.`);
      }
      if (!found.assignedProviderWallet) {
        throw new Error("task has no assigned provider wallet.");
      }

      if (!signature && body.serverPayout === true) {
        signature = await sendServerPayout(found.assignedProviderWallet, found.priceSol);
      }

      found.payoutSignature = requireString(signature, "payout signature", 120);
      recordStatus(found, "paid_out", "Provider payout signature recorded.");
      return found;
    });

    return Response.json({ task });
  } catch (error) {
    return Response.json({ error: (error as Error).message }, { status: 400 });
  }
}
