const actions = new Set(["documents", "ask"]);

export async function POST(request: Request, context: { params: Promise<{ action: string }> }) {
  const { action } = await context.params;
  if (!actions.has(action)) {
    return Response.json({ detail: "Unknown endpoint." }, { status: 404 });
  }

  const baseUrl = process.env.KNOWFLOW_API_URL ?? "http://127.0.0.1:8000";
  const contentType = request.headers.get("content-type") ?? "application/json";
  const options: RequestInit & { duplex: "half" } = {
    method: "POST",
    headers: { "content-type": contentType },
    body: request.body,
    duplex: "half",
    signal: AbortSignal.timeout(120_000),
  };

  try {
    const upstream = await fetch(new URL(action, baseUrl.replace(/\/?$/, "/")), options);
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json(
      { detail: "The KnowFlow API is unavailable. Check that the backend is running and try again." },
      { status: 502 },
    );
  }
}
