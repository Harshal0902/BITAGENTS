import { NextResponse } from "next/server";
import { proxyDcaHealth } from "@/server/agentsApiProxy";

export async function GET(request: Request) {
  const pingLlm = new URL(request.url).searchParams.get("ping_llm") === "true";
  try {
    const res = await proxyDcaHealth(pingLlm);
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { status: "offline", detail: "DCA agent API is not running. Start it with: cd agent/new && python agents_api.py" },
      { status: 503 }
    );
  }
}
