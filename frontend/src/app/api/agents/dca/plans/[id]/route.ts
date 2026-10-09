import { NextRequest, NextResponse } from "next/server";
import { getAuthToken, proxyDcaUpdatePlan } from "@/server/agentsApiProxy";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const authToken = getAuthToken(request);
  if (!authToken) {
    return NextResponse.json({ error: "Wallet sign-in required" }, { status: 401 });
  }

  const { id } = await params;
  let body: {
    amount_per_buy?: number;
    interval?: string;
    max_executions?: number | null;
    total_budget?: number | null;
    slippage_bps?: number;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  try {
    const res = await proxyDcaUpdatePlan(id, body, authToken);
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "DCA agent API offline" }, { status: 503 });
  }
}
