"use client";

import { useEffect, useMemo, useState } from "react";
import { Upload } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:6200";

interface VatReport {
  year: number;
  quarter: number;
  invoice_count: number;
  total_ht: string;
  total_vat: string;
  total_ttc: string;
}

interface ProfitLossReport {
  year: number;
  months: { month: number; expense_ht: string; invoice_count: number }[];
}

interface AgingReport {
  as_of: string;
  buckets: Record<string, string>;
}

function eur(value: string): string {
  const n = Number(value);
  return Number.isFinite(n)
    ? new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(n)
    : value;
}

export default function ReportsPage() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [quarter, setQuarter] = useState(1);
  const [vat, setVat] = useState<VatReport | null>(null);
  const [pl, setPl] = useState<ProfitLossReport | null>(null);
  const [aging, setAging] = useState<AgingReport | null>(null);
  const [reconciliation, setReconciliation] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<VatReport>(`/reports/vat?year=${year}&quarter=${quarter}`).then(setVat).catch(() => {});
    apiFetch<ProfitLossReport>(`/reports/profit-loss?year=${year}`).then(setPl).catch(() => {});
    apiFetch<AgingReport>("/reports/aging").then(setAging).catch(() => {});
  }, [year, quarter]);

  const yearOptions = useMemo(() => [currentYear, currentYear - 1, currentYear - 2], [currentYear]);

  async function uploadBank(file: File | null) {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    const token = getAccessToken();
    const res = await fetch(`${API_URL}/reports/reconciliation/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form,
    });
    if (!res.ok) return;
    const data = (await res.json()) as { imported: number; matched: number };
    setReconciliation(`${data.imported} ligne(s), ${data.matched} rapprochement(s)`);
    setAging(await apiFetch<AgingReport>("/reports/aging"));
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-serif-italic text-[30px] leading-none text-white/95">Rapports</h1>
          <p className="mt-1 text-[13px] text-white/60">TVA, P&L, aging et rapprochement bancaire.</p>
        </div>
        <div className="glass flex items-center gap-2 p-2" style={{ borderRadius: 14 }}>
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="h-9 rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white"
          >
            {yearOptions.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
          <select
            value={quarter}
            onChange={(e) => setQuarter(Number(e.target.value))}
            className="h-9 rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white"
          >
            {[1, 2, 3, 4].map((value) => (
              <option key={value} value={value}>T{value}</option>
            ))}
          </select>
        </div>
      </div>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="glass p-5" style={{ borderRadius: 18 }}>
          <div className="relative z-10">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">TVA</p>
            <p className="mt-4 font-mono text-2xl text-white/90">{eur(vat?.total_vat ?? "0")}</p>
            <p className="mt-1 text-[12px] text-white/45">{vat?.invoice_count ?? 0} facture(s)</p>
          </div>
        </div>
        <div className="glass p-5" style={{ borderRadius: 18 }}>
          <div className="relative z-10">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">Dépenses HT</p>
            <p className="mt-4 font-mono text-2xl text-white/90">{eur(vat?.total_ht ?? "0")}</p>
            <p className="mt-1 text-[12px] text-white/45">Trimestre {quarter}</p>
          </div>
        </div>
        <div className="glass p-5" style={{ borderRadius: 18 }}>
          <div className="relative z-10">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">À payer</p>
            <p className="mt-4 font-mono text-2xl text-white/90">
              {eur(Object.values(aging?.buckets ?? {}).reduce((sum, value) => sum + Number(value), 0).toString())}
            </p>
            <p className="mt-1 text-[12px] text-white/45">au {aging?.as_of ?? "-"}</p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="glass p-5" style={{ borderRadius: 18 }}>
          <div className="relative z-10 space-y-3">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">P&L mensuel</h2>
            {(pl?.months ?? []).map((row) => (
              <div key={row.month} className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-sm">
                <span className="text-white/70">{String(row.month).padStart(2, "0")}/{pl?.year}</span>
                <span className="font-mono text-white/85">{eur(row.expense_ht)}</span>
              </div>
            ))}
            {pl?.months.length === 0 && <p className="text-sm text-white/40">Aucune donnée confirmée.</p>}
          </div>
        </div>
        <div className="glass p-5" style={{ borderRadius: 18 }}>
          <div className="relative z-10 space-y-3">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">Aging</h2>
            {Object.entries(aging?.buckets ?? {}).map(([bucket, value]) => (
              <div key={bucket} className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-sm">
                <span className="text-white/70">{bucket} jours</span>
                <span className="font-mono text-white/85">{eur(value)}</span>
              </div>
            ))}
            <label className="btn-primary-violet w-fit cursor-pointer">
              <Upload className="h-3.5 w-3.5" />
              Import banque CSV
              <input type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => uploadBank(e.target.files?.[0] ?? null)} />
            </label>
            {reconciliation && <p className="text-[12px] text-emerald-200">{reconciliation}</p>}
          </div>
        </div>
      </section>
    </div>
  );
}
