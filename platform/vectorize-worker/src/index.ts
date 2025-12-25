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

function extractEmbedding(response: unknown): number[] | undefined {
  if (!response || typeof response !== "object") {
    return undefined;
  }
  const payload = response as { data?: unknown; result?: { data?: unknown } };
  const data = (Array.isArray(payload.data)
    ? payload.data
    : Array.isArray(payload.result?.data)
    ? payload.result?.data
    : undefined) as unknown[] | undefined;
  if (!data || data.length === 0) {
    return undefined;
  }
  const first = data[0] as unknown;
  if (Array.isArray(first)) {
    return Array.from(first as number[]);
  }
  if (ArrayBuffer.isView(first)) {
    return Array.from(first as ArrayLike<number>);
  }
  if (
    first &&
    typeof first === "object" &&
    Array.isArray((first as { embedding?: unknown }).embedding)
  ) {
    return ((first as { embedding: number[] }).embedding ?? []).slice();
  }
  return undefined;
}

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
      const values = extractEmbedding(embeddingResponse);
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

async function handleSearch(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const query = url.searchParams.get("q")?.trim();
  if (!query) {
    return new Response(
      JSON.stringify({ ok: false, error: "Missing query param 'q'" }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
  }

  const topK = Math.min(
    Math.max(Number(url.searchParams.get("k") ?? url.searchParams.get("topK") ?? 5) || 5, 1),
    20,
  );

  try {
    const embeddingResponse = await env.AI.run(EMBED_MODEL, { text: query });
    const vector = extractEmbedding(embeddingResponse);
    if (!vector || vector.length === 0) {
      throw new Error("Failed to generate embedding for query");
    }

    const results = await env.VECTORIZE_INDEX.query(vector, {
      topK,
      includeVectors: false,
      returnMetadata: true,
    });

    return new Response(JSON.stringify({ ok: true, matches: results.matches ?? results }), {
      headers: { "content-type": "application/json" },
    });
  } catch (error) {
    console.error("Vectorize search failed", error);
    return new Response(
      JSON.stringify({ ok: false, error: (error as Error).message ?? "Unknown error" }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/ingest" && request.method === "POST") {
      return handleIngest(request, env);
    }
    if (url.pathname === "/search" && request.method === "GET") {
      return handleSearch(request, env);
    }
    return new Response("Not Found", { status: 404 });
  },
};
