const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

export interface ChatRequest {
  query: string;
  sessionId?: string;
  userId?: string;
  country?: string;
}

export interface ChatStreamHandlers {
  /** Fired once, as soon as the server assigns/confirms the session id. */
  onSession?: (info: { session_id: string; user_id: string | null }) => void;
  /** Fired for each chunk of the assistant's reply, in order. */
  onToken?: (content: string) => void;
}

/** Sends one conversation turn to POST /chat and streams the reply via SSE,
 * invoking `handlers` as events arrive. Resolves once the stream ends;
 * throws if the connection fails or the server reports an error event. */
export async function streamChatMessage(req: ChatRequest, handlers: ChatStreamHandlers): Promise<void> {
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

  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Chat request failed (${res.status}): ${detail}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex: number;
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      dispatchSseEvent(rawEvent, handlers);
    }
  }
}

/** Parses one "event: X\ndata: Y" block and invokes the matching handler. */
function dispatchSseEvent(rawEvent: string, handlers: ChatStreamHandlers): void {
  let eventName = "message";
  let dataText = "";
  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("event:")) eventName = line.slice("event:".length).trim();
    else if (line.startsWith("data:")) dataText += line.slice("data:".length).trim();
  }
  if (!dataText) return;

  const data = JSON.parse(dataText);
  switch (eventName) {
    case "session":
      handlers.onSession?.(data);
      break;
    case "token":
      handlers.onToken?.(data.content);
      break;
    case "error":
      throw new Error(data.message || "Chat stream failed");
  }
}

/** Flushes any pending long-term memory for a session via POST /chat/{session_id}/end. */
export async function endChatSession(sessionId: string, userId: string): Promise<void> {
  const url = new URL(`${API_BASE_URL}/chat/${sessionId}/end`);
  url.searchParams.set("user_id", userId);

  await fetch(url.toString(), { method: "POST" });
}
