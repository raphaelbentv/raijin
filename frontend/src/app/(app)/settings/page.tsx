"use client";

import { useEffect, useState } from "react";
import { Key, Shield, Sparkles, UserCircle } from "lucide-react";
import { toast } from "sonner";
import { ApiError, apiFetch } from "@/lib/api";
import type { ApiKey, User, UserSession } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";

type Tab = "profile" | "security" | "preferences";

const TABS: { value: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { value: "profile", label: "Profil", icon: UserCircle },
  { value: "security", label: "Sécurité", icon: Shield },
  { value: "preferences", label: "Préférences", icon: Sparkles },
];

const inputClass =
  "h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white placeholder:text-white/35 focus:border-violet-500/40 focus:outline-none focus:ring-1 focus:ring-violet-500/30 disabled:opacity-60";

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="glass p-6" style={{ borderRadius: 18 }}>
      <div className="relative z-10">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">
          {title}
        </h3>
        {description && (
          <p className="mt-1 text-[12px] text-white/45">{description}</p>
        )}
        <div className="mt-4 space-y-4">{children}</div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [tab, setTab] = useState<Tab>("profile");

  const [fullName, setFullName] = useState("");
  const [locale, setLocale] = useState("fr");
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [savingPwd, setSavingPwd] = useState(false);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [newKeyName, setNewKeyName] = useState("Integration key");
  const [newKeySecret, setNewKeySecret] = useState<string | null>(null);
  const [totpUrl, setTotpUrl] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [notificationPrefs, setNotificationPrefs] = useState<Record<string, { in_app: boolean; email: boolean }>>({});

  useEffect(() => {
    apiFetch<User>("/auth/me")
      .then((u) => {
        setUser(u);
        setFullName(u.full_name ?? "");
        setLocale(u.locale ?? "fr");
      })
      .catch(() => toast.error("Impossible de charger le profil"));
  }, []);

  useEffect(() => {
    if (tab === "security") {
      apiFetch<ApiKey[]>("/security/api-keys").then(setApiKeys).catch(() => {});
      apiFetch<UserSession[]>("/security/sessions").then(setSessions).catch(() => {});
    }
    if (tab === "preferences") {
      apiFetch<Record<string, { in_app: boolean; email: boolean }>>("/me/notification-preferences")
        .then(setNotificationPrefs)
        .catch(() => {});
    }
  }, [tab]);

  async function saveProfile() {
    if (!user) return;
    setSavingProfile(true);
    try {
      const updated = await apiFetch<User>("/me/profile", {
        method: "PATCH",
        json: { full_name: fullName || null, locale },
      });
      setUser(updated);
      toast.success("Profil enregistré");
      if (locale !== (user.locale ?? "fr")) {
        document.cookie = `raijin.locale=${locale}; path=/; max-age=31536000; SameSite=Lax`;
        window.location.reload();
      }
    } catch {
      toast.error("Enregistrement impossible");
    } finally {
      setSavingProfile(false);
    }
  }

  async function createApiKey() {
    try {
      const created = await apiFetch<{ api_key: ApiKey; secret: string }>("/security/api-keys", {
        method: "POST",
        json: {
          name: newKeyName,
          scopes: ["invoices:read", "invoices:write"],
        },
      });
      setApiKeys((items) => [created.api_key, ...items]);
      setNewKeySecret(created.secret);
      toast.success("Clé API créée");
    } catch {
      toast.error("Impossible de créer la clé");
    }
  }

  async function revokeApiKey(id: string) {
    await apiFetch(`/security/api-keys/${id}/revoke`, { method: "POST" });
    setApiKeys((items) =>
      items.map((item) => (item.id === id ? { ...item, revoked_at: new Date().toISOString() } : item)),
    );
  }

  async function setupTotp() {
    const setup = await apiFetch<{ otpauth_url: string; backup_codes: string[] }>("/security/totp/setup", { method: "POST" });
    setTotpUrl(setup.otpauth_url);
    setBackupCodes(setup.backup_codes);
    toast.success("Secret 2FA généré");
  }

  async function enableTotp() {
    await apiFetch("/security/totp/enable", { method: "POST", json: { code: totpCode } });
    setUser((u) => (u ? { ...u, totp_enabled: true } : u));
    toast.success("2FA activée");
  }

  async function saveNotificationPrefs() {
    await apiFetch("/me/notification-preferences", {
      method: "PUT",
      json: { preferences: notificationPrefs },
    });
    toast.success("Préférences enregistrées");
  }

  async function savePassword() {
    if (newPassword !== confirmPassword) {
      toast.error("Les deux mots de passe ne correspondent pas");
      return;
    }
    if (newPassword.length < 8) {
      toast.error("Au moins 8 caractères");
      return;
    }
    setSavingPwd(true);
    try {
      await apiFetch("/me/password", {
        method: "POST",
        json: { current_password: currentPassword, new_password: newPassword },
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast.success("Mot de passe mis à jour");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        toast.error("Mot de passe actuel incorrect");
      } else {
        toast.error("Changement impossible");
      }
    } finally {
      setSavingPwd(false);
    }
  }

  if (!user) return <p className="text-sm text-white/50">Chargement…</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif-italic text-[30px] leading-none text-white/95">
          Paramètres
        </h1>
        <p className="mt-1 text-[13px] text-white/60">
          Gère ton profil, ta sécurité et tes préférences.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1.5">
        {TABS.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            onClick={() => setTab(value)}
            className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[12px] font-medium transition ${
              tab === value
                ? "text-white"
                : "bg-white/[0.05] text-white/60 hover:bg-white/[0.08]"
            }`}
            style={
              tab === value
                ? {
                    background:
                      "linear-gradient(90deg, rgba(139,92,246,0.3) 0%, rgba(99,102,241,0.2) 100%)",
                    border: "1px solid rgba(139,92,246,0.4)",
                  }
                : { border: "1px solid rgba(255,255,255,0.06)" }
            }
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {tab === "profile" && (
        <div className="max-w-2xl space-y-4">
          <Section title="Identité" description="Ces informations sont visibles par ton équipe.">
            <div className="space-y-1.5">
              <Label className="text-[11px] text-white/55">Email</Label>
              <input
                value={user.email}
                disabled
                className={`${inputClass} cursor-not-allowed font-mono-display`}
              />
              <p className="text-[11px] text-white/35">
                L&apos;email ne peut pas être modifié. Pour en changer, contacte un admin.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="settings-full-name" className="text-[11px] text-white/55">Nom complet</Label>
              <Input
                id="settings-full-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="border-white/10 bg-white/[0.04] text-white placeholder:text-white/35 focus-visible:ring-violet-500/50"
                placeholder="Prénom Nom"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-[11px] text-white/55">Rôle</Label>
              <div className="flex items-center gap-2">
                <span
                  className="inline-flex items-center gap-1.5 rounded-full border border-violet-500/40 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-violet-300"
                  style={{
                    background:
                      "linear-gradient(90deg, rgba(139,92,246,0.2), rgba(99,102,241,0.2))",
                  }}
                >
                  {user.role}
                </span>
                <span className="text-[11px] text-white/45">
                  · {user.tenant.name}
                </span>
              </div>
            </div>
            <div>
              <button
                onClick={saveProfile}
                disabled={savingProfile}
                className="btn-primary-violet disabled:opacity-60"
              >
                {savingProfile ? "Enregistrement…" : "Enregistrer"}
              </button>
            </div>
          </Section>
        </div>
      )}

      {tab === "security" && (
        <div className="max-w-2xl space-y-4">
          <Section
            title="Mot de passe"
            description="Au moins 8 caractères. Choisis une phrase unique et non réutilisée."
          >
            <div className="space-y-1.5">
              <Label htmlFor="settings-current-password" className="text-[11px] text-white/55">Mot de passe actuel</Label>
              <PasswordInput
                id="settings-current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
                className="border-white/10 bg-white/[0.04] text-white placeholder:text-white/35 focus-visible:ring-violet-500/50"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="settings-new-password" className="text-[11px] text-white/55">Nouveau</Label>
                <PasswordInput
                  id="settings-new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  className="border-white/10 bg-white/[0.04] text-white placeholder:text-white/35 focus-visible:ring-violet-500/50"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="settings-confirm-password" className="text-[11px] text-white/55">Confirmer</Label>
                <PasswordInput
                  id="settings-confirm-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  className="border-white/10 bg-white/[0.04] text-white placeholder:text-white/35 focus-visible:ring-violet-500/50"
                />
              </div>
            </div>
            <div>
              <button
                onClick={savePassword}
                disabled={savingPwd || !currentPassword || !newPassword}
                className="btn-primary-violet disabled:opacity-60"
              >
                {savingPwd ? "Mise à jour…" : "Changer le mot de passe"}
              </button>
            </div>
          </Section>

          <Section
            title="Clés API"
            description="Créer des tokens longue durée pour les intégrations tierces."
          >
            <div className="flex gap-2">
              <Input
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                className="border-white/10 bg-white/[0.04] text-white"
              />
              <button className="btn-primary-violet" onClick={createApiKey}>
                Créer
              </button>
            </div>
            {newKeySecret && (
              <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-3 font-mono text-[11px] text-emerald-100">
                {newKeySecret}
              </div>
            )}
            <div className="space-y-2">
              {apiKeys.map((key) => (
                <div
                  key={key.id}
                  className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5"
                >
                  <div>
                    <p className="text-[13px] text-white/80">{key.name}</p>
                    <p className="font-mono text-[11px] text-white/35">
                      {key.key_prefix} · {key.scopes.join(", ")}
                    </p>
                  </div>
                  <button
                    className="btn-glass disabled:opacity-40"
                    disabled={Boolean(key.revoked_at)}
                    onClick={() => revokeApiKey(key.id)}
                  >
                    {key.revoked_at ? "Révoquée" : "Révoquer"}
                  </button>
                </div>
              ))}
            </div>
          </Section>

          <Section title="2FA TOTP" description="Prépare un secret compatible Authenticator.">
            <div className="flex gap-2">
              <button className="btn-glass" onClick={setupTotp}>Générer</button>
              <Input
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                placeholder="Code 6 chiffres"
                className="max-w-[160px] border-white/10 bg-white/[0.04] font-mono text-white"
              />
              <button className="btn-primary-violet" onClick={enableTotp} disabled={!totpUrl || !totpCode}>
                {user.totp_enabled ? "Activée" : "Activer"}
              </button>
            </div>
            {totpUrl && (
              <div className="space-y-2">
                <p className="break-all rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 font-mono text-[11px] text-white/55">
                  {totpUrl}
                </p>
                {backupCodes.length > 0 && (
                  <div className="grid gap-1 rounded-lg border border-amber-300/20 bg-amber-300/10 p-3 font-mono text-[11px] text-amber-100 sm:grid-cols-2">
                    {backupCodes.map((code) => (
                      <span key={code}>{code}</span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Section>

          <Section title="Sessions" description="Connexions récentes et révocation à distance.">
            <div className="space-y-2">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 text-[12px]"
                >
                  <p className="text-white/80">{session.ip_address ?? "IP inconnue"}</p>
                  <p className="truncate text-white/35">{session.user_agent ?? "User agent absent"}</p>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}

      {tab === "preferences" && (
        <div className="max-w-2xl space-y-4">
          <Section title="Langue" description="Langue de l'interface.">
            <div className="space-y-1.5">
              <Label className="text-[11px] text-white/55">Langue</Label>
              <select
                value={locale}
                onChange={(e) => setLocale(e.target.value)}
                className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white"
              >
                <option value="fr">Français</option>
                <option value="en">English</option>
                <option value="el">Ελληνικά</option>
              </select>
              <p className="text-[11px] text-white/35">
                La préférence est stockée sur ton profil et utilisée côté backend.
              </p>
              <button className="btn-glass" onClick={saveProfile}>
                Enregistrer la langue
              </button>
            </div>
          </Section>

          <Section title="Notifications" description="Choisis ce qui t'arrive en live.">
            {[
              { key: "invoice_ready", label: "Factures prêtes à valider" },
              { key: "invoice_failed", label: "Échecs OCR" },
              { key: "integration_synced", label: "Sync Outlook / Gmail / Drive" },
              { key: "mydata_submitted", label: "Soumissions myDATA" },
              { key: "erp_exported", label: "Exports ERP" },
            ].map((n) => (
              <div
                key={n.key}
                className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5"
              >
                <span className="text-[13px] text-white/80">{n.label}</span>
                <div className="flex items-center gap-3 text-[11px] text-white/55">
                  <label className="flex items-center gap-1">
                    <input
                      type="checkbox"
                      checked={notificationPrefs[n.key]?.in_app ?? true}
                      onChange={(e) =>
                        setNotificationPrefs((prefs) => ({
                          ...prefs,
                          [n.key]: {
                            in_app: e.target.checked,
                            email: prefs[n.key]?.email ?? false,
                          },
                        }))
                      }
                    />
                    App
                  </label>
                  <label className="flex items-center gap-1">
                    <input
                      type="checkbox"
                      checked={notificationPrefs[n.key]?.email ?? false}
                      onChange={(e) =>
                        setNotificationPrefs((prefs) => ({
                          ...prefs,
                          [n.key]: {
                            in_app: prefs[n.key]?.in_app ?? true,
                            email: e.target.checked,
                          },
                        }))
                      }
                    />
                    Email
                  </label>
                </div>
              </div>
            ))}
            <button className="btn-primary-violet" onClick={saveNotificationPrefs}>
              Enregistrer les préférences
            </button>
          </Section>

          <Section
            title="Mes données"
            description="Exporte ou demande la suppression de tes données personnelles (RGPD)."
          >
            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                className="btn-glass"
                onClick={async () => {
                  try {
                    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:6200";
                    const token = (await import("@/lib/auth")).getAccessToken();
                    const res = await fetch(`${apiUrl}/security/gdpr/export`, {
                      headers: token ? { Authorization: `Bearer ${token}` } : {},
                    });
                    if (!res.ok) throw new Error(`status_${res.status}`);
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "raijin-gdpr-export.zip";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    toast.success("Export téléchargé");
                  } catch {
                    toast.error("Export impossible");
                  }
                }}
              >
                Télécharger mes données (.zip)
              </button>
              <button
                className="btn-glass text-rose-200 hover:text-rose-100"
                onClick={async () => {
                  if (!confirm("Demander la suppression de ton compte et de toutes tes données sous 30 jours ?")) return;
                  try {
                    await apiFetch("/security/gdpr/delete-request", { method: "POST" });
                    toast.success("Demande de suppression enregistrée. Tu recevras une confirmation par email.");
                  } catch (err) {
                    const msg = err instanceof ApiError ? `Erreur ${err.status}` : "Erreur réseau";
                    toast.error(msg);
                  }
                }}
              >
                Demander la suppression
              </button>
            </div>
            <p className="text-[11px] text-white/35">
              L&apos;export inclut ton profil, tes factures, tes fournisseurs et tes sessions. La suppression est planifiée à +30 jours et réversible pendant cette période.
            </p>
          </Section>
        </div>
      )}
    </div>
  );
}
