const SOLANA_RPC_URL = process.env.SOLANA_RPC_URL?.trim();

export function getServerSolanaRpcUrl(): string {
  if (!SOLANA_RPC_URL) {
    throw new Error("SOLANA_RPC_URL is not configured.");
  }
  return SOLANA_RPC_URL;
}

export async function forwardSolanaRpcRequest(body: string): Promise<Response> {
  if (!SOLANA_RPC_URL) {
    return Response.json(
      {
        jsonrpc: "2.0",
        error: { code: -32603, message: "SOLANA_RPC_URL is not configured on the server." },
        id: null,
      },
      { status: 503 }
    );
  }

  if (!body.trim()) {
    return Response.json({ error: "Empty RPC request body" }, { status: 400 });
  }

  try {
    JSON.parse(body);
  } catch {
    return Response.json({ error: "Invalid JSON-RPC body" }, { status: 400 });
  }

  try {
    const upstream = await fetch(SOLANA_RPC_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
    });
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return Response.json(
      {
        jsonrpc: "2.0",
        error: { code: -32603, message: "Failed to reach Solana RPC upstream." },
        id: null,
      },
      { status: 502 }
    );
  }
}
