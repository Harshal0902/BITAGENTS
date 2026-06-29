import { NextResponse } from "next/server";
import { proxyDcaWalletAgent } from "@/server/agentsApiProxy";

export async function GET() {
  try {
    const res = await proxyDcaWalletAgent();
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "DCA agent API offline" }, { status: 503 });
  }
}
