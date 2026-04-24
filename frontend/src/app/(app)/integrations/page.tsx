"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { apiFetch, ApiError } from "@/lib/api";
import type { AuthorizeResponse, CloudDriveSource, EmailSource } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { MyDataCard } from "@/components/mydata-card";
import { ErpCard } from "@/components/erp-card";

function formatRelative(iso: string | null): string {
  if (!iso) return "jamais";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  if (diff < 60_000) return "à l'instant";
  if (diff < 3_600_000) return `il y a ${Math.round(diff / 60_000)} min`;
  if (diff < 86_400_000) return `il y a ${Math.round(diff / 3_600_000)} h`;
  return d.toLocaleDateString("fr-FR");
}

export default function IntegrationsPage() {
  const [emailSources, setEmailSources] = useState<EmailSource[]>([]);
  const [driveSources, setDriveSources] = useState<CloudDriveSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectingOutlook, setConnectingOutlook] = useState(false);
  const [connectingGmail, setConnectingGmail] = useState(false);
  const [connectingDrive, setConnectingDrive] = useState(false);
  const [driveFolderId, setDriveFolderId] = useState("");
  const searchParams = useSearchParams();

  const load = useCallback(async () => {
    try {
      const [emails, drives] = await Promise.all([
        apiFetch<EmailSource[]>("/integrations/email-sources"),
        apiFetch<CloudDriveSource[]>("/integrations/gdrive-sources"),
      ]);
      setEmailSources(emails);
      setDriveSources(drives);
    } catch {
      toast.error("Impossible de charger les intégrations");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const connected = searchParams.get("connected");
    const err = searchParams.get("error");
    if (connected === "outlook") toast.success("Compte Outlook connecté");
    else if (connected === "gmail") toast.success("Compte Gmail connecté");
    else if (connected === "gdrive") toast.success("Google Drive connecté");
    else if (err) toast.error(`Connexion échouée : ${err}`);
  }, [searchParams]);

  async function connectProvider(
    path: string,
    setLoading: (v: boolean) => void,
    label: string,
  ) {
    setLoading(true);
    try {
      const res = await apiFetch<AuthorizeResponse>(path, { method: "POST" });
      window.location.href = res.authorize_url;
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        toast.error(`OAuth ${label} non configuré — contacte l'admin`);
      } else {
        toast.error("Impossible de lancer la connexion");
      }
      setLoading(false);
    }
  }

  async function connectDrive() {
    if (!driveFolderId.trim()) {
      toast.error("Indique l'ID du dossier Google Drive");
      return;
    }
    setConnectingDrive(true);
    try {
      const url = `/integrations/gdrive/authorize?folder_id=${encodeURIComponent(driveFolderId.trim())}`;
      const res = await apiFetch<AuthorizeResponse>(url, { method: "POST" });
      window.location.href = res.authorize_url;
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        toast.error("OAuth Google non configuré");
      } else {
        toast.error("Impossible de lancer la connexion");
      }
      setConnectingDrive(false);
    }
  }

  async function syncEmailNow(source: EmailSource) {
    try {
      await apiFetch(`/integrations/email-sources/${source.id}/sync`, { method: "POST" });
      toast.success("Sync lancée");
    } catch {
      toast.error("Sync impossible");
    }
  }

  async function syncDriveNow(source: CloudDriveSource) {
    try {
      await apiFetch(`/integrations/gdrive-sources/${source.id}/sync`, { method: "POST" });
      toast.success("Sync Drive lancée");
    } catch {
      toast.error("Sync impossible");
    }
  }

  async function disconnectEmail(source: EmailSource) {
    if (!confirm(`Déconnecter ${source.account_email} ?`)) return;
    try {
      await apiFetch(`/integrations/email-sources/${source.id}`, { method: "DELETE" });
      toast.success("Source déconnectée");
      await load();
    } catch {
      toast.error("Déconnexion impossible");
    }
  }

  async function disconnectDrive(source: CloudDriveSource) {
    if (!confirm(`Déconnecter le dossier ${source.folder_id} ?`)) return;
    try {
      await apiFetch(`/integrations/gdrive-sources/${source.id}`, { method: "DELETE" });
      toast.success("Source déconnectée");
      await load();
    } catch {
      toast.error("Déconnexion impossible");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Intégrations</h1>
        <p className="text-sm text-muted-foreground">
          Connecte tes boîtes mails et cloud drives pour ingérer automatiquement les factures.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Microsoft Outlook</CardTitle>
            <CardDescription>PDF/JPG/PNG attachés à l&apos;Inbox, toutes les 15 min.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={() => connectProvider("/integrations/outlook/authorize", setConnectingOutlook, "Microsoft")}
              disabled={connectingOutlook}
            >
              {connectingOutlook ? "Redirection…" : "Connecter Outlook"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Gmail</CardTitle>
            <CardDescription>Pièces jointes des mails reçus, toutes les 15 min.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={() => connectProvider("/integrations/gmail/authorize", setConnectingGmail, "Google")}
              disabled={connectingGmail}
            >
              {connectingGmail ? "Redirection…" : "Connecter Gmail"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Google Drive</CardTitle>
            <CardDescription>
              Surveille un dossier partagé et ingère les nouveaux PDF/JPG/PNG.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Label>ID du dossier</Label>
            <Input
              value={driveFolderId}
              onChange={(e) => setDriveFolderId(e.target.value)}
              placeholder="1A2B3C… (URL du dossier)"
            />
            <Button onClick={connectDrive} disabled={connectingDrive}>
              {connectingDrive ? "Redirection…" : "Connecter Drive"}
            </Button>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <MyDataCard />
        <ErpCard />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Sources email ({emailSources.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
          {!loading && emailSources.length === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">
              Aucune boîte mail connectée.
            </p>
          )}
          {emailSources.length > 0 && (
            <ul className="divide-y">
              {emailSources.map((source) => (
                <li key={source.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div>
                    <p className="font-medium">{source.account_email}</p>
                    <p className="text-xs text-muted-foreground">
                      {source.provider.toUpperCase()} · dossier {source.folder} ·{" "}
                      {source.is_active ? (
                        <span className="text-emerald-700">active</span>
                      ) : (
                        <span className="text-rose-700">inactive</span>
                      )}{" "}
                      · dernier sync : {formatRelative(source.last_sync_at)}
                    </p>
                    {source.last_error && (
                      <p className="mt-1 text-xs text-destructive">Erreur : {source.last_error}</p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => syncEmailNow(source)} disabled={!source.is_active}>
                      Sync
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => disconnectEmail(source)}>
                      Déconnecter
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Sources Google Drive ({driveSources.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
          {!loading && driveSources.length === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">Aucun dossier connecté.</p>
          )}
          {driveSources.length > 0 && (
            <ul className="divide-y">
              {driveSources.map((source) => (
                <li key={source.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div>
                    <p className="font-medium">{source.folder_name ?? source.folder_id}</p>
                    <p className="text-xs text-muted-foreground">
                      {source.provider.toUpperCase()} · {source.account_email ?? "—"} ·{" "}
                      {source.is_active ? (
                        <span className="text-emerald-700">active</span>
                      ) : (
                        <span className="text-rose-700">inactive</span>
                      )}{" "}
                      · dernier sync : {formatRelative(source.last_sync_at)}
                    </p>
                    {source.last_error && (
                      <p className="mt-1 text-xs text-destructive">Erreur : {source.last_error}</p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => syncDriveNow(source)} disabled={!source.is_active}>
                      Sync
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => disconnectDrive(source)}>
                      Déconnecter
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
