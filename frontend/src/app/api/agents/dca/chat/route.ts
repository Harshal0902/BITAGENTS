import { NextResponse } from "next/server";
import { getAuthToken, proxyDcaChat } from "@/server/dcaAgentProxy";

export async function POST(request: Request) {
  const authToken = getAuthToken(request);
  if (!authToken) {
    return NextResponse.json({ error: "Wallet sign-in required" }, { status: 401 });
  }

  let body: { message?: string; session_id?: string };
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
    const res = await proxyDcaChat({ message, session_id: body.session_id }, authToken);
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
