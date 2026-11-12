import { getVercelOidcToken } from "@vercel/oidc";

const postActions = new Set(["documents", "search", "ask", "login", "logout", "signup"]);

type Context = { params: Promise<{ action: string }> };

async function relay(request: Request, action: string) {
  const baseUrl = process.env.KNOWFLOW_API_URL ?? "http://127.0.0.1:8000";
  const headers = new Headers();
  for (const name of ["content-type", "cookie"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const options: RequestInit & { duplex: "half" } = {
    method: request.method,
    headers,
    body: request.body,
    duplex: "half",
    cache: "no-store",
    redirect: "error",
    signal: AbortSignal.timeout(120_000),
  };

  try {
    const url = new URL(action, baseUrl.replace(/\/?$/, "/"));
    const environment = process.env.VERCEL_ENV;
    if (
      (environment === "preview" || environment === "production")
      && url.protocol === "https:"
      && url.hostname.endsWith(".vercel.app")
    ) {
      headers.set("x-vercel-trusted-oidc-idp-token", await getVercelOidcToken());
    }
    const upstream = await fetch(url, options);
    if ([401, 403].includes(upstream.status) && !upstream.headers.get("content-type")?.includes("application/json")) {
      return Response.json(
        { detail: "Vercel deployment protection blocked the API request." },
        { status: 502 },
      );
    }
    const responseHeaders = new Headers({ "cache-control": "no-store" });
    const contentType = upstream.headers.get("content-type");
    if (contentType) responseHeaders.set("content-type", contentType);
    for (const cookie of upstream.headers.getSetCookie()) {
      responseHeaders.append("set-cookie", cookie);
    }
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return Response.json(
      { detail: "The KnowFlow API is unavailable. Check that the backend is running and try again." },
      { status: 502 },
    );
  }
}

export async function GET(request: Request, context: Context) {
  const { action } = await context.params;
  if (action !== "session") {
    return Response.json({ detail: "Unknown endpoint." }, { status: 404 });
  }
  return relay(request, action);
}

export async function POST(request: Request, context: Context) {
  const { action } = await context.params;
  if (!postActions.has(action)) {
    return Response.json({ detail: "Unknown endpoint." }, { status: 404 });
  }
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  const expectedOrigin = host ? `${new URL(request.url).protocol}//${host}` : new URL(request.url).origin;
  if (origin && origin !== expectedOrigin) {
    return Response.json({ detail: "Cross-origin request rejected." }, { status: 403 });
  }
  return relay(request, action);
}
