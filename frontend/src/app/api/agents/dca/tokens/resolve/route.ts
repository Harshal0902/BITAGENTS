import { NextRequest, NextResponse } from "next/server";
import { proxyDcaResolveToken } from "@/server/agentsApiProxy";

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.get("query")?.trim();
  if (!query) {
    return NextResponse.json({ error: "query is required" }, { status: 400 });
  }

  try {
    const res = await proxyDcaResolveToken(query);
    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json(
        { error: typeof data.detail === "string" ? data.detail : "Token resolve failed" },
        { status: res.status }
      );
    }
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "DCA agent API offline" }, { status: 503 });
  }
}
