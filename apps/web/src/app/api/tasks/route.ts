import { nowIso, type AgentTask } from "@bitagents/shared";
import { randomUUID } from "node:crypto";
import { providerPriceOrDefault, readDb, updateDb } from "@/server/db";
import { parseAgentInput, parseAgentType, requirePublicKey } from "@/server/validation";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const db = await readDb();
  const url = new URL(request.url);
  const requesterWallet = url.searchParams.get("requesterWallet");
  const assignedProviderWallet = url.searchParams.get("assignedProviderWallet");
  const status = url.searchParams.get("status");

  const tasks = db.tasks
    .filter((task) => !requesterWallet || task.requesterWallet === requesterWallet)
    .filter((task) => !assignedProviderWallet || task.assignedProviderWallet === assignedProviderWallet)
    .filter((task) => !status || task.status === status)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));

  return Response.json({ tasks });
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as Record<string, unknown>;
    const type = parseAgentType(body.type);
    const input = parseAgentInput(type, body.input);
    const requesterWallet = requirePublicKey(body.requesterWallet, "requester wallet");

    const task = await updateDb<AgentTask>((db) => {
      const cheapestOnlineProvider = db.providers
        .filter((provider) => provider.status === "online")
        .sort((a, b) => a.pricePerTaskSol - b.pricePerTaskSol)[0];
      const at = nowIso();
      const created: AgentTask = {
        id: randomUUID(),
        type,
        input,
        requesterWallet,
        status: "created",
        priceSol: providerPriceOrDefault(cheapestOnlineProvider),
        createdAt: at,
        updatedAt: at,
        history: [{ status: "created", at, note: "Task created and awaiting devnet payment." }]
      };
      db.tasks.push(created);
      return created;
    });

    return Response.json({ task });
  } catch (error) {
    return Response.json({ error: (error as Error).message }, { status: 400 });
  }
}
