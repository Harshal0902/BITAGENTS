import { nowIso } from "@bitagents/shared";
import { randomUUID } from "node:crypto";
import { updateDb } from "@/server/db";
import { parseComputeType, parsePriceSol, parseProviderStatus, requirePublicKey, requireString } from "@/server/validation";

export const runtime = "nodejs";

export async function GET() {
  const providers = await updateDb((db) => db.providers);
  return Response.json({ providers });
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as Record<string, unknown>;
    const walletAddress = requirePublicKey(body.walletAddress, "wallet address");
    const name = requireString(body.name, "provider name", 80);
    const computeType = parseComputeType(body.computeType);
    const pricePerTaskSol = parsePriceSol(body.pricePerTaskSol);
    const status = parseProviderStatus(body.status);

    const provider = await updateDb((db) => {
      const existing = db.providers.find((item) => item.walletAddress === walletAddress);
      const at = nowIso();

      if (existing) {
        existing.name = name;
        existing.computeType = computeType;
        existing.pricePerTaskSol = pricePerTaskSol;
        existing.status = status;
        existing.updatedAt = at;
        return existing;
      }

      const created = {
        id: randomUUID(),
        name,
        walletAddress,
        computeType,
        pricePerTaskSol,
        status,
        createdAt: at,
        updatedAt: at
      };
      db.providers.push(created);
      return created;
    });

    return Response.json({ provider });
  } catch (error) {
    return Response.json({ error: (error as Error).message }, { status: 400 });
  }
}
