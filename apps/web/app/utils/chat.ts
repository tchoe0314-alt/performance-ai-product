import type { ChatMessage } from "../types";

export const CHAT_THREAD_KEY_PREFIX = "civora-chat-thread:";

export function getChatThreadStorageKey(projectId: string) {
  return `${CHAT_THREAD_KEY_PREFIX}${projectId || "draft"}`;
}

export function createChatMessage(
  role: ChatMessage["role"],
  content: string,
  kind: ChatMessage["kind"] = "message",
  feedback?: ChatMessage["feedback"],
  phaseTag?: string,
): ChatMessage {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
    createdAt: Date.now(),
    kind,
    feedback,
    phaseTag,
  };
}

export function createWelcomeMessage(): ChatMessage {
  return {
    id: "welcome-message",
    role: "assistant",
    content:
      "Hi, I’m Civora. I can help you think through a site, answer questions, and turn design requests into a plan when you’re ready. Tell me what you want to change, or just ask me a question first.",
    createdAt: 0,
    kind: "message",
  };
}

export function extractDesignMemory(thread: ChatMessage[]): {
  preferences: string[];
  constraints: string[];
} {
  const preferences: string[] = [];
  const constraints: string[] = [];
  const seen = new Set<string>();

  for (const message of thread) {
    if (message.role !== "user") continue;
    const clauses = message.content.split(/[.!?\n;]+/);
    for (const clause of clauses) {
      const clean = clause.replace(/\s+/g, " ").trim();
      if (!clean || clean.length < 8) continue;
      const lowered = clean.toLowerCase();
      const key = lowered.slice(0, 160);
      if (seen.has(key)) continue;

      if (
        lowered.includes("make sure") ||
        lowered.includes("remember to") ||
        lowered.includes("prefer ") ||
        lowered.includes("keep ") ||
        lowered.includes("stay in ")
      ) {
        preferences.push(clean);
        seen.add(key);
        continue;
      }

      if (
        lowered.includes("do not") ||
        lowered.includes("don't") ||
        lowered.includes("dont") ||
        lowered.includes("never ") ||
        lowered.includes("without ") ||
        lowered.includes("no guessing") ||
        lowered.includes("ask for clarification")
      ) {
        constraints.push(clean);
        seen.add(key);
      }
    }
  }

  return {
    preferences: preferences.slice(-8),
    constraints: constraints.slice(-8),
  };
}
