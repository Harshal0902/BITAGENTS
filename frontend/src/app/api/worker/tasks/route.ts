import { readDb } from "@/server/db";
import { requirePublicKey } from "@/server/validation";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const providerWallet = requirePublicKey(url.searchParams.get("providerWallet"), "provider wallet");
    const db = await readDb();
    const tasks = db.tasks
      .filter((task) => task.assignedProviderWallet === providerWallet && task.status === "assigned")
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt));

    return Response.json({ tasks });
  } catch (error) {
    return Response.json({ error: (error as Error).message }, { status: 400 });
  }
}
