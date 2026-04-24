"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { ApiError, apiUpload } from "@/lib/api";
import type { UploadResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const ACCEPTED: Record<string, string[]> = {
  "application/pdf": [".pdf"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
};
const MAX_SIZE = 20 * 1024 * 1024;

type UploadItem = {
  file: File;
  status: "pending" | "uploading" | "done" | "error";
  error?: string;
  invoiceId?: string;
};

export default function UploadPage() {
  const router = useRouter();
  const [items, setItems] = useState<UploadItem[]>([]);

  const onDrop = useCallback((accepted: File[]) => {
    setItems((prev) => [...prev, ...accepted.map((f) => ({ file: f, status: "pending" as const }))]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxSize: MAX_SIZE,
  });

  async function uploadAll() {
    const pending = items.filter((i) => i.status === "pending");
    for (const item of pending) {
      setItems((prev) => prev.map((x) => (x === item ? { ...x, status: "uploading" } : x)));
      try {
        const res = await apiUpload<UploadResponse>("/invoices/upload", item.file);
        setItems((prev) =>
          prev.map((x) =>
            x === item ? { ...x, status: "done", invoiceId: res.id } : x,
          ),
        );
      } catch (err) {
        const message =
          err instanceof ApiError
            ? typeof err.payload === "object" && err.payload !== null && "detail" in err.payload
              ? String((err.payload as { detail: unknown }).detail)
              : `Erreur ${err.status}`
            : "Erreur réseau";
        setItems((prev) =>
          prev.map((x) => (x === item ? { ...x, status: "error", error: message } : x)),
        );
      }
    }
  }

  const hasPending = items.some((i) => i.status === "pending");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Importer des factures</h1>
        <p className="text-sm text-muted-foreground">
          Formats acceptés : PDF, JPG, PNG — 20 Mo max par fichier.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Glisser-déposer</CardTitle>
          <CardDescription>Ou clique pour sélectionner depuis ton disque.</CardDescription>
        </CardHeader>
        <CardContent>
          <div
            {...getRootProps()}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 text-center transition-colors",
              isDragActive ? "border-primary bg-primary/5" : "border-muted-foreground/30 hover:bg-muted/30",
            )}
          >
            <input {...getInputProps()} />
            <p className="text-sm font-medium">
              {isDragActive ? "Dépose ici…" : "Glisse tes factures ou clique pour parcourir"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">PDF, JPG, PNG</p>
          </div>
        </CardContent>
      </Card>

      {items.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Fichiers sélectionnés ({items.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ul className="divide-y">
              {items.map((item, idx) => (
                <li key={idx} className="flex items-center justify-between py-2 text-sm">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{item.file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {(item.file.size / 1024).toFixed(0)} Ko
                      {item.error && <span className="ml-2 text-destructive">— {item.error}</span>}
                    </p>
                  </div>
                  <span
                    className={cn(
                      "ml-4 shrink-0 text-xs font-medium",
                      item.status === "done" && "text-emerald-600",
                      item.status === "error" && "text-destructive",
                      item.status === "uploading" && "text-blue-600",
                    )}
                  >
                    {item.status === "pending" && "En attente"}
                    {item.status === "uploading" && "Envoi…"}
                    {item.status === "done" && "✓ Importée"}
                    {item.status === "error" && "Erreur"}
                  </span>
                  {item.invoiceId && (
                    <Link
                      href={`/invoices/${item.invoiceId}` as never}
                      className="ml-3 text-xs font-medium text-violet-300 underline-offset-4 hover:underline"
                    >
                      Ouvrir
                    </Link>
                  )}
                </li>
              ))}
            </ul>
            <div className="flex gap-2">
              <Button onClick={uploadAll} disabled={!hasPending}>
                Importer {hasPending ? `(${items.filter((i) => i.status === "pending").length})` : ""}
              </Button>
              <Button variant="outline" onClick={() => router.push("/dashboard")}>
                Retour au tableau de bord
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
