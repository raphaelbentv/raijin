"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Download, Upload } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { InvoiceStats, User } from "@/lib/types";
import {
  ActivityFeed,
  ConfidenceGauge,
  Greeting,
  HeroPending,
  IntegrationsHealth,
  MonthCard,
  Pipeline,
  Shortcuts,
  TodoList,
  TopSuppliers,
} from "@/components/dashboard/widgets";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:6200";

interface MetricsResponse {
  invoices: { counters: Record<string, number>; total: number };
  ocr: { success_rate: number | null; mean_confidence: number | null };
  review: { corrections_total: number };
}

export default function DashboardPage() {
  const [stats, setStats] = useState<InvoiceStats | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    apiFetch<InvoiceStats>("/invoices/stats").then(setStats).catch(() => {});
    apiFetch<MetricsResponse>("/metrics").then(setMetrics).catch(() => {});
    apiFetch<User>("/auth/me").then(setUser).catch(() => {});
  }, []);

  const pending = stats?.counters.ready_for_review ?? null;
  const total = stats?.counters.total ?? null;
  const confidence = metrics?.ocr.mean_confidence ?? null;

  const month = useMemo(() => {
    const docs = (stats?.counters.confirmed ?? 0) + (stats?.counters.ready_for_review ?? 0);
    const avgTtc = 480;
    const ttc = docs * avgTtc;
    const ht = Math.round(ttc / 1.24);
    const vat = ttc - ht;
    const fmt = (n: number) =>
      `€${n.toLocaleString("fr-FR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    return { ttc: fmt(ttc), ht: fmt(ht), vat: fmt(vat), docs };
  }, [stats]);

  async function exportExcel() {
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
    }
  }

  const displayName = user?.full_name ?? user?.email?.split("@")[0] ?? "";

  return (
    <div className="space-y-6">
      {/* Topbar */}
      <div className="flex items-start justify-between">
        <Greeting name={displayName} total={total} />
        <div className="flex items-center gap-2.5">
          <button onClick={exportExcel} className="btn-glass">
            <Download className="h-3.5 w-3.5" />
            Exporter Excel
          </button>
          <Link href="/upload" className="btn-primary-violet">
            <Upload className="h-3.5 w-3.5" />
            Importer
          </Link>
        </div>
      </div>

      {/* Widget grid */}
      <div className="grid grid-cols-4 gap-4">
        <HeroPending pending={pending} total={total} />
        <ConfidenceGauge confidence={confidence} />
        <MonthCard
          totalTtc={month.ttc}
          totalHt={month.ht}
          totalVat={month.vat}
          docsCount={month.docs}
          delta={18}
        />

        <Pipeline stats={stats} />

        <ActivityFeed />
        <TopSuppliers />

        <IntegrationsHealth />
        <TodoList stats={stats} />
        <Shortcuts />
      </div>
    </div>
  );
}
