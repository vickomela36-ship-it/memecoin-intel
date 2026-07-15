import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Upstash/Vercel KV REST — single-command endpoint.
const KV_URL = process.env.KV_REST_API_URL;
const KV_TOKEN = process.env.KV_REST_API_TOKEN;

async function kv(cmd: (string | number)[]): Promise<unknown> {
  const res = await fetch(KV_URL!, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${KV_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(cmd),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`KV ${res.status}`);
  const data = await res.json();
  return data?.result ?? null;
}

// Sync IDs are client-generated 128-bit+ random strings. The ID is the
// only credential — without it, keys are unguessable. Single-user tool.
const ID_RE = /^[A-Za-z0-9-]{20,80}$/;
const MAX_BYTES = 400_000;

export async function GET(req: NextRequest) {
  if (!KV_URL || !KV_TOKEN) {
    return NextResponse.json({ error: "kv not configured" }, { status: 503 });
  }
  const id = new URL(req.url).searchParams.get("id");
  if (!id || !ID_RE.test(id)) {
    return NextResponse.json({ error: "bad id" }, { status: 400 });
  }
  try {
    const raw = (await kv(["GET", `mi:snap:${id}`])) as string | null;
    return NextResponse.json({ snapshot: raw ? JSON.parse(raw) : null });
  } catch {
    return NextResponse.json({ error: "kv read failed" }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  if (!KV_URL || !KV_TOKEN) {
    return NextResponse.json({ error: "kv not configured" }, { status: 503 });
  }
  try {
    const body = await req.json();
    const id = String(body?.id ?? "");
    if (!ID_RE.test(id)) {
      return NextResponse.json({ error: "bad id" }, { status: 400 });
    }
    const str = JSON.stringify(body?.snapshot ?? null);
    if (!str || str === "null" || str.length > MAX_BYTES) {
      return NextResponse.json({ error: "bad snapshot" }, { status: 400 });
    }
    await kv(["SET", `mi:snap:${id}`, str]);
    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ error: "kv write failed" }, { status: 502 });
  }
}
