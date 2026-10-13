"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { endChatSession, sendChatMessage } from "@/lib/api";
import { getOrCreateUserId } from "@/lib/user";
import { cn } from "@/lib/utils";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function ChatClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const country = searchParams.get("country") ?? "";
  const visit = searchParams.get("v") ?? "";

  const [userId, setUserId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [ending, setEnding] = useState(false);
  const [ended, setEnded] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!country) {
      router.replace("/");
      return;
    }
    // Next's router cache can reuse this component across visits to /chat (e.g. after
    // "End session" takes you home and you click "Start chatting" again), which would
    // otherwise leave stale messages/sessionId around from the previous conversation.
    // The "v" param is a fresh value per visit, so resetting here whenever it changes
    // guarantees every visit starts clean regardless of component reuse. Also reads/writes
    // localStorage for the user id, so this must run client-side after mount, not during render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMessages([]);
    setSessionId(null);
    setInput("");
    setEnded(false);
    setUserId(getOrCreateUserId());
  }, [country, visit, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const MIN_QUERY_LENGTH = 10;

  async function handleSend() {
    const query = input.trim();
    if (query.length < MIN_QUERY_LENGTH || sending || !userId || ended) return;

    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setInput("");
    setSending(true);

    try {
      const res = await sendChatMessage({
        query,
        sessionId: sessionId ?? undefined,
        userId,
        country,
      });
      setSessionId(res.session_id);
      setMessages((prev) => [...prev, { role: "assistant", content: res.response }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, something went wrong reaching the server. Please try again.",
        },
      ]);
      console.error(err);
    } finally {
      setSending(false);
    }
  }

  async function handleEndChat() {
    if (ended || ending) return;

    setEnding(true);
    try {
      if (sessionId && userId) {
        await endChatSession(sessionId, userId);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setEnding(false);
      setEnded(true);
    }
  }

  if (!country) return null;

  return (
    <main className="mx-auto flex h-dvh w-full max-w-2xl flex-col p-4">
      <header className="flex items-center justify-between pb-3">
        <div>
          <h1 className="text-lg font-semibold">Learning about {country}</h1>
          <p className="text-sm text-muted-foreground">
            Ask anything — history, food, culture, nature, and more.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleEndChat} disabled={ending || ended}>
            {ended ? "Chat ended" : ending ? "Ending…" : "End chat"}
          </Button>
          {ended && (
            <Button size="sm" onClick={() => router.push("/")}>
              Start new chat
            </Button>
          )}
        </div>
      </header>
      <Separator />

      <ScrollArea className="my-3 min-h-0 flex-1 rounded-lg border p-4">
        <div className="flex flex-col gap-3">
          {messages.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Say hello, or ask your first question about {country}!
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={cn(
                "max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap",
                m.role === "user"
                  ? "self-end bg-primary text-primary-foreground"
                  : "self-start bg-muted"
              )}
            >
              {m.content}
            </div>
          ))}
          {sending && (
            <div className="self-start rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
              Thinking…
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      <form
        className="flex flex-col gap-1"
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
      >
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={ended ? "This chat has ended" : "Ask a question..."}
            disabled={sending || !userId || ended}
            autoFocus
          />
          <Button
            type="submit"
            disabled={sending || input.trim().length < MIN_QUERY_LENGTH || !userId || ended}
          >
            Send
          </Button>
        </div>
        {!ended && input.trim().length > 0 && input.trim().length < MIN_QUERY_LENGTH && (
          <p className="text-xs text-muted-foreground">
            Keep going — questions need at least {MIN_QUERY_LENGTH} characters.
          </p>
        )}
        {ended && (
          <p className="text-xs text-muted-foreground">This chat has ended.</p>
        )}
      </form>
    </main>
  );
}
