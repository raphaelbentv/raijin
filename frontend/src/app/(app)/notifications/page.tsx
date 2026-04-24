"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Bell,
  Check,
  FileCheck,
  Mail,
  Plug,
  Sparkles,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api";

type NotificationKind =
  | "invoice_ready"
  | "invoice_failed"
  | "integration_synced"
  | "integration_error"
  | "mydata_submitted"
  | "erp_exported"
  | "system";

interface Notification {
  id: string;
  kind: NotificationKind;
  title: string;
  body: string | null;
  entity_type: string | null;
  entity_id: string | null;
  is_read: boolean;
  created_at: string;
}

interface NotificationListResponse {
  items: Notification[];
  total: number;
  unread: number;
}

const ICONS: Record<NotificationKind, React.ComponentType<{ className?: string }>> = {
  invoice_ready: FileCheck,
  invoice_failed: AlertTriangle,
  integration_synced: Mail,
  integration_error: Plug,
  mydata_submitted: Upload,
  erp_exported: Upload,
  system: Sparkles,
};

const COLORS: Record<NotificationKind, string> = {
  invoice_ready: "text-violet-300",
  invoice_failed: "text-rose-300",
  integration_synced: "text-emerald-300",
  integration_error: "text-amber-300",
  mydata_submitted: "text-sky-300",
  erp_exported: "text-sky-300",
  system: "text-white/70",
};

function formatRel(iso: string): string {
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  if (diff < 60_000) return "à l'instant";
  if (diff < 3_600_000) return `il y a ${Math.round(diff / 60_000)} min`;
  if (diff < 86_400_000) return `il y a ${Math.round(diff / 3_600_000)} h`;
  return d.toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function entityHref(n: Notification): string | null {
  if (n.entity_type === "invoice" && n.entity_id) return `/invoices/${n.entity_id}`;
  if (n.entity_type === "email_source") return "/integrations";
  return null;
}

export default function NotificationsPage() {
  const [data, setData] = useState<NotificationListResponse | null>(null);
  const [filter, setFilter] = useState<"all" | "unread">("all");

  const load = useCallback(async () => {
    try {
      const qs = filter === "unread" ? "?unread_only=true&limit=80" : "?limit=80";
      const res = await apiFetch<NotificationListResponse>(`/notifications${qs}`);
      setData(res);
    } catch {
      toast.error("Impossible de charger les notifications");
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function markOne(id: string) {
    try {
      await apiFetch(`/notifications/${id}/read`, { method: "POST" });
      await load();
    } catch {
      toast.error("Action impossible");
    }
  }

  async function markAll() {
    try {
      await apiFetch("/notifications/read-all", { method: "POST" });
      toast.success("Toutes les notifications marquées lues");
      await load();
    } catch {
      toast.error("Action impossible");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-serif-italic text-[30px] leading-none text-white/95">
            Notifications
          </h1>
          <p className="mt-1 text-[13px] text-white/60">
            {data
              ? `${data.total} au total · ${data.unread} non lue${data.unread > 1 ? "s" : ""}`
              : "Chargement…"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data && data.unread > 0 && (
            <button onClick={markAll} className="btn-glass">
              <Check className="h-3.5 w-3.5" />
              Tout marquer lu
            </button>
          )}
        </div>
      </div>

      <div className="flex gap-1.5">
        {(["all", "unread"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1 text-[12px] font-medium transition ${
              filter === f
                ? "text-white"
                : "bg-white/[0.05] text-white/60 hover:bg-white/[0.08]"
            }`}
            style={
              filter === f
                ? {
                    background:
                      "linear-gradient(90deg, rgba(139,92,246,0.3) 0%, rgba(99,102,241,0.2) 100%)",
                    border: "1px solid rgba(139,92,246,0.4)",
                  }
                : { border: "1px solid rgba(255,255,255,0.06)" }
            }
          >
            {f === "all" ? "Toutes" : "Non lues"}
          </button>
        ))}
      </div>

      <div className="glass overflow-hidden" style={{ borderRadius: 18 }}>
        <div className="relative z-10">
          {data && data.items.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-16 text-center text-[13px] text-white/45">
              <Bell className="h-8 w-8 text-white/20" />
              <p>Aucune notification.</p>
            </div>
          ) : (
            <ul className="divide-y divide-white/[0.04]">
              {data?.items.map((n) => {
                const Icon = ICONS[n.kind] ?? Bell;
                const href = entityHref(n);
                const inner = (
                  <>
                    <div
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-white/[0.06] bg-white/[0.03] ${COLORS[n.kind]}`}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-3">
                        <p
                          className={`text-[13px] ${
                            n.is_read ? "text-white/60" : "font-medium text-white/95"
                          }`}
                        >
                          {n.title}
                        </p>
                        <span className="shrink-0 font-mono-display text-[10px] text-white/35">
                          {formatRel(n.created_at)}
                        </span>
                      </div>
                      {n.body && (
                        <p className="mt-0.5 text-[12px] leading-snug text-white/45">
                          {n.body}
                        </p>
                      )}
                    </div>
                    {!n.is_read && (
                      <span className="h-2 w-2 shrink-0 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(139,92,246,0.6)]" />
                    )}
                  </>
                );

                return (
                  <li
                    key={n.id}
                    className={`transition hover:bg-white/[0.02] ${n.is_read ? "" : "bg-violet-500/[0.03]"}`}
                  >
                    {href ? (
                      <Link
                        href={href}
                        onClick={() => !n.is_read && void markOne(n.id)}
                        className="flex items-start gap-3 px-5 py-3.5"
                      >
                        {inner}
                      </Link>
                    ) : (
                      <button
                        onClick={() => !n.is_read && void markOne(n.id)}
                        className="flex w-full items-start gap-3 px-5 py-3.5 text-left"
                      >
                        {inner}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
