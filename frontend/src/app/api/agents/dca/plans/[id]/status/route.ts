import { NextRequest, NextResponse } from "next/server";
import { getAuthToken, proxyDcaPlanStatus } from "@/server/agentsApiProxy";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const authToken = getAuthToken(request);
  if (!authToken) {
    return NextResponse.json({ error: "Missing session token" }, { status: 401 });
  }
  const { id } = await params;
  let body: { action?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  if (!body.action?.trim()) {
    return NextResponse.json({ error: "action is required" }, { status: 400 });
  }
  const res = await proxyDcaPlanStatus(id, body.action.trim(), authToken);
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
