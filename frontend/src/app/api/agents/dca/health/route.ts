import { NextResponse } from "next/server";
import { proxyDcaHealth } from "@/server/agentsApiProxy";

export async function GET() {
  try {
    const res = await proxyDcaHealth();
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { status: "offline", detail: "DCA agent API is not running. Start it with: cd agent/new && python dca_api.py" },
      { status: 503 }
    );
  }
}
