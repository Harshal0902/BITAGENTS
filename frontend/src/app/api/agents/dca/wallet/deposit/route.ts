import { NextResponse } from "next/server";
import { proxyDcaDepositVerify } from "@/server/dcaAgentProxy";

export async function POST(request: Request) {
  let body: { signature?: string; user_wallet?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const signature = body.signature?.trim();
  const userWallet = body.user_wallet?.trim();
  if (!signature || !userWallet) {
    return NextResponse.json({ error: "signature and user_wallet are required" }, { status: 400 });
  }

  try {
    const res = await proxyDcaDepositVerify({ signature, user_wallet: userWallet });
    const data = await res.json();
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : data.error ?? "Verification failed";
      return NextResponse.json({ error: detail }, { status: res.status });
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "DCA agent API offline" }, { status: 503 });
  }
}
