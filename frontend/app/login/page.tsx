"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({ detail: "Login failed" }));
        setError(body.detail || "Login failed");
        return;
      }
      const next = searchParams.get("next") || "/";
      router.push(next);
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0b0f17]">
      <form onSubmit={handleSubmit} className="card w-full max-w-sm flex flex-col gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-100">Mini NMS</h1>
          <p className="text-sm text-gray-500">Sign in to the network monitoring dashboard</p>
        </div>
        {error && <div className="rounded-md bg-red-900/40 border border-red-700 px-3 py-2 text-sm text-red-300">{error}</div>}
        <label className="flex flex-col gap-1 text-sm text-gray-300">
          Email
          <input
            className="input"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoFocus
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-300">
          Password
          <input
            className="input"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button type="submit" disabled={loading} className="btn-primary justify-center">
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
