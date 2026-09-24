"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { AuthProvider, useAuth } from "@/lib/auth-context";
import { useLiveUpdates } from "@/lib/ws";

function LiveUpdates() {
  const { email, loading } = useAuth();
  useLiveUpdates(!loading && email != null);
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 5_000,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <LiveUpdates />
        {children}
      </AuthProvider>
    </QueryClientProvider>
  );
}
