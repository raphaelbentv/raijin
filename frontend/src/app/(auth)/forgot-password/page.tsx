"use client";

import Link from "next/link";
import { useState } from "react";
import { Mail, Zap } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface ForgotPasswordResponse {
  ok: boolean;
  reset_link: string | null;
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await apiFetch<ForgotPasswordResponse>("/auth/forgot-password", {
        method: "POST",
        auth: false,
        json: { email },
      });
      setSent(true);
      setDevLink(response.reset_link);
    } catch {
      setError("Impossible d'envoyer le lien pour le moment.");
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
          Mot de passe oublié
        </h1>
        <p className="mt-1 text-[13px] text-white/60">
          Entre ton email, on t&apos;envoie un lien valable 1 heure.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email" className="text-white/80">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="border-white/10 bg-white/[0.04] text-white placeholder:text-white/35 focus-visible:ring-violet-500/50"
            />
          </div>
          {error && <p className="text-[13px] text-rose-400">{error}</p>}
          {sent && (
            <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 px-3 py-2 text-[13px] text-emerald-100">
              Email envoyé si ce compte existe.
              {devLink && (
                <a
                  href={devLink}
                  className="mt-2 flex items-center gap-2 font-medium text-violet-200 underline-offset-4 hover:underline"
                >
                  <Mail className="h-4 w-4" />
                  Ouvrir le lien de reset dev
                </a>
              )}
            </div>
          )}
          <button
            type="submit"
            disabled={loading}
            className="btn-primary-violet w-full justify-center disabled:opacity-60"
          >
            {loading ? "Envoi…" : "Envoyer le lien"}
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
