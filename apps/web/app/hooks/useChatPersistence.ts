"use client";

import { useEffect } from "react";

import type { ChatMessage } from "../types";
import { getChatThreadStorageKey } from "../utils/chat";

type UseChatPersistenceOptions = {
  chatMessages: ChatMessage[];
  setChatMessages: (messages: ChatMessage[]) => void;
  chatMessagesRef: React.MutableRefObject<ChatMessage[]>;
  chatScrollRef: React.RefObject<HTMLDivElement | null>;
  projectId: string;
  currentProjectId?: string;
};

export default function useChatPersistence({
  chatMessages,
  setChatMessages,
  chatMessagesRef,
  chatScrollRef,
  projectId,
  currentProjectId,
}: UseChatPersistenceOptions) {
  useEffect(() => {
    const node = chatScrollRef.current;
    if (!node) return;
    node.scrollTo({
      top: node.scrollHeight,
      behavior: "smooth",
    });
  }, [chatMessages, chatScrollRef]);

  useEffect(() => {
    chatMessagesRef.current = chatMessages;
  }, [chatMessages, chatMessagesRef]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const key = getChatThreadStorageKey(currentProjectId || projectId || "draft");
    try {
      window.localStorage.setItem(key, JSON.stringify(chatMessagesRef.current));
    } catch {
      // Ignore local storage failures.
    }
  }, [chatMessages, chatMessagesRef, currentProjectId, projectId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const key = getChatThreadStorageKey(currentProjectId || projectId || "draft");
    if (chatMessagesRef.current.length > 1) return;
    const raw = window.localStorage.getItem(key);
    if (!raw) return;
    try {
      const stored = JSON.parse(raw);
      if (!Array.isArray(stored) || !stored.length) return;
      const restored = stored
        .filter((message: ChatMessage) => message && typeof message.content === "string")
        .map((message: ChatMessage): ChatMessage => ({
          id:
            typeof message.id === "string"
              ? message.id
              : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          role:
            message.role === "user" ||
            message.role === "assistant" ||
            message.role === "system"
              ? message.role
              : "assistant",
          content: message.content,
          createdAt:
            typeof message.createdAt === "number" ? message.createdAt : Date.now(),
          kind:
            message.kind === "status" ||
            message.kind === "explanation" ||
            message.kind === "action"
              ? message.kind
              : "message",
          feedback:
            message.feedback === "up" || message.feedback === "down"
              ? message.feedback
              : undefined,
          phaseTag: typeof message.phaseTag === "string" ? message.phaseTag : undefined,
        }));
      if (restored.length) {
        chatMessagesRef.current = restored;
        setChatMessages(restored);
      }
    } catch {
      // Ignore invalid local storage payloads.
    }
  }, [chatMessagesRef, currentProjectId, projectId, setChatMessages]);
}
