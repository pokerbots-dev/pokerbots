export interface Env {
  SOLANA_CLUSTER: "devnet" | "mainnet-beta";
  SOLANA_RPC_URL?: string; // secret; contains the Helius API key, never log or return it
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return Response.json({
        ok: true,
        cluster: env.SOLANA_CLUSTER,
        rpc_configured: Boolean(env.SOLANA_RPC_URL),
      });
    }
    return new Response("Not found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;
