import { NextResponse } from "next/server";
import { proxyDcaAuthChallenge } from "@/server/agentsApiProxy";

export async function GET(request: Request) {
  const userWallet = new URL(request.url).searchParams.get("user_wallet")?.trim();
  if (!userWallet) {
    return NextResponse.json({ error: "user_wallet is required" }, { status: 400 });
  }

  try {
    const res = await proxyDcaAuthChallenge(userWallet);
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "DCA agent API offline" }, { status: 503 });
  }
}
