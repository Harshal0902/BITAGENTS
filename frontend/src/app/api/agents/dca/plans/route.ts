import { NextRequest, NextResponse } from "next/server";
import { getAuthToken, proxyDcaPlans } from "@/server/agentsApiProxy";

export async function GET(request: NextRequest) {
  const authToken = getAuthToken(request);
  if (!authToken) {
    return NextResponse.json({ error: "Missing session token" }, { status: 401 });
  }
  const activeOnly = request.nextUrl.searchParams.get("active_only") === "true";
  const status = request.nextUrl.searchParams.get("status") ?? undefined;
  const res = await proxyDcaPlans(authToken, { active_only: activeOnly, status });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
