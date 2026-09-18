"use client";

import { useJob } from "@larder/api-client";
import { Banner } from "@/components/ui";

/** Shows planning progress for a job and fades away when done (LLD §9.7). */
export function JobBanner({ jobId, onRetry, message }: { jobId: string | undefined; onRetry?: () => void; message?: string }) {
  const job = useJob(jobId);
  if (!jobId || !job.data) return null;
  if (job.data.status === "failed") {
    return (
      <Banner tone="danger" action={onRetry && <button className="underline" onClick={onRetry}>Retry</button>}>
        Couldn&apos;t finish planning. Your previous plan is unchanged.
      </Banner>
    );
  }
  if (job.data.status === "ready") return null;
  return (
    <Banner tone="info">
      <span className="inline-flex items-center gap-2">
        <span className="h-2 w-2 animate-pulse rounded-full bg-accent" aria-hidden />
        {message ?? "Planning your week from what's in the larder…"}
      </span>
    </Banner>
  );
}
