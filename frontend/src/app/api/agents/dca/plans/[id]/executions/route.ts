import { NextRequest, NextResponse } from "next/server";
import { getAuthToken, proxyDcaPlanExecutions } from "@/server/agentsApiProxy";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const authToken = getAuthToken(_request);
  if (!authToken) {
    return NextResponse.json({ error: "Wallet sign-in required" }, { status: 401 });
  }

  const { id } = await params;

  try {
    const res = await proxyDcaPlanExecutions(id, authToken);
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "DCA agent API offline" }, { status: 503 });
  }
}
