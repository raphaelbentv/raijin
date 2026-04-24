"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { KeyRound, Zap } from "lucide-react";
import { ApiError, apiFetch } from "@/lib/api";
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";

export default function ResetPasswordPage() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(token ? null : "Lien de reset manquant.");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    const nextPassword = String(new FormData(e.currentTarget as HTMLFormElement).get("password") ?? "");
    setError(null);
    setLoading(true);
    try {
      await apiFetch("/auth/reset-password", {
        method: "POST",
        auth: false,
        json: { token, password: nextPassword },
      });
      setSuccess(true);
      setTimeout(() => router.push("/login"), 700);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setError("Ce lien est invalide ou expiré.");
      } else {
        setError("Impossible de changer le mot de passe.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="glass glass-glow p-8" style={{ borderRadius: 22 }}>
      <div className="relative z-10">
        <div className="mb-6 flex items-center gap-2.5">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-lg"
            style={{
              background: "linear-gradient(135deg, #8b5cf6, #6366f1)",
              boxShadow: "0 0 20px rgba(139,92,246,0.4)",
            }}
          >
            <Zap className="h-[18px] w-[18px] text-white" />
          </div>
          <span className="text-[18px] font-semibold tracking-tight text-white/95">Raijin</span>
        </div>
        <h1 className="font-serif-italic text-[28px] leading-tight text-white/95">
          Nouveau mot de passe
        </h1>
        <p className="mt-1 text-[13px] text-white/60">
          Choisis un mot de passe robuste pour retrouver ton espace.
        </p>

        <form method="post" onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div className="space-y-2">
            <Label htmlFor="password" className="text-white/80">
              Mot de passe
            </Label>
            <PasswordInput
              id="password"
              name="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-white/10 bg-white/[0.04] text-white placeholder:text-white/35 focus-visible:ring-violet-500/50"
            />
          </div>
          {error && <p className="text-[13px] text-rose-400">{error}</p>}
          {success && (
            <p className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 px-3 py-2 text-[13px] text-emerald-100">
              Mot de passe mis à jour.
            </p>
          )}
          <button
            type="submit"
            disabled={loading || !token}
            className="btn-primary-violet w-full justify-center disabled:opacity-60"
          >
            <KeyRound className="h-4 w-4" />
            {loading ? "Mise à jour…" : "Changer le mot de passe"}
          </button>
          <p className="text-center text-[13px] text-white/60">
            <Link
              href="/login"
              className="font-medium text-violet-300 underline-offset-4 hover:underline"
            >
              Retour connexion
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
