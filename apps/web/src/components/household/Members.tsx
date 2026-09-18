"use client";

import { useCreateInvite, useInvites, useJoinHousehold, useRemoveMember, type HouseholdOut } from "@larder/api-client";
import { useState, type FormEvent } from "react";
import { Banner, Button, Input } from "@/components/ui";

export function MemberList({ household, meId, isOwner }: { household: HouseholdOut; meId: string; isOwner: boolean }) {
  const remove = useRemoveMember();
  return (
    <ul className="divide-y divide-line">
      {household.members.map((m) => (
        <li key={m.user_id} className="flex items-center justify-between gap-3 py-2">
          <span>
            {m.display_name ?? "Member"}
            <span className="ml-2 text-sm text-ink-muted">
              {m.role === "owner" ? "owner" : "member"}
              {m.user_id === meId ? " · you" : ""}
            </span>
          </span>
          {(isOwner && m.user_id !== meId) || (!isOwner && m.user_id === meId) ? (
            <Button size="sm" variant="danger" loading={remove.isPending} onClick={() => remove.mutate({ id: household.id, userId: m.user_id })}>
              {m.user_id === meId ? "Leave" : "Remove"}
            </Button>
          ) : null}
        </li>
      ))}
      {remove.error && (
        <li className="py-2">
          <Banner tone="danger">{remove.error.message}</Banner>
        </li>
      )}
    </ul>
  );
}

export function InviteCode({ householdId }: { householdId: string }) {
  const invites = useInvites(householdId);
  const create = useCreateInvite();
  const [copied, setCopied] = useState(false);
  const active = invites.data?.[0];
  const copy = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable
    }
  };
  return (
    <div className="space-y-3">
      <p className="text-sm text-ink-muted">Share a code so someone with a Larder account can join your kitchen. Codes last 7 days.</p>
      {active ? (
        <div className="flex flex-wrap items-center gap-3">
          <code className="rounded-md border border-line bg-surface-alt px-3 py-2 font-mono text-lg tracking-widest" data-testid="invite-code">
            {active.code}
          </code>
          <Button size="sm" variant="secondary" onClick={() => copy(active.code)}>
            {copied ? "Copied" : "Copy"}
          </Button>
          <span className="text-sm text-ink-muted">
            {active.uses} of {active.max_uses} used
          </span>
        </div>
      ) : (
        <Button variant="secondary" onClick={() => create.mutate({ id: householdId })} loading={create.isPending}>
          Create invite code
        </Button>
      )}
    </div>
  );
}

export function JoinForm() {
  const join = useJoinHousehold();
  const [code, setCode] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    join.mutate({ code: code.trim().toUpperCase() });
  };
  return (
    <form onSubmit={submit} className="space-y-3">
      <p className="text-sm text-ink-muted">Got a code from someone? Joining replaces your solo kitchen with theirs.</p>
      <div className="flex items-end gap-2">
        <Input name="code" label="Invite code" value={code} onChange={(e) => setCode(e.target.value)} maxLength={8} placeholder="K7PQ2M9X" className="font-mono uppercase tracking-widest" />
        <Button type="submit" variant="secondary" disabled={code.trim().length !== 8} loading={join.isPending}>
          Join
        </Button>
      </div>
      {join.error && <Banner tone="danger">{join.error.message}</Banner>}
    </form>
  );
}
