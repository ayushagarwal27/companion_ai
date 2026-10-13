const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

export interface ChatRequest {
  query: string;
  sessionId?: string;
  userId?: string;
  country?: string;
}

export interface ChatResponse {
  session_id: string;
  user_id: string | null;
  response: string;
}

/** Sends one conversation turn to POST /chat. */
export async function sendChatMessage(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: req.query,
      session_id: req.sessionId ?? null,
      user_id: req.userId ?? null,
      country: req.country ?? null,
    }),
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Chat request failed (${res.status}): ${detail}`);
  }

  return res.json();
}

/** Flushes any pending long-term memory for a session via POST /chat/{session_id}/end. */
export async function endChatSession(sessionId: string, userId: string): Promise<void> {
  const url = new URL(`${API_BASE_URL}/chat/${sessionId}/end`);
  url.searchParams.set("user_id", userId);

  await fetch(url.toString(), { method: "POST" });
}
