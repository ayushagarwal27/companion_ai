import { Suspense } from "react";
import { ChatClient } from "./chat-client";

export default function ChatPage() {
  return (
    <Suspense>
      <ChatClient />
    </Suspense>
  );
}
