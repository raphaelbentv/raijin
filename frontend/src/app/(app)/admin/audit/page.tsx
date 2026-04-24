"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api";
import type { AuditLog, AuditLogListResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AuditPage() {
  const [data, setData] = useState<AuditLogListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = new URLSearchParams({ page: String(page), page_size: "50" });
      if (action) qs.set("action", action);
      if (entity) qs.set("entity_type", entity);
      const res = await apiFetch<AuditLogListResponse>(`/audit?${qs.toString()}`);
      setData(res);
    } catch {
      toast.error("Impossible de charger le journal d'audit");
    } finally {
      setLoading(false);
    }
  }, [page, action, entity]);

  useEffect(() => {
    void load();
  }, [load]);

  const pageCount = useMemo(() => {
    if (!data) return 1;
    return Math.max(1, Math.ceil(data.total / data.page_size));
  }, [data]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Journal d&apos;audit</h1>
        <p className="text-sm text-muted-foreground">
          Toutes les actions sensibles effectuées dans l&apos;organisation.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Filtres</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1">
            <Label>Action</Label>
            <Input
              value={action}
              onChange={(e) => setAction(e.target.value)}
              placeholder="invoice.confirm, user.create…"
            />
          </div>
          <div className="space-y-1">
            <Label>Entity</Label>
            <Input
              value={entity}
              onChange={(e) => setEntity(e.target.value)}
              placeholder="invoice, user…"
            />
          </div>
          <div className="flex items-end">
            <Button
              variant="outline"
              onClick={() => {
                setPage(1);
                void load();
              }}
            >
              Appliquer
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            Événements ({data?.total ?? 0})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Chargement…</p>
          ) : data && data.items.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Aucun événement.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="py-2">Date</th>
                    <th className="py-2">Action</th>
                    <th className="py-2">Entity</th>
                    <th className="py-2">Entity ID</th>
                    <th className="py-2">IP</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data?.items.map((log: AuditLog) => (
                    <tr key={log.id}>
                      <td className="py-2 text-xs">{formatDate(log.created_at)}</td>
                      <td className="py-2 font-medium">{log.action}</td>
                      <td className="py-2 text-muted-foreground">{log.entity_type}</td>
                      <td className="py-2 font-mono text-xs text-muted-foreground">
                        {log.entity_id ? log.entity_id.slice(0, 8) : "—"}
                      </td>
                      <td className="py-2 text-xs text-muted-foreground">
                        {log.ip_address ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data && data.total > data.page_size && (
            <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
              <span>
                Page {data.page} / {pageCount} · {data.total} événement(s)
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  ← Précédent
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= pageCount}
                  onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
                >
                  Suivant →
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
