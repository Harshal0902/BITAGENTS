import { NextResponse } from "next/server";
import { proxyHedgeFundWalletAgent } from "@/server/agentsApiProxy";

export async function GET() {
  try {
    const res = await proxyHedgeFundWalletAgent();
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Hedge Fund agent API offline" }, { status: 503 });
  }
}
