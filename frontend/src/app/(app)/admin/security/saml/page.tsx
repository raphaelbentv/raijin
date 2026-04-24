"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ApiError, apiFetch } from "@/lib/api";
import type { User } from "@/lib/types";
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

interface SamlConfig {
  id?: string;
  entity_id: string | null;
  sso_url: string | null;
  certificate: string | null;
  is_enabled: boolean;
}

const EMPTY: SamlConfig = {
  entity_id: "",
  sso_url: "",
  certificate: "",
  is_enabled: false,
};

export default function AdminSamlPage() {
  const [config, setConfig] = useState<SamlConfig>(EMPTY);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:6200";

  useEffect(() => {
    Promise.all([
      apiFetch<SamlConfig | null>("/security/saml").catch(() => null),
      apiFetch<User>("/auth/me").catch(() => null),
    ]).then(([cfg, me]) => {
      if (cfg) setConfig({ ...EMPTY, ...cfg });
      if (me) setUser(me);
      setLoading(false);
    });
  }, []);

  async function save() {
    setSaving(true);
    try {
      const updated = await apiFetch<SamlConfig>("/security/saml", {
        method: "PUT",
        json: {
          entity_id: config.entity_id || null,
          sso_url: config.sso_url || null,
          certificate: config.certificate || null,
          is_enabled: config.is_enabled,
        },
      });
      setConfig({ ...EMPTY, ...updated });
      toast.success("Configuration SAML enregistrée");
    } catch (err) {
      const msg = err instanceof ApiError ? `Erreur ${err.status}` : "Erreur réseau";
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  const slug = user?.tenant?.slug ?? "tenant-slug";
  const acsUrl = `${apiUrl}/auth/saml/acs/${slug}`;
  const entityId = `${apiUrl}/auth/saml/metadata/${slug}`;
  const metadataUrl = `${apiUrl}/auth/saml/metadata/${slug}`;

  if (loading) {
    return <div className="text-sm text-white/50">Chargement…</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">SSO SAML</h1>
        <p className="text-sm text-muted-foreground">
          Configure un Identity Provider (Okta, Google Workspace, Azure AD, etc.) pour permettre à
          ton équipe de se connecter avec leurs identifiants d&apos;entreprise.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Paramètres Service Provider (Raijin)</CardTitle>
          <CardDescription>
            À communiquer à l&apos;équipe qui configure l&apos;IdP côté Okta / Workspace / Azure AD.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-[13px]">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-white/45">Entity ID</div>
            <code className="block break-all rounded-md bg-white/[0.04] px-2 py-1 font-mono text-violet-200">
              {entityId}
            </code>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-white/45">ACS URL (callback)</div>
            <code className="block break-all rounded-md bg-white/[0.04] px-2 py-1 font-mono text-violet-200">
              {acsUrl}
            </code>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-white/45">Métadonnées SP XML</div>
            <a
              href={metadataUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-violet-300 underline-offset-4 hover:underline"
            >
              {metadataUrl}
            </a>
          </div>
          <p className="text-[11px] text-white/45">
            NameID format : <code className="text-violet-200">emailAddress</code>. Attributs attendus :
            <code className="ml-1 text-violet-200">email</code> ou <code className="text-violet-200">emailAddress</code>,
            optionnellement <code className="text-violet-200">displayName</code> ou{" "}
            <code className="text-violet-200">givenName</code> + <code className="text-violet-200">surname</code>.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Identity Provider</CardTitle>
          <CardDescription>
            Valeurs copiées depuis la configuration de ton IdP (Okta, Google Workspace, etc.).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="idp-entity">IdP Entity ID</Label>
            <Input
              id="idp-entity"
              placeholder="ex. http://www.okta.com/exk..."
              value={config.entity_id ?? ""}
              onChange={(e) => setConfig((c) => ({ ...c, entity_id: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="idp-sso">SSO URL (Single Sign-On)</Label>
            <Input
              id="idp-sso"
              placeholder="ex. https://acme.okta.com/app/…/sso/saml"
              value={config.sso_url ?? ""}
              onChange={(e) => setConfig((c) => ({ ...c, sso_url: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="idp-cert">Certificat X.509 (public key IdP)</Label>
            <Textarea
              id="idp-cert"
              placeholder={"-----BEGIN CERTIFICATE-----\nMIIC...\n-----END CERTIFICATE-----"}
              value={config.certificate ?? ""}
              onChange={(e) => setConfig((c) => ({ ...c, certificate: e.target.value }))}
              className="min-h-[140px] font-mono text-[12px]"
            />
          </div>
          <label className="flex items-center gap-2 text-[13px] text-white/80">
            <input
              type="checkbox"
              checked={config.is_enabled}
              onChange={(e) => setConfig((c) => ({ ...c, is_enabled: e.target.checked }))}
            />
            Activer la connexion SSO SAML pour ce tenant
          </label>
          <Button onClick={save} disabled={saving}>
            {saving ? "Enregistrement…" : "Enregistrer la configuration"}
          </Button>
        </CardContent>
      </Card>

      {config.is_enabled && user?.tenant?.slug && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Tester la connexion</CardTitle>
            <CardDescription>
              Les utilisateurs pourront lancer la connexion SSO depuis /login en saisissant le slug
              <code className="ml-1 text-violet-200">{user.tenant.slug}</code>. Lien direct :
            </CardDescription>
          </CardHeader>
          <CardContent>
            <a
              href={`${apiUrl}/auth/saml/login/${user.tenant.slug}`}
              className="btn-glass inline-flex"
            >
              Tester le flow SSO
            </a>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
