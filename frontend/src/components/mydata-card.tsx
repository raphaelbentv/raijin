"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api";
import type {
  MyDataConnector,
  MyDataConnectorInput,
  MyDataConnectorKind,
} from "@/lib/types";
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

const KIND_LABELS: Record<MyDataConnectorKind, string> = {
  epsilon_digital: "Epsilon Digital (connecteur certifié)",
  softone_mydata: "SoftOne myDATA (connecteur certifié)",
  aade_direct: "AADE direct (intégration native)",
};

const CREDENTIAL_FIELDS: Record<MyDataConnectorKind, string[]> = {
  epsilon_digital: ["api_key"],
  softone_mydata: ["client_id", "client_secret", "subscription_id"],
  aade_direct: ["user_id", "subscription_key"],
};

export function MyDataCard() {
  const [connector, setConnector] = useState<MyDataConnector | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [kind, setKind] = useState<MyDataConnectorKind>("epsilon_digital");
  const [baseUrl, setBaseUrl] = useState("");
  const [issuerVat, setIssuerVat] = useState("");
  const [autoSubmit, setAutoSubmit] = useState(false);
  const [credentials, setCredentials] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<MyDataConnector | null>("/integrations/mydata");
      setConnector(data);
      if (data) {
        setKind(data.kind);
        setBaseUrl(data.base_url);
        setIssuerVat(data.issuer_vat_number ?? "");
        setAutoSubmit(data.auto_submit);
      }
    } catch {
      toast.error("Impossible de charger la config myDATA");
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
      const body: MyDataConnectorInput = {
        kind,
        base_url: baseUrl,
        credentials,
        issuer_vat_number: issuerVat || null,
        auto_submit: autoSubmit,
        is_active: true,
      };
      const updated = await apiFetch<MyDataConnector>("/integrations/mydata", {
        method: "PUT",
        json: body,
      });
      setConnector(updated);
      setEditing(false);
      setCredentials({});
      toast.success("Connecteur myDATA enregistré");
    } catch {
      toast.error("Enregistrement impossible");
    } finally {
      setSaving(false);
    }
  }

  async function disable() {
    if (!confirm("Désactiver le connecteur myDATA ?")) return;
    try {
      await apiFetch("/integrations/mydata", { method: "DELETE" });
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
        <CardTitle className="text-lg">myDATA (AADE)</CardTitle>
        <CardDescription>
          Soumission automatique des factures validées vers AADE via un connecteur certifié ou l&apos;API directe.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}

        {!loading && connector && !editing && (
          <div className="space-y-2 text-sm">
            <p>
              <span className="font-medium">Connecteur :</span> {KIND_LABELS[connector.kind]}
            </p>
            <p className="text-muted-foreground">Base URL : {connector.base_url}</p>
            {connector.issuer_vat_number && (
              <p className="text-muted-foreground">
                VAT émetteur : {connector.issuer_vat_number}
              </p>
            )}
            <p>
              <span className="font-medium">Auto-submit :</span>{" "}
              {connector.auto_submit ? "activé" : "désactivé"} ·{" "}
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
              <Label>Type de connecteur</Label>
              <select
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value as MyDataConnectorKind);
                  setCredentials({});
                }}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              >
                {(Object.keys(KIND_LABELS) as MyDataConnectorKind[]).map((k) => (
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
                placeholder="https://api.mon-connecteur.gr"
              />
            </div>

            <div className="space-y-1">
              <Label>TVA émetteur (sans préfixe EL)</Label>
              <Input
                value={issuerVat}
                onChange={(e) => setIssuerVat(e.target.value.toUpperCase())}
                placeholder="123456789"
              />
            </div>

            {CREDENTIAL_FIELDS[kind].map((field) => (
              <div className="space-y-1" key={field}>
                <Label>{field}</Label>
                {field.includes("secret") || field.includes("key") ? (
                  <Textarea
                    rows={2}
                    value={credentials[field] ?? ""}
                    onChange={(e) =>
                      setCredentials({ ...credentials, [field]: e.target.value })
                    }
                    placeholder="(valeur secrète)"
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

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="mydata-auto"
                checked={autoSubmit}
                onChange={(e) => setAutoSubmit(e.target.checked)}
              />
              <Label htmlFor="mydata-auto">
                Soumettre automatiquement chaque facture validée
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
