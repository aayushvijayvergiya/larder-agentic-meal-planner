"use client";

import { ApiProvider, createApi } from "@larder/api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMemo, useState, type ReactNode } from "react";
import { supabaseBrowser } from "@/lib/supabase/client";
import { ThemeProvider } from "@/lib/theme";

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, refetchOnWindowFocus: false } } }),
  );
  const api = useMemo(
    () =>
      createApi(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000", async () => {
        const { data } = await supabaseBrowser().auth.getSession();
        return data.session?.access_token ?? null;
      }),
    [],
  );
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ApiProvider api={api}>{children}</ApiProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
