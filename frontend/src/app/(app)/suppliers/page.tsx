"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import { Plus, Search, X } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Supplier {
  id: string;
  name: string;
  vat_number: string | null;
  country_code: string | null;
  city: string | null;
  email: string | null;
  phone: string | null;
  created_at: string;
  invoice_count: number;
  total_ttc: number | null;
}

interface SupplierListResponse {
  items: Supplier[];
  total: number;
  page: number;
  page_size: number;
}

type SupplierFormState = {
  name: string;
  vat_number: string;
  country_code: string;
  city: string;
  email: string;
  phone: string;
};

const EMPTY_FORM: SupplierFormState = {
  name: "",
  vat_number: "",
  country_code: "FR",
  city: "",
  email: "",
  phone: "",
};

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

function formatMoney(amount: number | null): string {
  if (amount === null || amount === 0) return "—";
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function SuppliersPage() {
  const [data, setData] = useState<SupplierListResponse | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<SupplierFormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = () => {
    const qs = new URLSearchParams({ page: String(page), page_size: "50" });
    if (search) qs.set("search", search);
    return apiFetch<SupplierListResponse>(`/suppliers?${qs.toString()}`)
      .then((response) => {
        setData(response);
        setError(null);
      })
      .catch(() => setError("Impossible de charger les fournisseurs."));
  };

  useEffect(() => {
    const t = setTimeout(() => {
      void load();
    }, search ? 250 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, page]);

  async function createSupplier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await apiFetch<Supplier>("/suppliers", {
        method: "POST",
        json: {
          name: form.name,
          vat_number: form.vat_number,
          country_code: form.country_code,
          city: form.city,
          email: form.email,
          phone: form.phone,
        },
      });
      setForm(EMPTY_FORM);
      setCreateOpen(false);
      await load();
      window.location.href = `/suppliers/${created.id}`;
    } catch {
      setError("Impossible de créer ce fournisseur. Vérifie le VAT ou réessaie.");
    } finally {
      setSaving(false);
    }
  }

  const maxCount = useMemo(
    () => Math.max(1, ...(data?.items.map((s) => s.invoice_count) ?? [0])),
    [data],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-serif-italic text-[30px] leading-none text-white/95">
            Fournisseurs
          </h1>
          <p className="mt-1 text-[13px] text-white/60">
            {data
              ? `${data.total} fournisseur${data.total > 1 ? "s" : ""} actifs dans Venio`
              : "Chargement…"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-white/35" />
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Rechercher un fournisseur ou un VAT…"
              className="h-10 w-[320px] rounded-lg border border-white/10 bg-white/[0.04] pl-8 pr-3 text-[13px] text-white placeholder:text-white/35 focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          <button
            type="button"
            onClick={() => setCreateOpen((open) => !open)}
            className="btn-primary-violet"
          >
            {createOpen ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            Nouveau
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-rose-400">{error}</p>}

      {createOpen && (
        <form
          onSubmit={createSupplier}
          className="glass grid gap-3 p-5 md:grid-cols-6"
          style={{ borderRadius: 18 }}
        >
          <div className="relative z-10 md:col-span-2">
            <label
              htmlFor="supplier-create-name"
              className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.10em] text-white/35"
            >
              Nom
            </label>
            <input
              id="supplier-create-name"
              required
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          <div className="relative z-10">
            <label
              htmlFor="supplier-create-vat"
              className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.10em] text-white/35"
            >
              VAT
            </label>
            <input
              id="supplier-create-vat"
              value={form.vat_number}
              onChange={(e) => setForm((f) => ({ ...f, vat_number: e.target.value }))}
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 font-mono-display text-[13px] text-white focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          <div className="relative z-10">
            <label
              htmlFor="supplier-create-country"
              className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.10em] text-white/35"
            >
              Pays
            </label>
            <input
              id="supplier-create-country"
              maxLength={2}
              value={form.country_code}
              onChange={(e) =>
                setForm((f) => ({ ...f, country_code: e.target.value.toUpperCase() }))
              }
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 font-mono-display text-[13px] text-white focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          <div className="relative z-10">
            <label
              htmlFor="supplier-create-city"
              className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.10em] text-white/35"
            >
              Ville
            </label>
            <input
              id="supplier-create-city"
              value={form.city}
              onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))}
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          <div className="relative z-10">
            <label
              htmlFor="supplier-create-email"
              className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.10em] text-white/35"
            >
              Email
            </label>
            <input
              id="supplier-create-email"
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          <div className="relative z-10 md:col-span-6 flex justify-end gap-2">
            <input
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              placeholder="Téléphone"
              className="h-10 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white placeholder:text-white/35 focus:border-violet-500/40 focus:outline-none focus:ring-2 focus:ring-violet-500/20 md:max-w-[240px]"
            />
            <button type="submit" className="btn-primary-violet" disabled={saving}>
              <Plus className="h-4 w-4" />
              {saving ? "Création…" : "Créer"}
            </button>
          </div>
        </form>
      )}

      <div className="glass overflow-hidden" style={{ borderRadius: 18 }}>
        <div className="relative z-10">
          {data && data.items.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-14 text-center text-sm text-white/60">
              <p>
                {search
                  ? `Aucun fournisseur ne correspond à "${search}".`
                  : "Aucun fournisseur pour le moment."}
              </p>
              {!search && (
                <Link href="/upload" className="btn-glass">
                  Importer une facture
                </Link>
              )}
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-white/[0.06]">
                <tr className="text-left text-[10px] font-semibold uppercase tracking-[0.10em] text-white/35">
                  <th className="px-5 py-3">Nom</th>
                  <th className="px-5 py-3">VAT</th>
                  <th className="px-5 py-3">Ville</th>
                  <th className="px-5 py-3">Factures</th>
                  <th className="px-5 py-3 text-right">Total TTC</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {data?.items.map((s) => (
                  <tr
                    key={s.id}
                    className="cursor-pointer transition hover:bg-white/[0.03]"
                    onClick={() => {
                      window.location.href = `/suppliers/${s.id}`;
                    }}
                  >
                    <td className="px-5 py-3">
                      <span className="mr-2 text-[14px]">
                        {flagForCountry(s.country_code)}
                      </span>
                      <span className="font-medium text-white/90">{s.name}</span>
                    </td>
                    <td className="px-5 py-3 font-mono-display text-[12px] text-violet-300/80">
                      {s.vat_number ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-white/60">{s.city ?? "—"}</td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2.5">
                        <span className="w-8 font-mono-display text-[12px] text-white/80">
                          {s.invoice_count}
                        </span>
                        <div className="h-[3px] flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${(s.invoice_count / maxCount) * 100}%`,
                              background:
                                "linear-gradient(90deg, #8b5cf6, rgba(99,102,241,0.6))",
                            }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-right font-mono-display text-white/80">
                      {formatMoney(s.total_ttc)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
