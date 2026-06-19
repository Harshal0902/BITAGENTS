import { forwardSolanaRpcRequest } from "@/server/solanaRpcProxy";

export async function POST(request: Request) {
  const body = await request.text();
  return forwardSolanaRpcRequest(body);
}
