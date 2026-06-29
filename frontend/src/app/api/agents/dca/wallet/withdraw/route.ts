import { NextResponse } from "next/server";
import { getAuthToken, proxyDcaWithdraw } from "@/server/agentsApiProxy";

export async function POST(request: Request) {
  const authToken = getAuthToken(request);
  if (!authToken) {
    return NextResponse.json({ error: "Wallet sign-in required" }, { status: 401 });
  }

  let body: { token?: string; amount?: number };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const token = body.token?.trim();
  const amount = Number(body.amount);
  if (!token) {
    return NextResponse.json({ error: "token is required" }, { status: 400 });
  }
  if (!Number.isFinite(amount) || amount <= 0) {
    return NextResponse.json({ error: "amount must be a positive number" }, { status: 400 });
  }

  try {
    const res = await proxyDcaWithdraw({ token, amount }, authToken);
    let data: { detail?: string; error?: string };
    try {
      data = await res.json();
    } catch {
      return NextResponse.json(
        { error: `Withdrawal failed (HTTP ${res.status})` },
        { status: res.status >= 400 ? res.status : 502 }
      );
    }
    if (!res.ok) {
      const detail =
        typeof data.detail === "string" ? data.detail : data.error ?? "Withdrawal failed";
      return NextResponse.json({ error: detail }, { status: res.status });
    }
    return NextResponse.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Withdrawal request failed";
    const offline =
      message.includes("fetch failed") ||
      message.includes("ECONNREFUSED") ||
      message.includes("network");
    return NextResponse.json(
      { error: offline ? "DCA agent API offline" : message },
      { status: 503 }
    );
  }
}
