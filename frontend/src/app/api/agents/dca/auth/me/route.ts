import { NextResponse } from "next/server";
import { getAuthToken, proxyDcaAuthMe } from "@/server/dcaAgentProxy";

export async function GET(request: Request) {
  const token = getAuthToken(request);
  if (!token) {
    return NextResponse.json({ error: "Missing session token" }, { status: 401 });
  }

  try {
    const res = await proxyDcaAuthMe(token);
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "DCA agent API offline" }, { status: 503 });
  }
}
