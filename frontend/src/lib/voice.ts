import { PipecatClient } from "@pipecat-ai/client-js";
import { ProtobufFrameSerializer, WebSocketTransport } from "@pipecat-ai/websocket-transport";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

export type VoiceState = "connecting" | "listening" | "speaking" | "disconnected";

export interface VoiceSessionRequest {
  sessionId?: string;
  userId: string;
  country: string;
}

export interface VoiceSessionHandlers {
  /** Fired once if the server minted a new session_id (a brand-new session). */
  onSession?: (info: { session_id: string; user_id: string | null }) => void;
  /** Fired once per final spoken user turn. */
  onUserText?: (text: string) => void;
  /** Fired for each chunk of the assistant's spoken reply, in order - mirrors streamChatMessage's onToken. */
  onAssistantToken?: (text: string) => void;
  onStateChange?: (state: VoiceState) => void;
  onError?: (message: string) => void;
}

export interface VoiceSession {
  stop(): Promise<void>;
}

/** Converts the backend's http(s) base URL into the matching ws(s) one. */
function wsBaseUrl(): string {
  return API_BASE_URL.replace(/^http/, "ws");
}

/** Opens a voice-mode connection to the backend's /voice endpoint and starts
 * listening on the mic. Resolves once the bot signals ready; call `stop()` on
 * the returned handle to end the call (triggers the server's disconnect-time
 * memory flush - see backend/voice/session.py).
 */
export async function startVoiceSession(req: VoiceSessionRequest, handlers: VoiceSessionHandlers): Promise<VoiceSession> {
  const client = new PipecatClient({
    transport: new WebSocketTransport({ serializer: new ProtobufFrameSerializer() }),
    enableMic: true,
    enableCam: false,
    callbacks: {
      onBotReady: () => handlers.onStateChange?.("listening"),
      onUserStartedSpeaking: () => handlers.onStateChange?.("listening"),
      onBotStartedSpeaking: () => handlers.onStateChange?.("speaking"),
      onBotStoppedSpeaking: () => handlers.onStateChange?.("listening"),
      onDisconnected: () => handlers.onStateChange?.("disconnected"),
      onServerMessage: (data: unknown) => {
        const message = data as { type?: string; session_id?: string; user_id?: string | null };
        if (message?.type === "session" && message.session_id) {
          handlers.onSession?.({ session_id: message.session_id, user_id: message.user_id ?? null });
        }
      },
      // onUserInput/onLlmRawText (the newer, non-deprecated events) are RTVI
      // 2.2.0+ - the installed pipecat-ai server (1.12.0) doesn't emit them yet,
      // only their deprecated predecessors below. onUserTranscript gives one
      // message per final utterance (safe to take as-is); onBotLlmText fires
      // once per LLMTextFrame GraphLLMProcessor pushes, i.e. a true per-token
      // delta - unlike onBotOutput, whose `text` is a whole TTS segment resent
      // repeatedly as spoken_progress advances, which is not safe to concatenate.
      onUserTranscript: (data) => {
        if (data.final) handlers.onUserText?.(data.text);
      },
      onBotLlmText: (data) => handlers.onAssistantToken?.(data.text),
      onError: (message) => handlers.onError?.(String(message)),
    },
  });

  const params = new URLSearchParams();
  if (req.sessionId) params.set("session_id", req.sessionId);
  params.set("user_id", req.userId);
  params.set("country", req.country);

  handlers.onStateChange?.("connecting");
  await client.connect({ wsUrl: `${wsBaseUrl()}/voice?${params.toString()}` });

  return {
    stop: async () => {
      await client.disconnect();
    },
  };
}
