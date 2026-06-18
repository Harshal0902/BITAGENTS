import { NextResponse } from "next/server";
import { proxyDcaChat } from "@/server/dcaAgentProxy";

export async function POST(request: Request) {
  let body: { message?: string; session_id?: string; user_wallet?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const message = body.message?.trim();
  if (!message) {
    return NextResponse.json({ error: "message is required" }, { status: 400 });
  }

  try {
    const res = await proxyDcaChat({
      message,
      session_id: body.session_id,
      user_wallet: body.user_wallet,
    });
    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json(data, { status: res.status });
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      {
        error: "Cannot reach DCA agent API",
        detail: "Start the agent locally: cd agent/new && python dca_api.py",
      },
      { status: 503 }
    );
  }
}
