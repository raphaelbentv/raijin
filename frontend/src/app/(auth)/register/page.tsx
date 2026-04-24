"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { Zap } from "lucide-react";
import { ApiError, apiFetch } from "@/lib/api";
import { setTokens } from "@/lib/auth";
import type { TokenPair } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await apiFetch<TokenPair>("/auth/register", {
        method: "POST",
        auth: false,
        json: {
          email,
          password,
          full_name: fullName || null,
          tenant_name: tenantName,
        },
      });
      setTokens(tokens.access_token, tokens.refresh_token);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("Un compte existe déjà avec cet email.");
      } else {
        setError("Impossible de créer le compte.");
      }
    } finally {
      setLoading(false);
    }
  }

  const inputClass =
    "border-white/10 bg-white/[0.04] text-white placeholder:text-white/35 focus-visible:ring-violet-500/50";

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
          Créer un compte
        </h1>
        <p className="mt-1 text-[13px] text-white/60">
          Démarre ton espace Raijin en 30 secondes.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div className="space-y-2">
            <Label htmlFor="tenant" className="text-white/80">
              Entreprise
            </Label>
            <Input
              id="tenant"
              required
              value={tenantName}
              onChange={(e) => setTenantName(e.target.value)}
              className={inputClass}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="full_name" className="text-white/80">
              Nom complet
            </Label>
            <Input
              id="full_name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className={inputClass}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email" className="text-white/80">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password" className="text-white/80">
              Mot de passe
            </Label>
            <PasswordInput
              id="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
            <p className="text-[11px] text-white/45">Au moins 8 caractères.</p>
          </div>
          {error && <p className="text-[13px] text-rose-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="btn-primary-violet w-full justify-center disabled:opacity-60"
          >
            {loading ? "Création…" : "Créer mon compte"}
          </button>
          <p className="text-center text-[13px] text-white/60">
            Déjà un compte ?{" "}
            <Link
              href="/login"
              className="font-medium text-violet-300 underline-offset-4 hover:underline"
            >
              Se connecter
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
