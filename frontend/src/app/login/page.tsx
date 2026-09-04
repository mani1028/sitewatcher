"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Activity } from "lucide-react";
import { api, isLoggedIn, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@visyscloudtech.com");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isLoggedIn()) router.replace("/dashboard");
  }, [router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await api.login(email, password);
      setToken(res.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-5 py-12">
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -left-24 top-20 h-72 w-72 rounded-full bg-teal/10 blur-3xl" />
        <div className="absolute -right-16 bottom-10 h-80 w-80 rounded-full bg-alert-slow/10 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md animate-rise">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-teal text-white shadow-soft">
            <Activity className="h-5 w-5" />
          </div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">SiteWatch</h1>
          <p className="mt-2 text-sm text-ink-soft">
            Monitor every project. Get alerted by domain mail when something goes down.
          </p>
        </div>

        <form onSubmit={onSubmit} className="surface rounded-3xl p-6 shadow-soft">
          <label className="mb-4 block">
            <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-mute">Email</span>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="mb-5 block">
            <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-mute">Password</span>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <p className="mb-4 text-sm text-alert-down">{error}</p>}
          <button className="btn-primary w-full" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
