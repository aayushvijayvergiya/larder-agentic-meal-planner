"use client";

import { useMe } from "@larder/api-client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { SkeletonList } from "@/components/ui";

/** Routes the signed-in user by onboarding status (LLD §9.4). */
export default function RootPage() {
  const router = useRouter();
  const me = useMe();
  useEffect(() => {
    if (!me.data) return;
    router.replace(me.data.onboarding_status === "complete" ? "/today" : "/onboarding");
  }, [me.data, router]);
  return (
    <main className="mx-auto max-w-[880px] px-4 py-10">
      {me.isError ? (
        <p className="text-danger">Couldn&apos;t reach Larder. Check that the API is running and try again.</p>
      ) : (
        <SkeletonList rows={2} />
      )}
    </main>
  );
}
