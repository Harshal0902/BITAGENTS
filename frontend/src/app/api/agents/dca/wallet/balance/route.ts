import { NextResponse } from "next/server";
import { getAuthToken, proxyDcaWalletBalance } from "@/server/agentsApiProxy";

export async function GET(request: Request) {
  const authToken = getAuthToken(request);
  if (!authToken) {
    return NextResponse.json({ error: "Wallet sign-in required" }, { status: 401 });
  }

  try {
    const res = await proxyDcaWalletBalance(authToken);
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "DCA agent API offline" }, { status: 503 });
  }
}
