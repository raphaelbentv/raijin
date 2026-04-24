"use client";

import { useCallback, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { ApiError, apiFetch } from "@/lib/api";
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

interface IpRule {
  id: string;
  cidr: string;
  is_active: boolean;
}

export default function AdminIpRulesPage() {
  const [rules, setRules] = useState<IpRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [cidr, setCidr] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      const list = await apiFetch<IpRule[]>("/security/ip-rules");
      setRules(list);
    } catch (err) {
      const msg = err instanceof ApiError ? `Erreur ${err.status}` : "Erreur réseau";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createRule(e: React.FormEvent) {
    e.preventDefault();
    if (!cidr.trim()) return;
    setCreating(true);
    try {
      const created = await apiFetch<IpRule>("/security/ip-rules", {
        method: "POST",
        json: { cidr: cidr.trim() },
      });
      setRules((prev) => [created, ...prev]);
      setCidr("");
      toast.success("Règle ajoutée");
    } catch (err) {
      const msg = err instanceof ApiError ? `Erreur ${err.status}` : "Erreur réseau";
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  }

  async function deleteRule(id: string) {
    if (!confirm("Supprimer cette règle IP ?")) return;
    try {
      await apiFetch(`/security/ip-rules/${id}`, { method: "DELETE" });
      setRules((prev) => prev.filter((r) => r.id !== id));
      toast.success("Règle supprimée");
    } catch (err) {
      const msg = err instanceof ApiError ? `Erreur ${err.status}` : "Erreur réseau";
      toast.error(msg);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Restrictions IP</h1>
        <p className="text-sm text-muted-foreground">
          Contrôle les plages d&apos;adresses autorisées à se connecter à ton tenant. Si aucune règle n&apos;est
          définie, toutes les IP sont acceptées.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Ajouter une règle CIDR</CardTitle>
          <CardDescription>
            Notation CIDR : <code className="text-violet-300">192.168.1.0/24</code>,{" "}
            <code className="text-violet-300">10.0.0.5/32</code> pour une IP unique,{" "}
            <code className="text-violet-300">2001:db8::/32</code> pour IPv6.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex items-end gap-3" onSubmit={createRule}>
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="cidr">CIDR</Label>
              <Input
                id="cidr"
                placeholder="ex. 203.0.113.0/24"
                value={cidr}
                onChange={(e) => setCidr(e.target.value)}
                disabled={creating}
                required
              />
            </div>
            <Button type="submit" disabled={creating || !cidr.trim()}>
              {creating ? "Ajout…" : "Ajouter"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Règles actives</CardTitle>
          <CardDescription>
            {loading
              ? "Chargement…"
              : rules.length === 0
                ? "Aucune règle définie — tout le trafic est autorisé."
                : `${rules.length} règle${rules.length > 1 ? "s" : ""} active${rules.length > 1 ? "s" : ""}.`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {rules.length > 0 && (
            <ul className="divide-y divide-white/[0.06]">
              {rules.map((rule) => (
                <li
                  key={rule.id}
                  className="flex items-center justify-between py-3"
                >
                  <div className="flex items-center gap-3">
                    <code className="rounded-md bg-white/[0.04] px-2 py-1 font-mono text-sm text-violet-200">
                      {rule.cidr}
                    </code>
                    <span
                      className={`text-[11px] font-semibold uppercase tracking-wider ${
                        rule.is_active ? "text-emerald-300" : "text-white/35"
                      }`}
                    >
                      {rule.is_active ? "active" : "inactive"}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => deleteRule(rule.id)}
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-[12px] text-rose-200 transition hover:bg-rose-500/[0.08] hover:text-rose-100"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Supprimer
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
