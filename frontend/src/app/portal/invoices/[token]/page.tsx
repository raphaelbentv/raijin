"use client";

import { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { InvoiceDetail } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

function money(value: string | null, currency: string): string {
  if (!value) return "-";
  const n = Number(value);
  return Number.isFinite(n)
    ? new Intl.NumberFormat("fr-FR", { style: "currency", currency }).format(n)
    : value;
}

export default function PortalInvoicePage({ params }: { params: { token: string } }) {
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    apiFetch<InvoiceDetail>(`/portal/invoices/${params.token}`, { auth: false })
      .then(setInvoice)
      .catch(() => setMissing(true));
  }, [params.token]);

  if (missing) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#050508] p-6 text-white">
        <div className="glass max-w-md p-6 text-center">
          <p className="text-sm text-white/60">Lien expiré ou facture indisponible.</p>
        </div>
      </main>
    );
  }

  if (!invoice) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#050508] text-sm text-white/50">
        Chargement...
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#050508] p-6 text-white">
      <div className="mx-auto max-w-5xl space-y-5">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/35">
              Portail Raijin
            </p>
            <h1 className="font-serif-italic text-[30px] leading-tight text-white/95">
              {invoice.invoice_number ?? invoice.source_file_name}
            </h1>
          </div>
          <StatusBadge status={invoice.status} />
        </header>

        <section className="glass grid gap-5 p-5 md:grid-cols-3" style={{ borderRadius: 18 }}>
          <div className="relative z-10">
            <p className="text-[11px] uppercase tracking-[0.12em] text-white/35">Fournisseur</p>
            <p className="mt-1 text-sm text-white/85">{invoice.supplier?.name ?? "-"}</p>
          </div>
          <div className="relative z-10">
            <p className="text-[11px] uppercase tracking-[0.12em] text-white/35">Échéance</p>
            <p className="mt-1 text-sm text-white/85">{invoice.due_date ?? "-"}</p>
          </div>
          <div className="relative z-10">
            <p className="text-[11px] uppercase tracking-[0.12em] text-white/35">Total TTC</p>
            <p className="mt-1 font-mono text-lg text-white/90">
              {money(invoice.total_ttc, invoice.currency)}
            </p>
          </div>
        </section>

        <section className="grid gap-5 lg:grid-cols-2">
          <div className="glass p-5" style={{ borderRadius: 18 }}>
            <div className="relative z-10 space-y-3">
              <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">
                Lignes
              </h2>
              {invoice.lines.map((line) => (
                <div
                  key={line.id ?? line.line_number}
                  className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[12px]"
                >
                  <span className="truncate text-white/75">{line.description ?? "-"}</span>
                  <span className="font-mono text-white/60">
                    {money(line.line_total_ttc, invoice.currency)}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="glass p-5" style={{ borderRadius: 18 }}>
            <div className="relative z-10 space-y-3">
              <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">
                Document
              </h2>
              {invoice.file_url ? (
                <a href={invoice.file_url} className="btn-primary-violet" target="_blank">
                  <FileText className="h-3.5 w-3.5" />
                  Ouvrir le PDF
                </a>
              ) : (
                <p className="text-sm text-white/45">Aucun PDF disponible.</p>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
