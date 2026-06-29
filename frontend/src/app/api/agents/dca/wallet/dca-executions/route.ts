import { NextRequest, NextResponse } from "next/server";
import { getAuthToken, proxyDcaExecutions } from "@/server/agentsApiProxy";

export async function GET(request: NextRequest) {
  const authToken = getAuthToken(request);
  if (!authToken) {
    return NextResponse.json({ error: "Missing session token" }, { status: 401 });
  }
  const limit = Number(request.nextUrl.searchParams.get("limit") ?? "100");
  const res = await proxyDcaExecutions(authToken, Number.isFinite(limit) ? limit : 100);
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
