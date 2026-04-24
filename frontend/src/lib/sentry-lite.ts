"use client";

type ErrorLike = Error | PromiseRejectionEvent | string | unknown;

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
const environment = process.env.NEXT_PUBLIC_ENVIRONMENT ?? "development";
const release = process.env.NEXT_PUBLIC_RELEASE_VERSION ?? "local";

let installed = false;

export function installFrontendErrorReporting() {
  if (!dsn || installed || typeof window === "undefined") return;
  installed = true;

  window.addEventListener("error", (event) => {
    captureFrontendError(event.error ?? event.message, {
      source: event.filename,
      line: event.lineno,
      column: event.colno,
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    captureFrontendError(event.reason ?? event, { source: "unhandledrejection" });
  });
}

export async function captureFrontendError(error: ErrorLike, extra: Record<string, unknown> = {}) {
  if (!dsn || typeof window === "undefined") return;

  const parsed = parseDsn(dsn);
  if (!parsed) return;

  const normalized = normalizeError(error);
  const event = {
    event_id: crypto.randomUUID().replaceAll("-", ""),
    timestamp: new Date().toISOString(),
    platform: "javascript",
    level: "error",
    environment,
    release,
    request: {
      url: window.location.href,
      headers: {
        "User-Agent": navigator.userAgent,
      },
    },
    exception: {
      values: [
        {
          type: normalized.name,
          value: normalized.message,
          stacktrace: normalized.stack ? { frames: parseStack(normalized.stack) } : undefined,
        },
      ],
    },
    extra,
  };

  const envelope = [
    JSON.stringify({ event_id: event.event_id, sent_at: event.timestamp, dsn }),
    JSON.stringify({ type: "event" }),
    JSON.stringify(event),
  ].join("\n");

  await fetch(parsed.envelopeUrl, {
    method: "POST",
    body: envelope,
    keepalive: true,
    headers: { "Content-Type": "application/x-sentry-envelope" },
  }).catch(() => undefined);
}

function parseDsn(value: string): { envelopeUrl: string } | null {
  try {
    const url = new URL(value);
    const projectId = url.pathname.replace("/", "");
    const base = `${url.protocol}//${url.host}`;
    return { envelopeUrl: `${base}/api/${projectId}/envelope/` };
  } catch {
    return null;
  }
}

function normalizeError(error: ErrorLike): { name: string; message: string; stack?: string } {
  if (error instanceof Error) {
    return { name: error.name, message: error.message, stack: error.stack };
  }
  if (typeof error === "string") {
    return { name: "Error", message: error };
  }
  return { name: "Error", message: JSON.stringify(error) };
}

function parseStack(stack: string) {
  return stack
    .split("\n")
    .slice(1, 30)
    .map((line) => ({
      function: line.trim(),
      filename: "browser",
      lineno: 0,
      colno: 0,
    }))
    .reverse();
}
