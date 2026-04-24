"use client";

import { useEffect } from "react";

import { captureFrontendError } from "@/lib/sentry-lite";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    captureFrontendError(error, { digest: error.digest });
  }, [error]);

  return (
    <html lang="fr">
      <body className="min-h-screen bg-background text-foreground">
        <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-6">
          <p className="font-serif text-sm italic text-primary">Raijin</p>
          <h1 className="mt-3 text-3xl font-semibold">Une erreur est survenue</h1>
          <p className="mt-3 text-sm text-muted-foreground">
            L’incident a été transmis à l’équipe si le reporting est configuré.
          </p>
          <button className="btn-primary-violet mt-6 w-fit" onClick={reset}>
            Réessayer
          </button>
        </main>
      </body>
    </html>
  );
}
