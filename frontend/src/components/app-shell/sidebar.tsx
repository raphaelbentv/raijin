"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  BarChart3,
  Bell,
  Building2,
  FileText,
  Home,
  LogOut,
  Plug,
  Search,
  Settings,
  Shield,
  Sparkles,
  Upload,
  Users,
  Zap,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { clearTokens } from "@/lib/auth";
import type { User } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useCommandPalette } from "@/components/command-palette";

interface NavItem {
  labelKey: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  adminOnly?: boolean;
  badge?: number;
}

const MAIN_NAV: NavItem[] = [
  { labelKey: "dashboard", href: "/dashboard", icon: Home },
  { labelKey: "invoices", href: "/invoices", icon: FileText },
  { labelKey: "reports", href: "/reports", icon: BarChart3 },
  { labelKey: "suppliers", href: "/suppliers", icon: Building2 },
  { labelKey: "upload", href: "/upload", icon: Upload },
  { labelKey: "integrations", href: "/integrations", icon: Plug, adminOnly: true },
];

const ADMIN_NAV_BASE: NavItem[] = [
  { labelKey: "users", href: "/admin/users", icon: Users, adminOnly: true },
  { labelKey: "audit", href: "/admin/audit", icon: BarChart3 },
  { labelKey: "ip_rules", href: "/admin/security/ip-rules", icon: Shield, adminOnly: true },
  { labelKey: "saml", href: "/admin/security/saml", icon: Shield, adminOnly: true },
  { labelKey: "notifications", href: "/notifications", icon: Bell },
  { labelKey: "settings", href: "/settings", icon: Settings },
];

function NavRow({
  item,
  active,
  label,
}: {
  item: NavItem;
  active: boolean;
  label: string;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "relative flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[13px] font-medium transition",
        active
          ? "text-white"
          : "text-white/60 hover:bg-white/[0.05] hover:text-white/95",
      )}
      style={
        active
          ? {
              background:
                "linear-gradient(90deg, rgba(139,92,246,0.25) 0%, rgba(99,102,241,0.15) 100%)",
              border: "1px solid rgba(139,92,246,0.25)",
              boxShadow:
                "0 0 20px rgba(139,92,246,0.12), inset 0 1px 0 rgba(255,255,255,0.08)",
            }
          : undefined
      }
    >
      <Icon className={cn("h-[15px] w-[15px] shrink-0", active && "text-violet-300")} />
      <span className="flex-1">{label}</span>
      {item.badge !== undefined && (
        <span
          className="ml-auto rounded-full px-1.5 py-[1px] text-[10px] font-semibold text-violet-200"
          style={{
            background: "rgba(139,92,246,0.4)",
            border: "1px solid rgba(139,92,246,0.5)",
          }}
        >
          {item.badge}
        </span>
      )}
    </Link>
  );
}

export function Sidebar({ user }: { user: User | null }) {
  const pathname = usePathname();
  const router = useRouter();
  const isAdmin = user?.role === "admin";
  const cmd = useCommandPalette();
  const tApp = useTranslations("app");
  const tNav = useTranslations("nav");
  const tPromo = useTranslations("promo");
  const [unread, setUnread] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    function fetchUnread() {
      apiFetch<{ unread: number }>("/notifications?limit=1")
        .then((r) => {
          if (!cancelled) setUnread(r.unread);
        })
        .catch(() => {});
    }
    fetchUnread();
    const t = setInterval(fetchUnread, 60_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [pathname]);

  const ADMIN_NAV: NavItem[] = ADMIN_NAV_BASE.map((item) =>
    item.href === "/notifications"
      ? { ...item, badge: unread > 0 ? unread : undefined }
      : item,
  );

  const initials = (user?.full_name ?? user?.email ?? "??")
    .split(/[@.\s]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase())
    .join("");

  function logout() {
    clearTokens();
    router.replace("/login");
  }

  function isActive(href: string): boolean {
    if (href === "/dashboard") return pathname === "/dashboard";
    return pathname.startsWith(href);
  }

  return (
    <aside
      className="relative flex h-screen w-[240px] shrink-0 flex-col overflow-hidden px-3.5 py-5"
      style={{
        background: "rgba(255,255,255,0.025)",
        backdropFilter: "blur(40px) saturate(160%)",
        WebkitBackdropFilter: "blur(40px) saturate(160%)",
        borderRight: "1px solid var(--glass-border)",
      }}
    >
      <div className="pointer-events-none absolute inset-0" style={{ background: "var(--glass-reflex)" }} />

      <div className="relative flex flex-1 flex-col">
        {/* Logo */}
        <div className="mb-4 flex items-center gap-2.5 border-b border-white/[0.08] px-2 pb-5 pt-1">
          <div
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
            style={{
              background: "linear-gradient(135deg, #8b5cf6, #6366f1)",
              boxShadow: "0 0 20px rgba(139,92,246,0.4)",
            }}
          >
            <Zap className="h-4 w-4 text-white" />
          </div>
          <span className="flex-1 text-base font-semibold tracking-tight text-white/95">
            Raijin
          </span>
          {isAdmin && (
            <span
              className="rounded-full border px-1.5 py-[2px] text-[9px] font-semibold uppercase tracking-[0.08em] text-violet-300"
              style={{
                background:
                  "linear-gradient(90deg, rgba(139,92,246,0.3), rgba(99,102,241,0.3))",
                borderColor: "rgba(139,92,246,0.4)",
              }}
            >
              {tApp("admin_badge")}
            </span>
          )}
        </div>

        {/* Search */}
        <button
          type="button"
          className="mb-5 flex w-full items-center gap-2 rounded-[10px] border border-white/[0.08] bg-white/[0.04] px-2.5 py-2 transition hover:border-white/[0.14] hover:bg-white/[0.07]"
          onClick={cmd.open}
        >
          <Search className="h-[14px] w-[14px] shrink-0 text-white/35" />
          <span className="flex-1 text-left text-[12px] text-white/35">{tApp("search_placeholder")}</span>
          <span className="raijin-kbd">⌘K</span>
        </button>

        {/* Main nav */}
        <nav className="space-y-0.5">
          {MAIN_NAV.filter((i) => !i.adminOnly || isAdmin).map((item) => (
            <NavRow key={item.href} item={item} active={isActive(item.href)} label={tNav(item.labelKey)} />
          ))}
        </nav>

        {/* Admin group */}
        <div className="mt-4">
          <div className="px-2.5 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/35">
            {tNav("section_admin")}
          </div>
          <nav className="space-y-0.5">
            {ADMIN_NAV.filter((i) => !i.adminOnly || isAdmin).map((item) => (
              <NavRow key={item.href} item={item} active={isActive(item.href)} label={tNav(item.labelKey)} />
            ))}
          </nav>
        </div>

        {/* Promo */}
        <div
          className="relative mb-3 mt-auto overflow-hidden rounded-2xl border p-4"
          style={{
            background: "rgba(255,255,255,0.05)",
            borderColor: "rgba(139,92,246,0.2)",
            boxShadow: "0 0 30px rgba(139,92,246,0.1)",
          }}
        >
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-3/5"
            style={{
              background:
                "linear-gradient(180deg, rgba(139,92,246,0.08) 0%, transparent 100%)",
            }}
          />
          <div className="relative">
            <div className="mb-2 inline-flex items-center gap-1 text-[10px] font-semibold text-violet-300">
              <Sparkles className="h-3 w-3" />
              {tPromo("mydata_title")}
            </div>
            <p className="font-serif-italic mb-1.5 text-[15px] leading-tight text-white/95">
              {tPromo("mydata_title")}
            </p>
            <p className="mb-3 text-[11px] leading-[1.5] text-white/35">
              {tPromo("mydata_desc")}
            </p>
            <Link
              href="/integrations"
              className="block rounded-lg px-4 py-2 text-center text-[12px] font-semibold text-white transition"
              style={{
                background: "linear-gradient(90deg, #8b5cf6, #6366f1)",
                boxShadow: "0 8px 24px -8px rgba(139,92,246,0.6)",
              }}
            >
              {tPromo("mydata_cta")}
            </Link>
          </div>
        </div>

        {/* Profile */}
        <button
          type="button"
          onClick={logout}
          className="flex items-center gap-2.5 rounded-xl border border-transparent p-2.5 transition hover:border-white/[0.08] hover:bg-white/[0.04]"
        >
          <div
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
            style={{
              background: "linear-gradient(135deg, #8b5cf6, #a855f7)",
              boxShadow: "0 0 12px rgba(139,92,246,0.4)",
            }}
          >
            {initials || "??"}
          </div>
          <div className="min-w-0 flex-1 text-left">
            <div className="truncate text-[13px] font-medium text-white/95">
              {user?.full_name ?? "—"}
            </div>
            <div className="truncate text-[11px] text-white/35">
              {user?.email ?? ""}
            </div>
          </div>
          <LogOut className="h-[14px] w-[14px] shrink-0 text-white/35" />
        </button>
      </div>
    </aside>
  );
}
