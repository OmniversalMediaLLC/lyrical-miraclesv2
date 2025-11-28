interface Env {
  VECTORIZE_INDEX: VectorizeIndex;
  AI: Ai;
}

type ChunkPayload = {
  id: string;
  text: string;
  metadata?: Record<string, unknown>;
};

const EMBED_MODEL = "@cf/baai/bge-base-en-v1.5";

async function handleIngest(request: Request, env: Env): Promise<Response> {
  let chunks: ChunkPayload[];
  try {
    chunks = await request.json<ChunkPayload[]>();
  } catch (error) {
    return new Response(
      JSON.stringify({ ok: false, error: "Invalid JSON payload" }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
  }

  if (!Array.isArray(chunks) || chunks.length === 0) {
    return new Response(
      JSON.stringify({ ok: false, error: "Payload must be a non-empty array" }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
  }

  let processed = 0;

  try {
    for (const chunk of chunks) {
      if (!chunk.id || !chunk.text?.trim()) {
        continue;
      }
      const embeddingResponse = await env.AI.run(EMBED_MODEL, { text: chunk.text });
      const values = Array.isArray(embeddingResponse?.data)
        ? (embeddingResponse.data[0] as number[])
        : undefined;
      if (!values || values.length === 0) {
        throw new Error("Missing embedding values in AI response");
      }
      await env.VECTORIZE_INDEX.upsert([
        {
          id: chunk.id,
          values,
          metadata: chunk.metadata ?? {},
        },
      ]);
      processed += 1;
    }
  } catch (error) {
    console.error("Vectorize ingest failed", error);
    return new Response(
      JSON.stringify({ ok: false, error: (error as Error).message ?? "Unknown error" }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }

  return new Response(JSON.stringify({ ok: true, count: processed }), {
    headers: { "content-type": "application/json" },
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/ingest" && request.method === "POST") {
      return handleIngest(request, env);
    }
    return new Response("Not Found", { status: 404 });
  },
};
