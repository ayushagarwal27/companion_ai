"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Lightbulb, Send, User } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { endChatSession, streamChatMessage } from "@/lib/api";
import { COUNTRY_FLAGS } from "@/lib/countries";
import { getOrCreateUserId } from "@/lib/user";
import { cn } from "@/lib/utils";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  time: number;
}

const QUICK_IDEAS = [
  "What's the food like there?",
  "Tell me a fun fact!",
  "What's the culture like?",
  "Any famous landmarks?",
];

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

/** Keeps the assistant's markdown reply visually consistent with the rest of the
 * (compact, hand-styled) chat UI instead of browser-default element spacing. */
const markdownComponents: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-extrabold">{children}</strong>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-4 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-4 last:mb-0">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-2">
      {children}
    </a>
  ),
  code: ({ children }) => <code className="rounded bg-surface-low px-1 py-0.5 text-xs">{children}</code>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-ink/40 pl-2 italic">{children}</blockquote>
  ),
};

export function ChatClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const country = searchParams.get("country") ?? "";
  const visit = searchParams.get("v") ?? "";
  const flag = COUNTRY_FLAGS[country] ?? "🌍";

  const [userId, setUserId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [ending, setEnding] = useState(false);
  const [ended, setEnded] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
  }, [messages, sending]);

  const MIN_QUERY_LENGTH = 10;
  const trimmedLength = input.trim().length;
  const isTooShort = trimmedLength > 0 && trimmedLength < MIN_QUERY_LENGTH;
  const lastMessage = messages[messages.length - 1];
  // True while waiting on the first chunk of a reply - once streaming starts,
  // the growing assistant bubble (role "assistant") replaces these dots.
  const awaitingResponse = sending && lastMessage?.role === "user";

  async function handleSend() {
    const query = input.trim();
    if (query.length < MIN_QUERY_LENGTH || sending || !userId || ended) return;

    setMessages((prev) => [...prev, { role: "user", content: query, time: Date.now() }]);
    setInput("");
    setSending(true);

    // Accumulated outside the setState updater: React 18 Strict Mode invokes
    // updater functions twice to catch impurities, so mutating state here
    // (rather than inside the updater) keeps each setMessages call pure -
    // both invocations read the same already-computed values.
    let assistantContent = "";
    let assistantStarted = false;

    try {
      await streamChatMessage(
        { query, sessionId: sessionId ?? undefined, userId, country },
        {
          onSession: (res) => setSessionId(res.session_id),
          onToken: (token) => {
            const isFirstToken = !assistantStarted;
            assistantStarted = true;
            assistantContent += token;

            setMessages((prev) => {
              if (isFirstToken) {
                return [...prev, { role: "assistant", content: assistantContent, time: Date.now() }];
              }
              const next = [...prev];
              next[next.length - 1] = { ...next[next.length - 1], content: assistantContent };
              return next;
            });
          },
        }
      );
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, something went wrong reaching the server. Please try again.",
          time: Date.now(),
        },
      ]);
      console.error(err);
    } finally {
      setSending(false);
    }
  }

  function fillQuickIdea(text: string) {
    if (sending || ended) return;
    setInput(text);
    inputRef.current?.focus();
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
    <div className="mx-auto flex h-dvh w-full max-w-3xl flex-col px-3 py-3 sm:px-6 sm:py-4">
      <header className="flex items-center justify-between gap-2 rounded-xl border-2 border-ink bg-white px-3 py-3 shadow-[3px_3px_0px_var(--ink)] sm:gap-3 sm:px-4">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <button
            onClick={() => router.push("/")}
            aria-label="Back to destinations"
            className="flex size-9 shrink-0 items-center justify-center rounded-lg border-2 border-ink bg-white shadow-[2px_2px_0px_var(--ink)] transition-all hover:bg-muted active:translate-x-px active:translate-y-px active:shadow-none"
          >
            <ArrowLeft className="size-4" />
          </button>
          <div className="flex min-w-0 items-center gap-2">
            <span className="shrink-0 text-2xl">{flag}</span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="truncate font-heading text-lg font-extrabold leading-tight text-ink">
                  {country}
                </h1>
                {!ended && (
                  <span className="hidden shrink-0 items-center gap-1 rounded-full border-2 border-ink bg-mint-soft px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ink sm:inline-flex">
                    <span className="size-1.5 animate-pulse rounded-full bg-mint" />
                    Live
                  </span>
                )}
              </div>
              <p className="hidden truncate text-xs font-medium text-muted-foreground sm:block">
                Ask anything — history, food, culture, nature & more.
              </p>
            </div>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={handleEndChat} disabled={ending || ended}>
          {ended ? "Chat ended" : ending ? "Ending…" : "End chat"}
        </Button>
      </header>

      <div className="my-3 min-h-0 flex-1 overflow-y-auto rounded-xl border-2 border-ink bg-surface-low p-3 sm:p-4">
        <div className="flex flex-col gap-4">
          {messages.length === 0 && (
            <div className="flex items-center gap-2 rounded-xl rounded-bl-sm border-2 border-ink bg-white px-4 py-3 shadow-[3px_3px_0px_var(--ink)]">
              <span className="text-lg">{flag}</span>
              <p className="text-sm font-medium text-ink">
                Say hello, or ask your first question about {country}!
              </p>
            </div>
          )}
          {messages.map((m, i) => {
            const isUser = m.role === "user";
            return (
              <div
                key={i}
                className={cn("flex w-full items-end gap-2", isUser ? "justify-end" : "justify-start")}
              >
                {!isUser && (
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full border-2 border-ink bg-white text-sm shadow-[1px_1px_0px_var(--ink)]">
                    {flag}
                  </span>
                )}
                <div
                  className={cn(
                    "flex max-w-[78%] flex-col gap-1",
                    isUser ? "items-end" : "items-start"
                  )}
                >
                  <span className="px-1 text-[11px] font-bold text-muted-foreground">
                    {isUser ? "You" : country} · {formatTime(m.time)}
                  </span>
                  <div
                    className={cn(
                      "rounded-2xl border-2 border-ink px-4 py-2.5 text-sm font-medium",
                      isUser
                        ? "whitespace-pre-wrap rounded-br-sm bg-cyan-soft text-ink shadow-[2px_2px_0px_var(--ink)]"
                        : "rounded-bl-sm bg-white text-ink shadow-[3px_3px_0px_var(--ink)]"
                    )}
                  >
                    {isUser ? (
                      m.content
                    ) : (
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                        {m.content}
                      </ReactMarkdown>
                    )}
                  </div>
                </div>
                {isUser && (
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full border-2 border-ink bg-sunshine text-ink shadow-[1px_1px_0px_var(--ink)]">
                    <User className="size-3.5" />
                  </span>
                )}
              </div>
            );
          })}
          {awaitingResponse && (
            <div className="flex w-full items-end justify-start gap-2">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full border-2 border-ink bg-white text-sm shadow-[1px_1px_0px_var(--ink)]">
                {flag}
              </span>
              <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm border-2 border-ink bg-white px-4 py-3 shadow-[3px_3px_0px_var(--ink)]">
                <span className="size-1.5 animate-bounce rounded-full bg-ink [animation-delay:-0.3s]" />
                <span className="size-1.5 animate-bounce rounded-full bg-ink [animation-delay:-0.15s]" />
                <span className="size-1.5 animate-bounce rounded-full bg-ink" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
      >
        {!ended && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5">
            <span className="flex shrink-0 items-center gap-1 pr-0.5 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
              <Lightbulb className="size-3.5" />
              Ideas:
            </span>
            {QUICK_IDEAS.map((idea) => (
              <button
                key={idea}
                type="button"
                onClick={() => fillQuickIdea(idea)}
                className="shrink-0 whitespace-nowrap rounded-full border-2 border-ink bg-white px-3 py-1 text-xs font-bold text-ink shadow-[1px_1px_0px_var(--ink)] transition-all hover:bg-sunshine active:translate-x-px active:translate-y-px active:shadow-none"
              >
                {idea}
              </button>
            ))}
          </div>
        )}

        <div className="flex items-center gap-2 rounded-xl border-2 border-ink bg-white p-1.5 shadow-[3px_3px_0px_var(--ink)] focus-within:shadow-[4px_4px_0px_var(--ink)]">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={ended ? "This chat has ended" : "Ask a question..."}
            disabled={sending || !userId || ended}
            autoFocus
            className="flex-1 bg-transparent px-2.5 py-1.5 text-base font-medium text-ink outline-none placeholder:text-outline disabled:opacity-50 md:text-sm"
          />
          <button
            type="submit"
            aria-label="Send message"
            disabled={sending || input.trim().length < MIN_QUERY_LENGTH || !userId || ended}
            className="flex size-9 shrink-0 items-center justify-center rounded-lg border-2 border-ink bg-sunshine text-ink shadow-[2px_2px_0px_var(--ink)] transition-all hover:bg-sunshine-dim active:translate-x-px active:translate-y-px active:shadow-none disabled:pointer-events-none disabled:opacity-50"
          >
            <Send className="size-4" />
          </button>
        </div>
        {!ended && isTooShort && (
          <div className="flex items-start gap-2 rounded-lg border-2 border-ink bg-bubblegum-soft px-3 py-2 shadow-[1px_1px_0px_var(--ink)]">
            <span className="text-sm leading-none">⚠️</span>
            <p className="text-xs font-bold text-ink">
              Keep going — questions need at least {MIN_QUERY_LENGTH} characters.
            </p>
          </div>
        )}
        {ended && (
          <p className="px-1 text-xs font-medium text-muted-foreground">This chat has ended.</p>
        )}
      </form>
    </div>
  );
}
