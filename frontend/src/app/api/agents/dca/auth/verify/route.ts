import { NextResponse } from "next/server";
import { proxyDcaAuthVerify } from "@/server/dcaAgentProxy";

export async function POST(request: Request) {
  let body: { user_wallet?: string; message?: string; signature?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const userWallet = body.user_wallet?.trim();
  const message = body.message?.trim();
  const signature = body.signature?.trim();
  if (!userWallet || !message || !signature) {
    return NextResponse.json({ error: "user_wallet, message, and signature are required" }, { status: 400 });
  }

  try {
    const res = await proxyDcaAuthVerify({ user_wallet: userWallet, message, signature });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "DCA agent API offline" }, { status: 503 });
  }
}
