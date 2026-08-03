"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Brain, Check, MessageSquare, Send, Trash2, UserMinus, UserPlus, Users } from "lucide-react";

import { deleteJson, getJson, patchJson, postJson } from "../../lib/api";
import type {
  EngineeringMemoryConsent,
  EngineeringMemoryItem,
  ProjectCollaboration,
} from "../types";

type ProjectAdminSurface = {
  current_user_role: string;
  permissions: {
    can_manage_access: boolean;
  };
  members: Array<{
    user_id: string;
    email: string;
    name: string;
    role: string;
  }>;
  invites: Array<{
    invite_id: string;
    email: string;
    role: string;
    status: string;
  }>;
};

type MemorySurface = {
  consent: EngineeringMemoryConsent;
  items: EngineeringMemoryItem[];
};

type ProjectTeamMemoryPanelProps = {
  projectId?: string | null;
  projectName: string;
  token?: string | null;
};

const EMPTY_CONSENT: EngineeringMemoryConsent = {
  personal_enabled: false,
  company_enabled: false,
  global_learning_enabled: false,
  default: "off",
};

function mentionEmails(body: string) {
  return Array.from(
    new Set(
      Array.from(body.matchAll(/@([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})/gi)).map(
        (match) => match[1].toLowerCase(),
      ),
    ),
  );
}

export function ProjectTeamMemoryPanel({ projectId, projectName, token }: ProjectTeamMemoryPanelProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [collaboration, setCollaboration] = useState<ProjectCollaboration | null>(null);
  const [admin, setAdmin] = useState<ProjectAdminSurface | null>(null);
  const [memory, setMemory] = useState<MemorySurface>({ consent: EMPTY_CONSENT, items: [] });
  const [comment, setComment] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("reviewer");
  const [reviewEmail, setReviewEmail] = useState("");
  const [reviewMessage, setReviewMessage] = useState("");
  const [memoryScope, setMemoryScope] = useState<"project" | "personal" | "company">("project");
  const [memoryLabel, setMemoryLabel] = useState("");
  const [memoryNote, setMemoryNote] = useState("");

  const canUseBackend = Boolean(token && projectId);
  const activePeople = collaboration?.presence ?? [];
  const openComments = useMemo(
    () => (collaboration?.comments ?? []).filter((item) => item.status !== "resolved"),
    [collaboration?.comments],
  );
  const openReviews = useMemo(
    () => (collaboration?.review_requests ?? []).filter((item) => !["completed", "cancelled"].includes(item.status)),
    [collaboration?.review_requests],
  );

  const refresh = useCallback(async (quiet = false) => {
    if (!token || !projectId) return;
    if (!quiet) setLoading(true);
    try {
      await postJson(`/api/projects/${projectId}/presence`, { context: { mode: "projects", view: "team_memory" } }, { token });
      const [collaborationResponse, adminResponse, memoryResponse] = await Promise.all([
        getJson<{ success: boolean } & ProjectCollaboration>(`/api/projects/${projectId}/collaboration`, { token }),
        getJson<{ success: boolean } & ProjectAdminSurface>(`/api/projects/${projectId}/admin`, { token }),
        getJson<{ success: boolean } & MemorySurface>(`/api/memory?project_id=${encodeURIComponent(projectId)}`, { token }),
      ]);
      setCollaboration(collaborationResponse);
      setAdmin(adminResponse);
      setMemory({ consent: memoryResponse.consent, items: memoryResponse.items ?? [] });
      if (!quiet) setNotice("");
    } catch (error) {
      if (!quiet) setNotice(error instanceof Error ? error.message : "Team and memory could not load.");
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [projectId, token]);

  useEffect(() => {
    if (!open || !canUseBackend) return;
    void refresh();
    const timer = window.setInterval(() => void refresh(true), 20_000);
    return () => window.clearInterval(timer);
  }, [canUseBackend, open, refresh]);

  const addComment = async () => {
    if (!token || !projectId || !comment.trim()) return;
    try {
      await postJson(
        `/api/projects/${projectId}/comments`,
        { body: comment.trim(), mentions: mentionEmails(comment) },
        { token },
      );
      setComment("");
      setNotice("Comment added.");
      await refresh(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Comment could not be added.");
    }
  };

  const requestReview = async () => {
    if (!token || !projectId) return;
    try {
      await postJson(
        `/api/projects/${projectId}/review-requests`,
        { assigned_email: reviewEmail.trim(), message: reviewMessage.trim() },
        { token },
      );
      setReviewMessage("");
      setNotice("Review requested.");
      await refresh(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Review request could not be created.");
    }
  };

  const inviteMember = async () => {
    if (!token || !projectId || !inviteEmail.trim()) return;
    try {
      await postJson(
        `/api/projects/${projectId}/admin/invites`,
        { email: inviteEmail.trim(), role: inviteRole },
        { token },
      );
      setInviteEmail("");
      setNotice("Project invitation created.");
      await refresh(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Invitation could not be created.");
    }
  };

  const updateMemberRole = async (userId: string, role: string) => {
    if (!token || !projectId) return;
    try {
      await patchJson(`/api/projects/${projectId}/admin/members/${userId}`, { role }, { token });
      setNotice("Project role updated.");
      await refresh(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Project role could not be updated.");
    }
  };

  const removeMember = async (userId: string) => {
    if (!token || !projectId) return;
    try {
      await deleteJson(`/api/projects/${projectId}/admin/members/${userId}`, { token });
      setNotice("Project member removed.");
      await refresh(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Project member could not be removed.");
    }
  };

  const updateReviewStatus = async (requestId: string, status: "in_review" | "completed" | "cancelled") => {
    if (!token || !projectId) return;
    try {
      await patchJson(`/api/projects/${projectId}/review-requests/${requestId}`, { status }, { token });
      setNotice(status === "completed" ? "Review marked complete." : status === "in_review" ? "Review started." : "Review request cancelled.");
      await refresh(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Review status could not be updated.");
    }
  };

  const updateConsent = async (key: keyof EngineeringMemoryConsent, value: boolean) => {
    if (!token) return;
    const previous = memory.consent;
    const next = { ...memory.consent, [key]: value };
    setMemory((current) => ({ ...current, consent: next }));
    try {
      const response = await patchJson<{ consent: EngineeringMemoryConsent }>(
        "/api/memory/consent",
        {
          personal_enabled: next.personal_enabled,
          company_enabled: next.company_enabled,
          global_learning_enabled: next.global_learning_enabled,
        },
        { token },
      );
      setMemory((current) => ({ ...current, consent: response.consent }));
      setNotice("Memory controls updated.");
      await refresh(true);
    } catch (error) {
      setMemory((current) => ({ ...current, consent: previous }));
      setNotice(error instanceof Error ? error.message : "Memory controls could not be updated.");
    }
  };

  const addMemory = async () => {
    if (!token || !projectId || !memoryLabel.trim() || !memoryNote.trim()) return;
    try {
      await postJson(
        "/api/memory",
        {
          scope: memoryScope,
          category: memoryScope === "project" ? "decision" : "preference",
          label: memoryLabel.trim(),
          value: { note: memoryNote.trim() },
          project_id: projectId,
        },
        { token },
      );
      setMemoryLabel("");
      setMemoryNote("");
      setNotice("Memory saved as a suggestion, not an engineering rule.");
      await refresh(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Memory could not be saved.");
    }
  };

  const resolveComment = async (commentId: string) => {
    if (!token || !projectId) return;
    try {
      await patchJson(`/api/projects/${projectId}/comments/${commentId}`, { status: "resolved" }, { token });
      setNotice("Comment resolved.");
      await refresh(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Comment could not be resolved.");
    }
  };

  const removeMemory = async (memoryId: string) => {
    if (!token) return;
    try {
      await deleteJson(`/api/memory/${memoryId}`, { token });
      setNotice("Memory removed.");
      await refresh(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Memory could not be removed.");
    }
  };

  return (
    <details
      className="rounded-xl border border-slate-200 bg-white"
      data-testid="project-team-memory"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
        <span className="flex min-w-0 items-center gap-2 text-sm font-semibold text-slate-900">
          <Users size={16} aria-hidden="true" />
          Team & memory
        </span>
        <span className="text-xs text-slate-500">
          {canUseBackend ? `${activePeople.length} active` : "Save and sign in"}
        </span>
      </summary>

      <div className="space-y-5 border-t border-slate-100 px-4 py-4">
        {!canUseBackend ? (
          <p className="text-xs leading-5 text-slate-600">
            Save this project and sign in before sharing, commenting, requesting review, or storing controlled memory.
          </p>
        ) : loading ? (
          <p className="text-xs text-slate-500">Loading team and memory...</p>
        ) : (
          <>
            <section className="space-y-3" aria-labelledby="project-team-heading">
              <div className="flex items-center justify-between gap-3">
                <h3 id="project-team-heading" className="text-xs font-semibold uppercase text-slate-500">Team</h3>
                <span className="text-xs text-slate-500">{admin?.current_user_role || "viewer"}</span>
              </div>
              <div className="space-y-2">
                {(admin?.members ?? []).map((member) => (
                  <div key={member.user_id} className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2">
                    <span className="min-w-0 flex-1 truncate text-xs text-slate-700">{member.name || member.email}</span>
                    {admin?.permissions.can_manage_access && member.role !== "owner" ? (
                      <>
                        <select
                          aria-label={`Role for ${member.name || member.email}`}
                          value={member.role}
                          onChange={(event) => void updateMemberRole(member.user_id, event.target.value)}
                          className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs"
                        >
                          <option value="viewer">Viewer</option>
                          <option value="reviewer">Reviewer</option>
                          <option value="editor">Editor</option>
                          <option value="admin">Admin</option>
                        </select>
                        <button
                          type="button"
                          aria-label={`Remove ${member.name || member.email} from project`}
                          onClick={() => void removeMember(member.user_id)}
                          className="rounded-md p-1.5 text-slate-500 hover:bg-white hover:text-red-600"
                        >
                          <UserMinus size={14} />
                        </button>
                      </>
                    ) : (
                      <span
                        aria-label={`Role for ${member.name || member.email}`}
                        className="text-xs text-slate-500"
                      >
                        {member.role}
                      </span>
                    )}
                  </div>
                ))}
              </div>
              {admin?.permissions.can_manage_access ? (
                <div className="grid grid-cols-[1fr_auto_auto] gap-2">
                  <input
                    aria-label="Invite email"
                    value={inviteEmail}
                    onChange={(event) => setInviteEmail(event.target.value)}
                    placeholder="reviewer@firm.com"
                    className="min-w-0 rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                  <select
                    aria-label="Invite role"
                    value={inviteRole}
                    onChange={(event) => setInviteRole(event.target.value)}
                    className="rounded-lg border border-slate-200 px-2 text-sm"
                  >
                    <option value="viewer">Viewer</option>
                    <option value="reviewer">Reviewer</option>
                    <option value="editor">Editor</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button type="button" aria-label="Invite project member" onClick={() => void inviteMember()} className="rounded-lg bg-slate-950 p-2 text-white">
                    <UserPlus size={16} />
                  </button>
                </div>
              ) : null}
            </section>

            <section className="space-y-3" aria-labelledby="project-comments-heading">
              <div className="flex items-center justify-between gap-3">
                <h3 id="project-comments-heading" className="text-xs font-semibold uppercase text-slate-500">Comments</h3>
                <span className="text-xs text-slate-500">{openComments.length} open</span>
              </div>
              {openComments.slice(0, 5).map((item) => (
                <div key={item.comment_id} className="rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
                  <p className="font-semibold text-slate-900">{item.author_name || item.author_email || "Project member"}</p>
                  <p className="mt-1 leading-5">{item.body}</p>
                  {collaboration?.permissions.can_comment ? (
                    <button
                      type="button"
                      onClick={() => void resolveComment(item.comment_id)}
                      className="mt-2 inline-flex items-center gap-1 font-semibold text-emerald-700"
                    >
                      <Check size={13} /> Resolve
                    </button>
                  ) : null}
                </div>
              ))}
              {collaboration?.permissions.can_comment ? (
                <div className="flex gap-2">
                  <input
                    aria-label="Project comment"
                    value={comment}
                    onChange={(event) => setComment(event.target.value)}
                    placeholder="Comment or @mention an email"
                    className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                  <button type="button" aria-label="Add project comment" onClick={() => void addComment()} className="rounded-lg bg-slate-950 p-2 text-white">
                    <Send size={16} />
                  </button>
                </div>
              ) : null}
            </section>

            {collaboration?.permissions.can_request_review ? (
              <section className="space-y-3" aria-labelledby="review-request-heading">
                <div className="flex items-center justify-between gap-3">
                  <h3 id="review-request-heading" className="text-xs font-semibold uppercase text-slate-500">Review requests</h3>
                  <span className="text-xs text-slate-500">{openReviews.length} open</span>
                </div>
                <input aria-label="Review assignee email" value={reviewEmail} onChange={(event) => setReviewEmail(event.target.value)} placeholder="Invited reviewer email (optional)" className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
                <div className="flex gap-2">
                  <input aria-label="Review request message" value={reviewMessage} onChange={(event) => setReviewMessage(event.target.value)} placeholder="What should be reviewed?" className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm" />
                  <button type="button" aria-label="Request project review" onClick={() => void requestReview()} className="rounded-lg bg-slate-950 p-2 text-white">
                    <MessageSquare size={16} />
                  </button>
                </div>
                <div className="space-y-2">
                  {openReviews.slice(0, 5).map((item) => (
                    <div key={item.request_id} className="rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
                      <p className="font-semibold text-slate-900">{item.assigned_email || "Project review"}</p>
                      {item.message ? <p className="mt-1 leading-5">{item.message}</p> : null}
                      <div className="mt-2 flex flex-wrap gap-2">
                        {item.status === "open" ? (
                          <button type="button" onClick={() => void updateReviewStatus(item.request_id, "in_review")} className="font-semibold text-blue-700">Start review</button>
                        ) : null}
                        <button type="button" onClick={() => void updateReviewStatus(item.request_id, "completed")} className="font-semibold text-emerald-700">Complete</button>
                        <button type="button" onClick={() => void updateReviewStatus(item.request_id, "cancelled")} className="font-semibold text-slate-500">Cancel</button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            <section className="space-y-3" aria-labelledby="project-memory-heading">
              <div className="flex items-center gap-2">
                <Brain size={15} aria-hidden="true" />
                <h3 id="project-memory-heading" className="text-xs font-semibold uppercase text-slate-500">Controlled memory</h3>
              </div>
              <p className="text-xs leading-5 text-slate-600">
                Memory is off by default and only suggests preferences. It never changes standards, evidence, or engineering results by itself.
              </p>
              <div className="grid gap-2 sm:grid-cols-3">
                {([
                  ["personal_enabled", "Personal"],
                  ["company_enabled", "Company"],
                  ["global_learning_enabled", "Global learning consent"],
                ] as const).map(([key, label]) => (
                  <label key={key} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-700">
                    <input type="checkbox" checked={Boolean(memory.consent[key])} onChange={(event) => void updateConsent(key, event.target.checked)} />
                    {label}
                  </label>
                ))}
              </div>
              <p className="text-[11px] leading-4 text-slate-500">
                Global learning records consent only. No project data is used unless a separately governed, anonymized learning pipeline is enabled.
              </p>
              <div className="grid gap-2 sm:grid-cols-[auto_1fr]">
                <select aria-label="Memory scope" value={memoryScope} onChange={(event) => setMemoryScope(event.target.value as typeof memoryScope)} className="rounded-lg border border-slate-200 px-2 py-2 text-sm">
                  <option value="project">This project</option>
                  <option value="personal">Personal</option>
                  <option value="company">Company</option>
                </select>
                <input aria-label="Memory label" value={memoryLabel} onChange={(event) => setMemoryLabel(event.target.value)} placeholder="Decision or preference name" className="rounded-lg border border-slate-200 px-3 py-2 text-sm" />
              </div>
              <div className="flex gap-2">
                <input aria-label="Memory note" value={memoryNote} onChange={(event) => setMemoryNote(event.target.value)} placeholder="What should Civora remember?" className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm" />
                <button type="button" aria-label="Save controlled memory" onClick={() => void addMemory()} className="rounded-lg bg-slate-950 px-3 py-2 text-sm font-semibold text-white">Save</button>
              </div>
              <div className="space-y-2">
                {memory.items.slice(0, 8).map((item) => (
                  <div key={item.memory_id} className="flex items-start justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-slate-900">{item.label}</p>
                      <p className="text-[11px] text-slate-500">{item.scope} · suggestion only</p>
                    </div>
                    <button
                      type="button"
                      aria-label={`Delete memory ${item.label}`}
                      onClick={() => void removeMemory(item.memory_id)}
                      className="rounded-md p-1 text-slate-500 hover:bg-white hover:text-red-600"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
        {notice ? <p role="status" className="text-xs leading-5 text-slate-600">{notice}</p> : null}
        <p className="text-[11px] text-slate-400">{projectName}</p>
      </div>
    </details>
  );
}
