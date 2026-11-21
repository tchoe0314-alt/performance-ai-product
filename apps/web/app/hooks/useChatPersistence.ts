"use client";

import { useEffect, useRef } from "react";

import type { ChatMessage } from "../types";
import { getChatThreadStorageKey, resolveStoredChatThread } from "../utils/chat";

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
  const activeStorageKeyRef = useRef<string | null>(null);
  const storageKey =
    currentProjectId || projectId
      ? getChatThreadStorageKey(currentProjectId || projectId || "draft")
      : null;

  useEffect(() => {
    // Chat panel is mounted lazily; guard until the scroll container exists.
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
    if (typeof window === "undefined" || !storageKey) return;
    if (activeStorageKeyRef.current === storageKey) return;
    activeStorageKeyRef.current = storageKey;
    const restored = resolveStoredChatThread(
      chatMessagesRef.current,
      window.localStorage.getItem(storageKey),
    );
    if (restored !== chatMessagesRef.current) {
      chatMessagesRef.current = restored;
      setChatMessages(restored);
    }
  }, [chatMessagesRef, setChatMessages, storageKey]);

  useEffect(() => {
    if (typeof window === "undefined" || !storageKey) return;
    // On a project switch, the restoration effect above must claim the new key
    // before any thread is persisted under it.
    if (activeStorageKeyRef.current !== storageKey) return;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(chatMessagesRef.current));
    } catch {
      // Ignore local storage failures.
    }
  }, [chatMessages, chatMessagesRef, storageKey]);
}
