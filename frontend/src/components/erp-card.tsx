"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api";
import type { ErpConnector, ErpConnectorInput, ErpConnectorKind } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const KIND_LABELS: Record<ErpConnectorKind, string> = {
  softone: "SoftOne (Genesis / Atlantis / Cloud)",
  epsilon_net: "Epsilon Net (Pylon / Hypersoft)",
};

const CREDENTIAL_FIELDS: Record<ErpConnectorKind, string[]> = {
  softone: ["username", "password", "app_id"],
  epsilon_net: ["api_key", "subscription_id"],
};

export function ErpCard() {
  const [connector, setConnector] = useState<ErpConnector | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [kind, setKind] = useState<ErpConnectorKind>("softone");
  const [baseUrl, setBaseUrl] = useState("");
  const [autoExport, setAutoExport] = useState(false);
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [company, setCompany] = useState("1");
  const [branch, setBranch] = useState("1");

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<ErpConnector | null>("/integrations/erp");
      setConnector(data);
      if (data) {
        setKind(data.kind);
        setBaseUrl(data.base_url);
        setAutoExport(data.auto_export);
        const cfg = data.config as Record<string, unknown> | null;
        if (cfg) {
          if (cfg.company) setCompany(String(cfg.company));
          if (cfg.branch) setBranch(String(cfg.branch));
        }
      }
    } catch {
      toast.error("Impossible de charger la config ERP");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    const missing = CREDENTIAL_FIELDS[kind].filter((f) => !credentials[f]);
    if (missing.length > 0) {
      toast.error(`Champs manquants : ${missing.join(", ")}`);
      return;
    }

    setSaving(true);
    try {
      const config: Record<string, unknown> =
        kind === "softone"
          ? { company: Number(company) || 1, branch: Number(branch) || 1 }
          : company
            ? { company_id: company }
            : {};
      const body: ErpConnectorInput = {
        kind,
        base_url: baseUrl,
        credentials,
        config,
        auto_export: autoExport,
        is_active: true,
      };
      const updated = await apiFetch<ErpConnector>("/integrations/erp", {
        method: "PUT",
        json: body,
      });
      setConnector(updated);
      setEditing(false);
      setCredentials({});
      toast.success("Connecteur ERP enregistré");
    } catch {
      toast.error("Enregistrement impossible");
    } finally {
      setSaving(false);
    }
  }

  async function disable() {
    if (!confirm("Désactiver la connexion ERP ?")) return;
    try {
      await apiFetch("/integrations/erp", { method: "DELETE" });
      toast.success("Connecteur désactivé");
      await load();
    } catch {
      toast.error("Désactivation impossible");
    }
  }

  const showForm = editing || !connector;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">ERP comptable</CardTitle>
        <CardDescription>
          Export automatique des factures validées vers SoftOne. Epsilon Net à venir.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}

        {!loading && connector && !editing && (
          <div className="space-y-2 text-sm">
            <p>
              <span className="font-medium">ERP :</span> {KIND_LABELS[connector.kind]}
            </p>
            <p className="text-muted-foreground">Base URL : {connector.base_url}</p>
            <p>
              <span className="font-medium">Auto-export :</span>{" "}
              {connector.auto_export ? "activé" : "désactivé"} ·{" "}
              <span className={connector.is_active ? "text-emerald-700" : "text-rose-700"}>
                {connector.is_active ? "actif" : "inactif"}
              </span>
            </p>
            <div className="flex gap-2 pt-2">
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                Modifier
              </Button>
              {connector.is_active && (
                <Button size="sm" variant="destructive" onClick={disable}>
                  Désactiver
                </Button>
              )}
            </div>
          </div>
        )}

        {!loading && showForm && (
          <div className="space-y-3">
            <div className="space-y-1">
              <Label>ERP</Label>
              <select
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value as ErpConnectorKind);
                  setCredentials({});
                }}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              >
                {(Object.keys(KIND_LABELS) as ErpConnectorKind[]).map((k) => (
                  <option key={k} value={k}>
                    {KIND_LABELS[k]}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <Label>Base URL</Label>
              <Input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://s1.mon-client.gr"
              />
            </div>

            {CREDENTIAL_FIELDS[kind].map((field) => (
              <div className="space-y-1" key={field}>
                <Label>{field}</Label>
                {field.includes("password") ? (
                  <Input
                    type="password"
                    value={credentials[field] ?? ""}
                    onChange={(e) =>
                      setCredentials({ ...credentials, [field]: e.target.value })
                    }
                  />
                ) : (
                  <Input
                    value={credentials[field] ?? ""}
                    onChange={(e) =>
                      setCredentials({ ...credentials, [field]: e.target.value })
                    }
                  />
                )}
              </div>
            ))}

            {kind === "softone" && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Company</Label>
                  <Input value={company} onChange={(e) => setCompany(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Branch</Label>
                  <Input value={branch} onChange={(e) => setBranch(e.target.value)} />
                </div>
              </div>
            )}

            {kind === "epsilon_net" && (
              <div className="space-y-1">
                <Label>Company ID (optionnel)</Label>
                <Input
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="laisser vide si mono-société"
                />
              </div>
            )}

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="erp-auto"
                checked={autoExport}
                onChange={(e) => setAutoExport(e.target.checked)}
              />
              <Label htmlFor="erp-auto">
                Exporter automatiquement chaque facture validée
              </Label>
            </div>

            <div className="flex gap-2 pt-2">
              <Button onClick={save} disabled={saving || !baseUrl}>
                {saving ? "Enregistrement…" : "Enregistrer"}
              </Button>
              {connector && (
                <Button variant="ghost" onClick={() => setEditing(false)}>
                  Annuler
                </Button>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
