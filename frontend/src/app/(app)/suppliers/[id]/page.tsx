"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Edit3, GitMerge, Mail, MapPin, Phone, Save, Search, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { InvoiceStatus } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

interface SupplierInvoiceItem {
  id: string;
  source_file_name: string;
  invoice_number: string | null;
  issue_date: string | null;
  total_ttc: number | null;
  currency: string;
  status: InvoiceStatus;
}

interface Supplier {
  id: string;
  name: string;
  vat_number: string | null;
  country_code: string | null;
  city: string | null;
  email: string | null;
  phone: string | null;
  created_at: string;
}

interface SupplierListItem extends Supplier {
  invoice_count: number;
  total_ttc: number | null;
}

interface SupplierListResponse {
  items: SupplierListItem[];
  total: number;
  page: number;
  page_size: number;
}

interface SupplierStats {
  invoice_count: number;
  confirmed_count: number;
  total_ttc: number;
  avg_ttc: number;
  last_invoice_date: string | null;
  first_invoice_date: string | null;
}

type SupplierFormState = {
  name: string;
  vat_number: string;
  country_code: string;
  city: string;
  email: string;
  phone: string;
};

function formFromSupplier(supplier: Supplier): SupplierFormState {
  return {
    name: supplier.name,
    vat_number: supplier.vat_number ?? "",
    country_code: supplier.country_code ?? "",
    city: supplier.city ?? "",
    email: supplier.email ?? "",
    phone: supplier.phone ?? "",
  };
}

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

function formatMoney(amount: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function Kpi({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: "serif" | "mono";
}) {
  return (
    <div className="glass p-5" style={{ borderRadius: 18 }}>
      <div className="relative z-10">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/35">
          {label}
        </div>
        <div
          className={
            accent === "mono"
              ? "font-mono-display text-[28px] leading-none text-white/95"
              : "font-serif-display text-[36px] leading-none text-white/95"
          }
        >
          {value}
        </div>
        {hint && <div className="mt-2 text-[11px] text-white/45">{hint}</div>}
      </div>
    </div>
  );
}

export default function SupplierDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [stats, setStats] = useState<SupplierStats | null>(null);
  const [invoices, setInvoices] = useState<SupplierInvoiceItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<SupplierFormState | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [mergeOpen, setMergeOpen] = useState(false);
  const [mergeSearch, setMergeSearch] = useState("");
  const [mergeCandidates, setMergeCandidates] = useState<SupplierListItem[]>([]);
  const [mergingId, setMergingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, st, inv] = await Promise.all([
        apiFetch<Supplier>(`/suppliers/${id}`),
        apiFetch<SupplierStats>(`/suppliers/${id}/stats`),
        apiFetch<SupplierInvoiceItem[]>(`/suppliers/${id}/invoices?limit=50`),
      ]);
      setSupplier(s);
      setForm(formFromSupplier(s));
      setStats(st);
      setInvoices(inv);
    } catch {
      setError("Impossible de charger le fournisseur.");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!mergeOpen || mergeSearch.trim().length < 2) {
      setMergeCandidates([]);
      return;
    }
    const t = setTimeout(() => {
      apiFetch<SupplierListResponse>(
        `/suppliers?search=${encodeURIComponent(mergeSearch)}&page_size=8`,
      )
        .then((response) =>
          setMergeCandidates(response.items.filter((item) => item.id !== id)),
        )
        .catch(() => setMergeCandidates([]));
    }, 250);
    return () => clearTimeout(t);
  }, [id, mergeOpen, mergeSearch]);

  async function saveSupplier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiFetch<Supplier>(`/suppliers/${id}`, {
        method: "PATCH",
        json: form,
      });
      setSupplier(updated);
      setForm(formFromSupplier(updated));
      setEditing(false);
      await load();
    } catch {
      setError("Impossible d'enregistrer ce fournisseur. Vérifie le VAT ou réessaie.");
    } finally {
      setSaving(false);
    }
  }

  async function mergeSupplier(sourceId: string) {
    setMergingId(sourceId);
    setError(null);
    try {
      await apiFetch<Supplier>(`/suppliers/${id}/merge`, {
        method: "POST",
        json: { source_supplier_id: sourceId },
      });
      setMergeOpen(false);
      setMergeSearch("");
      setMergeCandidates([]);
      await load();
    } catch {
      setError("Impossible de fusionner ces fournisseurs.");
    } finally {
      setMergingId(null);
    }
  }

  if (error) return <p className="text-sm text-rose-400">{error}</p>;
  if (!supplier) return <p className="text-sm text-white/50">Chargement…</p>;

  const related = invoices;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          href="/suppliers"
          className="mb-3 inline-flex items-center gap-1 text-[12px] text-white/45 transition hover:text-white/80"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Fournisseurs
        </Link>
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div>
            <h1 className="font-serif-italic flex items-center gap-3 text-[34px] leading-tight text-white/95">
              <span className="text-[28px]">{flagForCountry(supplier.country_code)}</span>
              {supplier.name}
            </h1>
            <div className="mt-1 flex flex-wrap gap-4 text-[12px] text-white/45">
              {supplier.vat_number && (
                <span className="font-mono-display text-violet-300/80">
                  {supplier.vat_number}
                </span>
              )}
              {supplier.city && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {supplier.city}
                </span>
              )}
              {supplier.email && (
                <span className="flex items-center gap-1">
                  <Mail className="h-3.5 w-3.5" />
                  {supplier.email}
                </span>
              )}
              {supplier.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="h-3.5 w-3.5" />
                  {supplier.phone}
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setEditing((value) => !value);
                setForm(formFromSupplier(supplier));
              }}
              className="btn-glass"
            >
              {editing ? <X className="h-4 w-4" /> : <Edit3 className="h-4 w-4" />}
              {editing ? "Annuler" : "Modifier"}
            </button>
            <button
              type="button"
              onClick={() => setMergeOpen((value) => !value)}
              className="btn-glass"
            >
              <GitMerge className="h-4 w-4" />
              Fusionner
            </button>
            <div className="text-[11px] text-white/35">
              Fournisseur depuis {formatDate(supplier.created_at)}
            </div>
          </div>
        </div>
      </div>

      {editing && form && (
        <form
          onSubmit={saveSupplier}
          className="glass grid gap-3 p-5 md:grid-cols-6"
          style={{ borderRadius: 18 }}
        >
          <div className="relative z-10 md:col-span-2">
            <label
              htmlFor="supplier-edit-name"
              className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.10em] text-white/35"
            >
              Nom
            </label>
            <input
              id="supplier-edit-name"
              required
              value={form.name}
              onChange={(e) => setForm((f) => f && { ...f, name: e.target.value })}
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          <div className="relative z-10">
            <label
              htmlFor="supplier-edit-vat"
              className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.10em] text-white/35"
            >
              VAT
            </label>
            <input
              id="supplier-edit-vat"
              value={form.vat_number}
              onChange={(e) => setForm((f) => f && { ...f, vat_number: e.target.value })}
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 font-mono-display text-[13px] text-white focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          <div className="relative z-10">
            <label
              htmlFor="supplier-edit-country"
              className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.10em] text-white/35"
            >
              Pays
            </label>
            <input
              id="supplier-edit-country"
              maxLength={2}
              value={form.country_code}
              onChange={(e) =>
                setForm((f) => f && { ...f, country_code: e.target.value.toUpperCase() })
              }
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 font-mono-display text-[13px] text-white focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          <div className="relative z-10">
            <label
              htmlFor="supplier-edit-city"
              className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.10em] text-white/35"
            >
              Ville
            </label>
            <input
              id="supplier-edit-city"
              value={form.city}
              onChange={(e) => setForm((f) => f && { ...f, city: e.target.value })}
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          <div className="relative z-10">
            <label
              htmlFor="supplier-edit-email"
              className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.10em] text-white/35"
            >
              Email
            </label>
            <input
              id="supplier-edit-email"
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => f && { ...f, email: e.target.value })}
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          <div className="relative z-10 md:col-span-6 flex justify-end gap-2">
            <input
              value={form.phone}
              onChange={(e) => setForm((f) => f && { ...f, phone: e.target.value })}
              placeholder="Téléphone"
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white placeholder:text-white/35 focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20 md:max-w-[240px]"
            />
            <button type="submit" className="btn-primary-violet" disabled={saving}>
              <Save className="h-4 w-4" />
              {saving ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </form>
      )}

      {mergeOpen && (
        <div className="glass p-5" style={{ borderRadius: 18 }}>
          <div className="relative z-10">
            <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.10em] text-white/35">
              Fusion de doublon
            </label>
            <div className="relative max-w-xl">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" />
              <input
                value={mergeSearch}
                onChange={(e) => setMergeSearch(e.target.value)}
                placeholder="Rechercher le fournisseur à absorber…"
                className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] pl-9 pr-3 text-[13px] text-white placeholder:text-white/35 focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
              />
            </div>
            <div className="mt-3 divide-y divide-white/[0.04] overflow-hidden rounded-lg border border-white/[0.06]">
              {mergeCandidates.length === 0 ? (
                <p className="px-3 py-4 text-[13px] text-white/45">
                  Saisis au moins deux caractères pour trouver un doublon.
                </p>
              ) : (
                mergeCandidates.map((candidate) => (
                  <div
                    key={candidate.id}
                    className="flex items-center justify-between gap-3 px-3 py-2.5"
                  >
                    <div>
                      <div className="text-[13px] font-medium text-white/90">
                        {candidate.name}
                      </div>
                      <div className="font-mono-display text-[11px] text-white/40">
                        {candidate.vat_number ?? "sans VAT"} · {candidate.invoice_count} facture
                        {candidate.invoice_count > 1 ? "s" : ""}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => void mergeSupplier(candidate.id)}
                      className="btn-glass"
                      disabled={mergingId === candidate.id}
                    >
                      <GitMerge className="h-4 w-4" />
                      {mergingId === candidate.id ? "Fusion…" : "Absorber"}
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* KPIs */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-4">
          <Kpi
            label="Factures"
            value={String(stats.invoice_count)}
            hint={`dont ${stats.confirmed_count} validée${stats.confirmed_count > 1 ? "s" : ""}`}
          />
          <Kpi
            label="Total TTC"
            value={formatMoney(stats.total_ttc)}
            hint={stats.invoice_count > 0 ? "tous statuts confondus" : undefined}
          />
          <Kpi
            label="Facture moyenne"
            value={stats.avg_ttc > 0 ? formatMoney(stats.avg_ttc) : "—"}
          />
          <Kpi
            label="Dernière facture"
            value={formatDate(stats.last_invoice_date)}
            accent="mono"
            hint={
              stats.first_invoice_date
                ? `première le ${formatDate(stats.first_invoice_date)}`
                : undefined
            }
          />
        </div>
      )}

      {/* Invoices */}
      <div className="glass overflow-hidden" style={{ borderRadius: 18 }}>
        <div className="relative z-10">
          <div className="border-b border-white/[0.06] px-5 py-3.5">
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">
              Factures récentes
            </h3>
          </div>
          {related && related.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.04] text-left text-[10px] font-semibold uppercase tracking-[0.10em] text-white/35">
                  <th className="px-5 py-2.5">Fichier</th>
                  <th className="px-5 py-2.5">Numéro</th>
                  <th className="px-5 py-2.5">Date</th>
                  <th className="px-5 py-2.5">Total TTC</th>
                  <th className="px-5 py-2.5">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {related.slice(0, 20).map((inv) => (
                  <tr
                    key={inv.id}
                    className="cursor-pointer transition hover:bg-white/[0.03]"
                    onClick={() => {
                      window.location.href = `/invoices/${inv.id}`;
                    }}
                  >
                    <td className="px-5 py-2.5 text-white/90">{inv.source_file_name}</td>
                    <td className="px-5 py-2.5 font-mono-display text-[12px] text-white/60">
                      {inv.invoice_number ?? "—"}
                    </td>
                    <td className="px-5 py-2.5 text-white/60">
                      {formatDate(inv.issue_date)}
                    </td>
                    <td className="px-5 py-2.5 font-mono-display text-white/80">
                      {inv.total_ttc !== null
                        ? new Intl.NumberFormat("fr-FR", {
                            style: "currency",
                            currency: inv.currency,
                          }).format(inv.total_ttc)
                        : "—"}
                    </td>
                    <td className="px-5 py-2.5">
                      <StatusBadge status={inv.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="py-10 text-center text-[13px] text-white/45">
              Aucune facture pour ce fournisseur.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
