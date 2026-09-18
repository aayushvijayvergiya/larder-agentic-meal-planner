"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button, Input } from "@/components/ui";
import { supabaseBrowser } from "@/lib/supabase/client";

export function AuthForm({ mode }: { mode: "sign-in" | "sign-up" }) {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const supabase = supabaseBrowser();
    const result =
      mode === "sign-up"
        ? await supabase.auth.signUp({ email, password })
        : await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (result.error) {
      setError(result.error.message);
      return;
    }
    if (mode === "sign-up" && !result.data.session) {
      setError("Check your inbox to confirm your email, then sign in.");
      return;
    }
    router.replace(params.get("next") ?? "/");
    router.refresh();
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center px-4 py-12">
      <p className="text-sm font-medium text-accent">Larder</p>
      <h1 className="mt-2 text-3xl">{mode === "sign-up" ? "Start with what's in your kitchen." : "Welcome back."}</h1>
      <p className="mt-2 text-ink-muted">
        {mode === "sign-up" ? "Plans that use up what you already have." : "Your week is waiting."}
      </p>
      <form onSubmit={submit} className="mt-8 space-y-4" data-testid={`${mode}-form`}>
        <Input label="Email" name="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Input
          label="Password"
          name="password"
          type="password"
          autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
          minLength={6}
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" loading={busy}>
          {mode === "sign-up" ? "Create account" : "Sign in"}
        </Button>
      </form>
      <p className="mt-6 text-sm text-ink-muted">
        {mode === "sign-up" ? (
          <>
            Already have an account? <Link className="underline" href="/sign-in">Sign in</Link>
          </>
        ) : (
          <>
            New here? <Link className="underline" href="/sign-up">Create an account</Link>
          </>
        )}
      </p>
    </main>
  );
}
