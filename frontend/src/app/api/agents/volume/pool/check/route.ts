import { NextRequest, NextResponse } from "next/server";
import { proxyVolumePoolCheck } from "@/server/agentsApiProxy";

export async function GET(request: NextRequest) {
  const baseMint = request.nextUrl.searchParams.get("base_mint")?.trim();
  if (!baseMint) {
    return NextResponse.json({ error: "base_mint is required" }, { status: 400 });
  }
  const quoteMint = request.nextUrl.searchParams.get("quote_mint")?.trim();
  const res = await proxyVolumePoolCheck(baseMint, quoteMint);
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
