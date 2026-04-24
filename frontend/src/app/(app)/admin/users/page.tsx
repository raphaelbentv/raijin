"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { apiFetch, ApiError } from "@/lib/api";
import type {
  TenantUser,
  UserCreatePayload,
  UserCreatedResponse,
  UserRole,
} from "@/lib/types";
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

const ROLES: UserRole[] = ["admin", "reviewer", "viewer"];

function roleLabel(role: UserRole): string {
  switch (role) {
    case "admin":
      return "Admin";
    case "reviewer":
    case "user":
      return "Reviewer";
    case "viewer":
      return "Viewer";
  }
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [activationLink, setActivationLink] = useState<string | null>(null);

  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState<UserRole>("reviewer");

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<TenantUser[]>("/users");
      setUsers(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        toast.error("Accès réservé aux administrateurs");
      } else {
        toast.error("Impossible de charger les utilisateurs");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createUser() {
    if (!newEmail) return;
    setCreating(true);
    try {
      const body: UserCreatePayload = {
        email: newEmail,
        full_name: newName || null,
        role: newRole,
      };
      const res = await apiFetch<UserCreatedResponse>("/users", {
        method: "POST",
        json: body,
      });
      setActivationLink(res.activation_link);
      setNewEmail("");
      setNewName("");
      setNewRole("reviewer");
      await load();
      toast.success("Invitation envoyée");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error("Email déjà utilisé");
      } else {
        toast.error("Création impossible");
      }
    } finally {
      setCreating(false);
    }
  }

  async function updateRole(user: TenantUser, role: UserRole) {
    try {
      await apiFetch(`/users/${user.id}`, {
        method: "PATCH",
        json: { role },
      });
      toast.success(`Rôle mis à jour : ${roleLabel(role)}`);
      await load();
    } catch {
      toast.error("Mise à jour impossible");
    }
  }

  async function toggleActive(user: TenantUser) {
    try {
      await apiFetch(`/users/${user.id}`, {
        method: "PATCH",
        json: { is_active: !user.is_active },
      });
      toast.success(user.is_active ? "Utilisateur désactivé" : "Utilisateur réactivé");
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error("Tu ne peux pas te désactiver toi-même");
      } else {
        toast.error("Action impossible");
      }
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Utilisateurs</h1>
        <p className="text-sm text-muted-foreground">
          Gère les comptes de ton organisation.
        </p>
      </div>

      {activationLink && (
        <Card>
          <CardContent className="space-y-2 pt-6">
            <p className="text-sm font-medium">Lien d&apos;activation dev :</p>
            <a
              href={activationLink}
              className="block break-all rounded-md bg-muted px-3 py-2 text-sm underline-offset-4 hover:underline"
            >
              {activationLink}
            </a>
            <Button variant="outline" size="sm" onClick={() => setActivationLink(null)}>
              Masquer
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Ajouter un utilisateur</CardTitle>
          <CardDescription>
            Un email d&apos;activation sera envoyé à la personne concernée.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-4">
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor="invite-email">Email</Label>
            <Input
              id="invite-email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              type="email"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="invite-name">Nom</Label>
            <Input
              id="invite-name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="invite-role">Rôle</Label>
            <select
              id="invite-role"
              value={newRole}
              onChange={(e) => setNewRole(e.target.value as UserRole)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {roleLabel(r)}
                </option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-4">
            <Button onClick={createUser} disabled={creating || !newEmail}>
              {creating ? "Envoi…" : "Inviter"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Équipe ({users.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Chargement…</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="py-2">Email</th>
                  <th className="py-2">Nom</th>
                  <th className="py-2">Rôle</th>
                  <th className="py-2">Statut</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="py-3 font-medium">{u.email}</td>
                    <td className="py-3 text-muted-foreground">{u.full_name ?? "—"}</td>
                    <td className="py-3">
                      <select
                        value={u.role}
                        onChange={(e) => updateRole(u, e.target.value as UserRole)}
                        className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {roleLabel(r)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-3">
                      {u.is_active ? (
                        <span className="text-emerald-700">actif</span>
                      ) : (
                        <span className="text-rose-700">désactivé</span>
                      )}
                    </td>
                    <td className="py-3">
                      <Button size="sm" variant="ghost" onClick={() => toggleActive(u)}>
                        {u.is_active ? "Désactiver" : "Réactiver"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
