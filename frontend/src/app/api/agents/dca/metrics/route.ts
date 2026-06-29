import { NextResponse } from "next/server";
import { proxyDcaMetrics } from "@/server/agentsApiProxy";

export async function GET() {
  const res = await proxyDcaMetrics(false);
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
