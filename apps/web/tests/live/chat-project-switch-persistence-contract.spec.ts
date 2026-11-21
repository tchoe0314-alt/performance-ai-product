import { expect, test } from "@playwright/test";

import type { ChatMessage } from "../../app/types";
import { createWelcomeMessage, resolveStoredChatThread } from "../../app/utils/chat";

const message = (id: string, role: ChatMessage["role"], content: string): ChatMessage => ({
  id,
  role,
  content,
  createdAt: 1,
  kind: "message",
});

test("project switch restores its own local chat before persistence can replace it", () => {
  const projectA = [
    createWelcomeMessage(),
    message("a-user", "user", "Project A needs twelve spaces."),
  ];
  const projectB = [
    createWelcomeMessage(),
    message("b-user", "user", "Project B must preserve the north setback."),
  ];

  const restored = resolveStoredChatThread(
    [createWelcomeMessage()],
    JSON.stringify(projectB),
  );

  expect(restored.map(({ content }) => content)).toContain("Project B must preserve the north setback.");
  expect(restored.map(({ content }) => content)).not.toContain("Project A needs twelve spaces.");
  expect(JSON.stringify(projectA)).not.toBe(JSON.stringify(restored));
});

test("saved project chat remains authoritative and malformed recovery data is ignored", () => {
  const savedThread = [
    createWelcomeMessage(),
    message("server-user", "user", "Use the saved project conversation."),
  ];
  const localThread = [
    createWelcomeMessage(),
    message("local-user", "user", "This older local copy must not win."),
  ];

  expect(resolveStoredChatThread(savedThread, JSON.stringify(localThread))).toBe(savedThread);
  expect(resolveStoredChatThread([createWelcomeMessage()], "not-json")).toHaveLength(1);
});
