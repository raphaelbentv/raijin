"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckSquare, Download, Upload } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { InvoiceListResponse, InvoiceStatus } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:6200";

const STATUS_FILTERS: { value: InvoiceStatus | "all"; label: string }[] = [
  { value: "all", label: "Toutes" },
  { value: "ready_for_review", label: "À valider" },
  { value: "processing", label: "Traitement" },
  { value: "confirmed", label: "Validées" },
  { value: "rejected", label: "Rejetées" },
  { value: "failed", label: "Échecs" },
  { value: "uploaded", label: "Reçues" },
];

function formatMoney(amount: string | null, currency: string): string {
  if (!amount) return "—";
  const n = Number(amount);
  if (Number.isNaN(n)) return amount;
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency }).format(n);
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function InvoicesPage() {
  const [data, setData] = useState<InvoiceListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<InvoiceStatus | "all">("all");
  const [query, setQuery] = useState("");
  const [paid, setPaid] = useState<"all" | "paid" | "unpaid">("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const qs = new URLSearchParams({ page: String(page), page_size: "30" });
    if (filter !== "all") qs.set("status_filter", filter);
    if (query.trim()) qs.set("q", query.trim());
    if (paid !== "all") qs.set("paid", String(paid === "paid"));
    apiFetch<InvoiceListResponse>(`/invoices?${qs.toString()}`)
      .then(setData)
      .catch(() => setError("Impossible de charger les factures."));
  }, [page, filter, query, paid]);

  const pageCount = useMemo(() => {
    if (!data) return 1;
    return Math.max(1, Math.ceil(data.total / data.page_size));
  }, [data]);

  async function exportExcel() {
    setExporting(true);
    try {
      const token = getAccessToken();
      const res = await fetch(`${API_URL}/exports/excel`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      const cd = res.headers.get("Content-Disposition") ?? "";
      const match = /filename="([^"]+)"/.exec(cd);
      link.download = match ? match[1] : "raijin-export.xlsx";
      link.click();
      window.URL.revokeObjectURL(url);
    } catch {
      // silent
    } finally {
      setExporting(false);
    }
  }

  async function bulk(action: "confirm" | "mark_paid" | "reopen") {
    await apiFetch("/invoices/bulk", {
      method: "POST",
      json: { ids: Array.from(selected), action },
    });
    setSelected(new Set());
    const qs = new URLSearchParams({ page: String(page), page_size: "30" });
    if (filter !== "all") qs.set("status_filter", filter);
    if (query.trim()) qs.set("q", query.trim());
    if (paid !== "all") qs.set("paid", String(paid === "paid"));
    setData(await apiFetch<InvoiceListResponse>(`/invoices?${qs.toString()}`));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-serif-italic text-[30px] leading-none text-white/95">
            Factures
          </h1>
          <p className="mt-1 text-[13px] text-white/60">
            {data ? `${data.total} facture(s) — page ${data.page} / ${pageCount}` : "Chargement…"}
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <button onClick={exportExcel} className="btn-glass" disabled={exporting}>
            <Download className="h-3.5 w-3.5" />
            {exporting ? "Export…" : "Exporter Excel"}
          </button>
          <Link href="/upload" className="btn-primary-violet">
            <Upload className="h-3.5 w-3.5" />
            Importer
          </Link>
        </div>
      </div>

      {/* Filtres pills */}
      <div className="flex flex-wrap gap-1.5">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => {
              setFilter(f.value);
              setPage(1);
            }}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              filter === f.value
                ? "text-white"
                : "bg-white/[0.05] text-white/60 hover:bg-white/[0.08]",
            )}
            style={
              filter === f.value
                ? {
                    background:
                      "linear-gradient(90deg, rgba(139,92,246,0.3) 0%, rgba(99,102,241,0.2) 100%)",
                    border: "1px solid rgba(139,92,246,0.4)",
                  }
                : { border: "1px solid rgba(255,255,255,0.06)" }
            }
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="glass flex flex-wrap items-center gap-2 p-3" style={{ borderRadius: 14 }}>
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(1);
          }}
          placeholder="Recherche numéro ou fichier"
          className="h-9 min-w-[240px] rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white placeholder:text-white/35 outline-none"
        />
        <select
          value={paid}
          onChange={(e) => {
            setPaid(e.target.value as typeof paid);
            setPage(1);
          }}
          className="h-9 rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white"
        >
          <option value="all">Tous paiements</option>
          <option value="paid">Payées</option>
          <option value="unpaid">Non payées</option>
        </select>
        {selected.size > 0 && (
          <div className="ml-auto flex items-center gap-2 text-[12px] text-white/60">
            <CheckSquare className="h-4 w-4 text-violet-200" />
            {selected.size} sélectionnée(s)
            <button className="btn-glass" onClick={() => bulk("confirm")}>Valider</button>
            <button className="btn-glass" onClick={() => bulk("mark_paid")}>Marquer payées</button>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-rose-400">{error}</p>}

      <div className="glass overflow-hidden" style={{ borderRadius: 18 }}>
        <div className="relative z-10">
          {data && data.items.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-14 text-center text-sm text-white/60">
              <p>Aucune facture à afficher.</p>
              <Link href="/upload" className="btn-glass">
                <Upload className="h-3.5 w-3.5" />
                Importer une facture
              </Link>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-white/[0.06]">
                <tr className="text-left text-[10px] font-semibold uppercase tracking-[0.10em] text-white/35">
                  <th className="px-5 py-3"></th>
                  <th className="px-5 py-3">Fichier</th>
                  <th className="px-5 py-3">Numéro</th>
                  <th className="px-5 py-3">Date</th>
                  <th className="px-5 py-3">Total TTC</th>
                  <th className="px-5 py-3">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {data?.items.map((inv) => (
                  <tr
                    key={inv.id}
                    className="cursor-pointer transition hover:bg-white/[0.03]"
                    onClick={() => {
                      window.location.href = `/invoices/${inv.id}`;
                    }}
                  >
                    <td className="px-5 py-3" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selected.has(inv.id)}
                        onChange={(e) =>
                          setSelected((current) => {
                            const next = new Set(current);
                            if (e.target.checked) next.add(inv.id);
                            else next.delete(inv.id);
                            return next;
                          })
                        }
                      />
                    </td>
                    <td className="px-5 py-3 text-white/90">{inv.source_file_name}</td>
                    <td className="px-5 py-3 font-mono-display text-[12px] text-white/60">
                      <div className="flex items-center gap-2">
                        <span>{inv.invoice_number ?? "—"}</span>
                        {inv.possible_duplicate_of_id && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-amber-300/25 bg-amber-300/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-amber-200">
                            <AlertTriangle className="h-3 w-3" />
                            Doublon
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3 text-white/60">{formatDate(inv.issue_date)}</td>
                    <td className="px-5 py-3 font-mono-display text-white/80">
                      {formatMoney(inv.total_ttc, inv.currency)}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={inv.status} />
                        {inv.paid_at && (
                          <span className="rounded-full border border-emerald-300/25 bg-emerald-300/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-emerald-200">
                            Payée
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {data && data.total > data.page_size && (
            <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-3 text-[12px] text-white/45">
              <span>
                Page {data.page} / {pageCount} · {data.total} facture(s)
              </span>
              <div className="flex gap-2">
                <button
                  className="btn-glass disabled:opacity-40"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  ← Précédent
                </button>
                <button
                  className="btn-glass disabled:opacity-40"
                  disabled={page >= pageCount}
                  onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
                >
                  Suivant →
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
