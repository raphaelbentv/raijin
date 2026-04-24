"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  Bell,
  Building2,
  FileText,
  Home,
  Plug,
  Search,
  Settings,
  Upload,
  Users,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { InvoiceStatus } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

// ────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────

interface InvoiceHit {
  id: string;
  source_file_name: string;
  invoice_number: string | null;
  status: InvoiceStatus;
}
interface SupplierHit {
  id: string;
  name: string;
  vat_number: string | null;
  country_code: string | null;
}
interface SearchResponse {
  invoices: InvoiceHit[];
  suppliers: SupplierHit[];
}

type NavItem = {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  keywords?: string[];
};

const NAV_ITEMS: NavItem[] = [
  { label: "Tableau de bord", href: "/dashboard", icon: Home, keywords: ["dashboard", "accueil"] },
  { label: "Factures", href: "/invoices", icon: FileText, keywords: ["invoices", "factures"] },
  { label: "Rapports", href: "/reports", icon: BarChart3, keywords: ["reports", "tva", "p&l"] },
  { label: "Fournisseurs", href: "/suppliers", icon: Building2, keywords: ["suppliers", "vendors"] },
  { label: "Importer", href: "/upload", icon: Upload, keywords: ["upload", "import"] },
  { label: "Intégrations", href: "/integrations", icon: Plug, keywords: ["outlook", "gmail", "drive", "mydata", "erp"] },
  { label: "Utilisateurs", href: "/admin/users", icon: Users, keywords: ["users", "équipe"] },
  { label: "Audit", href: "/admin/audit", icon: BarChart3, keywords: ["audit", "logs", "journal"] },
  { label: "Notifications", href: "/notifications", icon: Bell },
  { label: "Paramètres", href: "/settings", icon: Settings, keywords: ["settings", "preferences"] },
];

function flagForCountry(code: string | null): string {
  if (!code) return "🌐";
  const map: Record<string, string> = {
    GR: "🇬🇷",
    FR: "🇫🇷",
    DE: "🇩🇪",
    IT: "🇮🇹",
    ES: "🇪🇸",
    BE: "🇧🇪",
    NL: "🇳🇱",
    PT: "🇵🇹",
  };
  return map[code] ?? "🌐";
}

// ────────────────────────────────────────────────────────────
// Context (global open state)
// ────────────────────────────────────────────────────────────

interface CommandPaletteContextValue {
  open: () => void;
  close: () => void;
  isOpen: boolean;
}

const CommandPaletteContext = createContext<CommandPaletteContextValue | null>(null);

export function useCommandPalette(): CommandPaletteContextValue {
  const ctx = useContext(CommandPaletteContext);
  if (!ctx) throw new Error("useCommandPalette must be used within CommandPaletteProvider");
  return ctx;
}

export function CommandPaletteProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <CommandPaletteContext.Provider value={{ open, close, isOpen }}>
      {children}
      {isOpen && <CommandPalette onClose={close} />}
    </CommandPaletteContext.Provider>
  );
}

// ────────────────────────────────────────────────────────────
// Palette UI
// ────────────────────────────────────────────────────────────

type FlatResult =
  | { kind: "nav"; item: NavItem }
  | { kind: "invoice"; item: InvoiceHit }
  | { kind: "supplier"; item: SupplierHit };

function CommandPalette({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [remote, setRemote] = useState<SearchResponse>({ invoices: [], suppliers: [] });
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Debounce query → debounced
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 120);
    return () => clearTimeout(t);
  }, [query]);

  // Fetch remote results
  useEffect(() => {
    if (!debounced) {
      setRemote({ invoices: [], suppliers: [] });
      return;
    }
    let cancelled = false;
    apiFetch<SearchResponse>(`/search?q=${encodeURIComponent(debounced)}`)
      .then((data) => {
        if (!cancelled) setRemote(data);
      })
      .catch(() => {
        if (!cancelled) setRemote({ invoices: [], suppliers: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [debounced]);

  // Nav filter client-side
  const navResults = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return NAV_ITEMS;
    return NAV_ITEMS.filter((it) => {
      const hay = [it.label, ...(it.keywords ?? [])].join(" ").toLowerCase();
      return hay.includes(q);
    });
  }, [query]);

  const flat: FlatResult[] = useMemo(
    () => [
      ...navResults.map((item) => ({ kind: "nav", item }) as const),
      ...remote.invoices.map((item) => ({ kind: "invoice", item }) as const),
      ...remote.suppliers.map((item) => ({ kind: "supplier", item }) as const),
    ],
    [navResults, remote],
  );

  // Reset index when results change
  useEffect(() => {
    setActiveIdx(0);
  }, [flat.length, debounced]);

  // Keyboard navigation
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((i) => Math.min(flat.length - 1, i + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((i) => Math.max(0, i - 1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const hit = flat[activeIdx];
        if (!hit) return;
        if (hit.kind === "nav") router.push(hit.item.href as never);
        else if (hit.kind === "invoice") router.push(`/invoices/${hit.item.id}` as never);
        else router.push(`/suppliers/${hit.item.id}` as never);
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeIdx, flat, onClose, router]);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[12vh]"
      onClick={onClose}
      style={{ background: "rgba(0,0,0,0.55)", backdropFilter: "blur(8px)" }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="glass glass-glow w-[640px] max-w-[92vw] overflow-hidden"
        style={{ borderRadius: 18 }}
      >
        <div className="relative z-10">
          {/* Input bar */}
          <div className="flex items-center gap-3 border-b border-white/[0.06] px-4 py-3">
            <Search className="h-4 w-4 text-white/35" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher une facture, un fournisseur, une page…"
              className="flex-1 bg-transparent text-[14px] text-white placeholder:text-white/35 focus:outline-none"
            />
            <kbd className="raijin-kbd">ESC</kbd>
          </div>

          {/* Results */}
          <div className="max-h-[60vh] overflow-y-auto py-2">
            {flat.length === 0 && (
              <p className="py-10 text-center text-[13px] text-white/35">
                Aucun résultat pour « {query} »
              </p>
            )}

            {navResults.length > 0 && (
              <ResultGroup label="Navigation">
                {navResults.map((item, idx) => {
                  const globalIdx = idx;
                  return (
                    <NavRow
                      key={item.href}
                      item={item}
                      active={globalIdx === activeIdx}
                      onClick={() => {
                        router.push(item.href as never);
                        onClose();
                      }}
                    />
                  );
                })}
              </ResultGroup>
            )}

            {remote.invoices.length > 0 && (
              <ResultGroup label="Factures">
                {remote.invoices.map((inv, idx) => {
                  const globalIdx = navResults.length + idx;
                  return (
                    <InvoiceRow
                      key={inv.id}
                      item={inv}
                      active={globalIdx === activeIdx}
                      onClick={() => {
                        router.push(`/invoices/${inv.id}` as never);
                        onClose();
                      }}
                    />
                  );
                })}
              </ResultGroup>
            )}

            {remote.suppliers.length > 0 && (
              <ResultGroup label="Fournisseurs">
                {remote.suppliers.map((s, idx) => {
                  const globalIdx = navResults.length + remote.invoices.length + idx;
                  return (
                    <SupplierRow
                      key={s.id}
                      item={s}
                      active={globalIdx === activeIdx}
                      onClick={() => {
                        router.push(`/suppliers/${s.id}` as never);
                        onClose();
                      }}
                    />
                  );
                })}
              </ResultGroup>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between border-t border-white/[0.06] px-4 py-2 text-[11px] text-white/35">
            <div className="flex items-center gap-2">
              <span className="raijin-kbd">↑↓</span>
              <span>naviguer</span>
              <span className="raijin-kbd">↵</span>
              <span>ouvrir</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span>Raijin search</span>
              <span className="raijin-kbd">⌘K</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ResultGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="pb-1">
      <div className="px-4 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/35">
        {label}
      </div>
      <div>{children}</div>
    </div>
  );
}

function NavRow({
  item,
  active,
  onClick,
}: {
  item: NavItem;
  active: boolean;
  onClick: () => void;
}) {
  const Icon = item.icon;
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-3 px-4 py-2 text-left text-[13px] transition ${
        active
          ? "bg-violet-500/15 text-white"
          : "text-white/70 hover:bg-white/[0.04] hover:text-white"
      }`}
    >
      <Icon className={`h-[15px] w-[15px] ${active ? "text-violet-300" : "text-white/45"}`} />
      <span className="flex-1">{item.label}</span>
      <span className="text-[10px] text-white/30">Aller</span>
    </button>
  );
}

function InvoiceRow({
  item,
  active,
  onClick,
}: {
  item: InvoiceHit;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-3 px-4 py-2 text-left text-[13px] transition ${
        active
          ? "bg-violet-500/15 text-white"
          : "text-white/70 hover:bg-white/[0.04] hover:text-white"
      }`}
    >
      <FileText className={`h-[15px] w-[15px] ${active ? "text-violet-300" : "text-white/45"}`} />
      <div className="min-w-0 flex-1">
        <div className="truncate">{item.source_file_name}</div>
        {item.invoice_number && (
          <div className="font-mono-display text-[11px] text-white/40">{item.invoice_number}</div>
        )}
      </div>
      <StatusBadge status={item.status} />
    </button>
  );
}

function SupplierRow({
  item,
  active,
  onClick,
}: {
  item: SupplierHit;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-3 px-4 py-2 text-left text-[13px] transition ${
        active
          ? "bg-violet-500/15 text-white"
          : "text-white/70 hover:bg-white/[0.04] hover:text-white"
      }`}
    >
      <span className="text-[14px]">{flagForCountry(item.country_code)}</span>
      <div className="min-w-0 flex-1">
        <div className="truncate">{item.name}</div>
        {item.vat_number && (
          <div className="font-mono-display text-[11px] text-violet-300/70">
            {item.vat_number}
          </div>
        )}
      </div>
      <Building2 className="h-[13px] w-[13px] text-white/30" />
    </button>
  );
}
