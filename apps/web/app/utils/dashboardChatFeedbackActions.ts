import type { MutableRefObject } from "react";

import { postJson } from "../../lib/api";
import type { ChatMessage, ControlOverrides } from "../types";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

export async function runDashboardSetMessageFeedback({
  buildChatDecisionContext,
  chatMessagesRef,
  currentProjectId,
  feedback,
  messageId,
  setChatMessages,
  token,
}: {
  buildChatDecisionContext: (overrides: ControlOverrides, message: string) => unknown;
  chatMessagesRef: MutableRefObject<ChatMessage[]>;
  currentProjectId?: string | null;
  feedback: ChatMessage["feedback"];
  messageId: string;
  setChatMessages: StateSetter<ChatMessage[]>;
  token: string | null;
}) {
  if (!token || !feedback) return;
  const thread = chatMessagesRef.current;
  const idx = thread.findIndex((message) => message.id === messageId);
  if (idx < 0) return;
  const target = thread[idx];
  const prevUser = [...thread]
    .slice(0, idx)
    .reverse()
    .find((message) => message.role === "user");
  const userMessage = prevUser?.content ?? "";

  setChatMessages((current) => {
    const next = current.map((message) =>
      message.id === messageId ? { ...message, feedback } : message,
    );
    chatMessagesRef.current = next;
    return next;
  });

  try {
    await postJson<{ success: boolean }>(
      "/api/chat/feedback",
      {
        project_id: currentProjectId ?? null,
        message_id: messageId,
        feedback,
        message: userMessage,
        assistant_message: target.content,
        context: buildChatDecisionContext({}, userMessage),
      },
      { token },
    );
  } catch {
    // Feedback logging should never block chat UX.
  }
}
